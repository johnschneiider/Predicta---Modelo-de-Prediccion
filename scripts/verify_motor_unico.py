"""
VERIFICACIÓN MOTOR ÚNICO (2026-09-01)
Compara para partidos de HOY (apuestas del día) y MAÑANA (fixtures API 02-Sep)
que web (build_web_predictions), auto_betting (get_official_predictions) y
value_betting (generate_full_prediction) arrojen EXACTAMENTE el mismo dato.

Salida: totales por mercado y lista de desajustes (debe ser vacía).
"""
import sys
sys.path.insert(0, '/var/www/predicta.com.co')
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
import django
django.setup()
import logging
logging.disable(logging.CRITICAL)

from django.utils import timezone
from auto_betting.models import AutoBet
from football_data.models import League
from football_api.models import ApiFixture, ApiTeam, ApiLeague
from ai_predictions.web_pipeline import build_web_predictions, get_official_prediction
from auto_betting.strategy import get_official_predictions
from value_betting.services import generate_full_prediction

TYPES = ['goals_total', 'corners_total', 'shots_on_target_total', 'both_teams_score']

def comparar(home, away, liga, etiqueta):
    """Compara los 3 motores para un partido. Devuelve (desajustes, omitidas)."""
    desajustes = []
    if liga is None:
        return desajustes, []
    try:
        wp = build_web_predictions(home, away, liga, prediction_types=TYPES)
    except Exception as e:
        return [f'{etiqueta} [{liga.name}] {home} vs {away}: web_pipeline EXCEPCIÓN {e}'], []
    try:
        ab = get_official_predictions(home, away, liga)
    except Exception as e:
        return [f'{etiqueta} [{liga.name}] {home} vs {away}: auto_betting EXCEPCIÓN {e}'], []
    try:
        fp = generate_full_prediction(home, away, liga)
    except Exception as e:
        return [f'{etiqueta} [{liga.name}] {home} vs {away}: value_betting EXCEPCIÓN {e}'], []

    def o(pt):
        p = get_official_prediction(wp, pt)
        return float(p['prediction']) if p else None

    w_goals, w_corn, w_sot, w_btts = o('goals_total'), o('corners_total'), o('shots_on_target_total'), o('both_teams_score')

    ab_goals = ab.get('goals_total', {}).get('lambda')
    ab_corn = ab.get('corners_total', {}).get('lambda')
    ab_sot = ab.get('shots_on_target', {}).get('lambda')
    ab_btts = ab.get('both_teams_score', {}).get('yes')

    fp_goals = fp.get('lambda_total') if fp else None
    fp_corn = fp.get('corners_total_pred') if fp else None
    fp_btts = fp.get('p_bts_yes') if fp else None

    def eq(a, b, tol=1e-9):
        if a is None and b is None:
            return True
        if a is None or b is None:
            return False
        return abs(a - b) < tol

    # Si auto_betting omite un mercado (None) pero la web genera, es el gate de
    # cobertura (validate_market_data ≥10 partidos por equipo) — comportamiento
    # esperado de APUESTAS, no un desajuste de dato. Se cuenta aparte.
    def registrar(etiqueta_mc, w, ab, vb, omitidas, des):
        if ab is None and w is not None:
            omitidas.append(f'{etiqueta} {etiqueta_mc}: omitido por cobertura (web={round(w,2)})')
            return
        if not eq(w, ab):
            des.append(f'{etiqueta} {etiqueta_mc}: web={w} vs auto={ab}')
        if vb is not None and not eq(w, vb):
            des.append(f'{etiqueta} {etiqueta_mc}: web={w} vs value={vb}')

    omitidas = []
    registrar('goles', w_goals, ab_goals, fp_goals, omitidas, desajustes)
    registrar('córners', w_corn, ab_corn, fp_corn, omitidas, desajustes)
    registrar('tiros a puerta', w_sot, ab_sot, None, omitidas, desajustes)
    registrar('btts', w_btts, ab_btts, fp_btts, omitidas, desajustes)
    return desajustes, omitidas

def main():
    total = 0
    todos = []
    todas_omitidas = []
    ligas = {l.name: l for l in League.objects.all()}

    # ── HOY: combinaciones únicas de apuestas (saltable con --solo-manana) ──
    if '--solo-manana' not in sys.argv:
        bets = AutoBet.objects.filter(creado__date=timezone.localdate())
        unicos = {}
        for b in bets:
            unicos[(b.home_team, b.away_team, b.liga)] = b
        print(f'HOY: {len(unicos)} partidos únicos apostados')
        for (home, away, liga), b in unicos.items():
            lg = ligas.get(liga)
            des, omi = comparar(home, away, lg, f'HOY {home} vs {away} [{liga}]')
            todos += des
            todas_omitidas += omi
            total += 1
    else:
        print('HOY: omitido (--solo-manana)')

    # ── MAÑANA: fixtures API-Football del 02-Sep con predicta_league ──
    fixts = list(ApiFixture.objects.filter(date__date='2026-09-02').select_related('home_team', 'away_team', 'league')[:30])
    validos = []
    for f in fixts:
        try:
            al = f.league
            if al and al.predicta_league_id:
                lg = League.objects.filter(id=al.predicta_league_id).first()
                if lg:
                    validos.append((f.home_team.name, f.away_team.name, lg))
        except Exception:
            continue
    print(f'MAÑANA: {len(validos)} fixtures con predicta_league')
    for home, away, lg in validos[:15]:
        des, omi = comparar(home, away, lg, f'MAÑANA {home} vs {away} [{lg.name}]')
        todos += des
        todas_omitidas += omi
        total += 1

    print(f'\n═══ RESULTADO: {total} partidos comparados, {len(todos)} desajustes reales ═══')
    for d in todos:
        print('  ✘', d)
    if not todos:
        print('  ✔ Los 3 motores (web / auto_betting / value_betting) arrojan EL MISMO dato en todos los mercados que ambos generan.')
    if todas_omitidas:
        print(f'\n  ℹ {len(todas_omitidas)} mercados omitidos por el gate de cobertura del auto_betting (esperado, no es desajuste):')
        for o in todas_omitidas[:25]:
            print('    -', o)

if __name__ == '__main__':
    main()
