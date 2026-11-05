# -*- coding: utf-8 -*-
"""Motor x12_v2 (Resultado Final 1X2) — migrado del paperbet a dinero real.

Reutiliza EXACTAMENTE el pipeline del paperbet (`run_paper_bets.py`) para no
introducir deriva entre lo que se midió en papel y lo que se apuesta:

  - Mismos features: `run_paper_bets.Command._goals_feats()` sobre
    `scripts/btts_v2/btts_state.pkl` (mismo TEAM_KEYS/PAIR/LSTATE).
  - Mismo modelo: `scripts/paperbet/engines.pkl` -> `eng['x12']`
    (clasificador 1X2) + `eng['x12_iso_h']` (isotónica de la clase local).
  - Mismo margen de calibración: `CAL_MARGIN` (2pp) del paperbet.

La compuerta de apuesta (P>=0.45, edge>=5pp vs fair devig, cuota>=1.80) NO
vive aquí: se aplica en `strategy.select_bets` + `MarketFilterConfig['x12']`
con las mismas constantes del papel.

Uso:
    from auto_betting.x12_engine import predict_x12_probs
    probs = predict_x12_probs(match, home_db, away_db, league)
    # -> {'home': float, 'draw': float, 'away': float} o None
"""

import logging
import pickle
from functools import lru_cache

logger = logging.getLogger('auto_betting')

S = '/var/www/predicta.com.co/scripts'
BTT_STATE_PATH = S + '/btts_v2/btts_state.pkl'
ENGINES_PATH = S + '/paperbet/engines.pkl'


@lru_cache(maxsize=1)
def _btt_state():
    with open(BTT_STATE_PATH, 'rb') as fh:
        return pickle.load(fh)


@lru_cache(maxsize=1)
def _engines():
    with open(ENGINES_PATH, 'rb') as fh:
        return pickle.load(fh)


def predict_x12_probs(match, home_team, away_team, league):
    """Probabilidades 1X2 del motor x12_v2 (ya con el margen de 2pp).

    Devuelve {'home','draw','away'} o None si faltan features/estado del
    partido (equipo sin historial en el estado del paperbet).
    """
    return predict_x12_probs_for(league.id, home_team, away_team, match['start_time'])


def predict_x12_probs_for(lid, home_team, away_team, start_time):
    """Igual que predict_x12_probs pero con el id de liga ya resuelto."""
    # Import perezoso: run_paper_bets importa run_auto_bets (que a su vez
    # importa este módulo de forma perezosa) -> evita el ciclo de imports.
    from auto_betting.management.commands.run_paper_bets import (
        Command as PaperCommand, FEATS, CAL_MARGIN,
    )

    st = _btt_state()
    eng = _engines()

    hk = st['TEAM_KEYS'].get(f'{lid}|{home_team}')
    ak = st['TEAM_KEYS'].get(f'{lid}|{away_team}')
    if hk is None or ak is None:
        return None

    row = PaperCommand()._goals_feats(st, hk, ak, lid, start_time)
    import pandas as pd
    X = pd.DataFrame([[row[k] for k in FEATS]], columns=FEATS).astype(float)

    p_x = eng['x12'].predict_proba(X)[0]
    p_home = float(eng['x12_iso_h'].predict([p_x[0]])[0])
    return {
        'home': max(0.03, p_home - CAL_MARGIN),
        'draw': max(0.03, float(p_x[1]) - CAL_MARGIN),
        'away': max(0.03, float(p_x[2]) - CAL_MARGIN),
    }
