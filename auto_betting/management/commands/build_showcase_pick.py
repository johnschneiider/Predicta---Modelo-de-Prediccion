"""
Partido destacado de la portada (ShowcasePick) — vitrina con datos reales.

Reutiliza la maquinaria REAL del auto-betting, sin credenciales:
  1. Partidos próximos NOT_STARTED de Kambi/BetPlay (ventana --hours).
  2. Mapeo liga/equipos al universo Predicta (exacto + fuzzy).
  3. Predicción Oficial + cuotas reales por mercado (_build_market_data).
  4. Selección por EV/edge con los filtros globales vigentes (select_bets).

Guarda el mejor candidato del primer partido (cronológico) con señal, junto
con las probabilidades 1X2 del mismo partido (tarjeta de calibración de la
portada). La home muestra la fila más reciente cuyo partido aún no empieza.

No coloca apuestas ni usa el ticket de BetPlay: solo endpoints públicos.
"""

import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone as django_timezone

from auto_betting.management.commands.run_auto_bets import (
    _build_market_data,
    find_predicta_league,
    map_teams,
)
from auto_betting.services import fetch_upcoming_matches
from auto_betting.strategy import (
    get_global_config,
    get_market_filters,
    predict_x12,
    select_bets,
)

logger = logging.getLogger('auto_betting')

# Etiqueta corta del objeto para armar la selección legible (ej. 'Over 9.5 córners')
_OBJETO_BAJO = {
    'corners': 'córners',
    'goals': 'goles',
    'shots_on_target': 'tiros a puerta',
    'remates': 'remates',
}
MERCADO_OPS = {
    'corners': 'Córners',
    'goals': 'Goles',
    'btts': 'Ambos Equipos Marcarán',
    'shots_on_target': 'Tiros a puerta',
    'remates': 'Remates totales',
}

# Umbral de presentación: la vitrina solo muestra señales con valor positivo
# claro contra el precio de mercado (evita un 'EDGE -0.2%' en portada).
MIN_EDGE_VITRINA = 0.02


def _seleccion_display(best):
    """Etiqueta legible para la portada (ej. 'Over 9.5 córners', 'Ambos marcan: Sí')."""
    if best['market'] == 'btts':
        return f"Ambos marcan: {best['side']}"
    etiqueta = f"{'Over' if best['side'] == 'over' else 'Under'} {best['line']}"
    objeto = _OBJETO_BAJO.get(best['market'])
    return f'{etiqueta} {objeto}' if objeto else etiqueta


class Command(BaseCommand):
    help = ('Genera el partido destacado de la portada (ShowcasePick) con '
            'selección real del motor y cuotas reales.')

    def add_arguments(self, parser):
        parser.add_argument('--hours', type=int, default=36,
                            help='Ventana hacia adelante en horas (default 36).')
        parser.add_argument('--max-matches', type=int, default=25,
                            help='Máximo de partidos mapeables a evaluar (default 25).')
        parser.add_argument('--min-lead-minutes', type=int, default=30,
                            help='Margen mínimo antes del inicio del partido (default 30).')
        parser.add_argument('--cuota-minima', type=float, default=1.7,
                            help='Cuota mínima para candidatos (default 1.7).')

    def handle(self, *args, **options):
        from auto_betting.models import ShowcasePick

        now = django_timezone.now()

        # Housekeeping: fuera filas de más de 3 días
        ShowcasePick.objects.filter(generado__lt=now - timedelta(days=3)).delete()

        matches = fetch_upcoming_matches(options['hours'])
        matches.sort(key=lambda m: m['start_time'])
        min_lead = timedelta(minutes=options['min_lead_minutes'])
        matches = [m for m in matches if m['start_time'] >= now + min_lead]

        gcfg = get_global_config()
        calib_cap = gcfg.get('calib_cap', 0.58) or 0.58
        market_filters = get_market_filters()
        # Misma neutralización que el auto-betting: la cuota mínima de la config
        # global no aplica; aquí manda --cuota-minima (referencia operativa).
        market_filters = {k: {**v, 'min_cuota': 0.0} for k, v in market_filters.items()}

        scanned = 0
        winner = None
        league_winner = None
        match_winner = None

        for m in matches:
            if scanned >= options['max_matches']:
                break
            league = find_predicta_league(m)
            if not league:
                continue
            home, away = map_teams(m, league)
            if not home or not away:
                continue
            scanned += 1
            try:
                markets = _build_market_data(m, home, away, league)
            except Exception as e:
                logger.error(f'build_showcase_pick: _build_market_data falló '
                             f'{home} vs {away}: {e}')
                continue
            if not markets:
                continue
            candidates = select_bets(
                markets, options['cuota_minima'], min_p=0.45, min_confidence=0.35,
                market_filters=market_filters, calib_cap=calib_cap,
            )
            # Filtro de presentación: EDGE positivo claro contra el precio
            candidates = [c for c in candidates if (c['p'] * c['cuota'] - 1.0) >= MIN_EDGE_VITRINA]
            if not candidates:
                continue
            winner = candidates[0]  # ordenados por EV descendente
            league_winner = league
            match_winner = (m, home, away)
            break

        if not winner:
            self.stdout.write(self.style.WARNING(
                f'build_showcase_pick: sin candidatos en {options["hours"]}h '
                f'({scanned} partidos evaluados). Nada que guardar.'
            ))
            return

        m, home, away = match_winner
        best = winner

        # 1X2 del mismo partido (tarjeta de calibración de la portada)
        x12 = None
        try:
            x12 = predict_x12(home, away, league_winner)
        except Exception as e:
            logger.warning(f'build_showcase_pick: x12 falló para {home} vs {away}: {e}')

        p = best['p']
        cuota = best['cuota']
        pick = ShowcasePick.objects.create(
            home_team=home,
            away_team=away,
            liga=league_winner.name,
            start_time=m['start_time'],
            mercado=MERCADO_OPS.get(best['market'], best['market']),
            seleccion=_seleccion_display(best),
            linea=best.get('line'),
            cuota=cuota,
            cuota_justa=round(1.0 / p, 3) if p else None,          # cuota que iguala nuestra prob.
            fair_odds=best.get('fair_odds'),                        # devig mercado (referencia)
            prob=round(p * 100, 2),
            prob_raw=round((best.get('p_raw') or p) * 100, 2),
            prob_mercado=round(100.0 / cuota, 1) if cuota else None,
            edge=round((p * cuota - 1.0) * 100, 2),                 # valor al precio de mercado
            ev=round(best['ev'] * 100, 2),                          # EV vs cuota justa devig (motor)
            confianza=best.get('confidence'),
            x12_local=round(x12['home'] * 100, 2) if x12 else None,
            x12_empate=round(x12['draw'] * 100, 2) if x12 else None,
            x12_visita=round(x12['away'] * 100, 2) if x12 else None,
            evento_id=m['event_id'],
        )
        self.stdout.write(self.style.SUCCESS(
            f'✅ Showcase #{pick.id}: {home} vs {away} | {pick.mercado} — '
            f'{pick.seleccion} @{pick.cuota} | P={pick.prob}% | '
            f'edge={pick.edge:+.1f}% | EV={pick.ev:+.1f}% | '
            f'{pick.start_time:%Y-%m-%d %H:%M} UTC'
        ))
