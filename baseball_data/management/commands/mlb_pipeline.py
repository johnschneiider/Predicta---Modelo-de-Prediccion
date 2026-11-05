"""
Pipeline diario MLB: captura líneas reales (API-Sports odds, multi-bookie),
predice con el modelo v1 (baseline validado), liquida con resultados reales y
acumula ROI por mercado en baseball_data/reports/live_roi.json.

Modos:
  --backfill-days N : procesa partidos terminados de los últimos N días
                      (dentro de la ventana de retención de odds de la API).
  --capture         : captura líneas de partidos próximos (hoy/mañana) a pending.json
  --settle          : liquida los picks de pending.json cuyos partidos terminaron

Regla de apuesta: edge = P(modelo) - P(mercado desvigado) >= 0.03 → 1u a la mejor cuota.
Mercados: moneyline, totales (todas las líneas), run line ±1.5.
"""
import json
import os
from collections import defaultdict

from django.conf import settings
from django.core.management.base import BaseCommand

from baseball_data.baseline import RollingStats, predict_matchup
from baseball_data.models import BaseballGame, BaseballTeam
from baseball_data.services import mlb_service

REPORT_DIR = os.path.join(settings.BASE_DIR, 'baseball_data', 'reports')
ROI_PATH = os.path.join(REPORT_DIR, 'live_roi.json')
PENDING_PATH = os.path.join(REPORT_DIR, 'pending_lines.json')
MIN_EDGE = 0.03
TOTAL_LINES = (5.5, 6.5, 7.5, 8.5, 9.5, 10.5, 11.5)
FIRST5_LINES = (2.5, 3.5, 4.5, 5.5)


def _devig(odds_a, odds_b):
    pa, pb = 1 / odds_a, 1 / odds_b
    s = pa + pb
    return pa / s, pb / s


def _collect_odds(odds_response):
    """Extrae por mercado las probabilidades fair promedio multi-bookie."""
    ml = []
    totals = defaultdict(list)  # line -> [(p_over, p_under)]
    rl = []
    for obj in odds_response:
        for bm in obj.get("bookmakers", []):
            for bet in bm.get("bets", []):
                name = bet.get("name")
                vals = [(x.get("value"), float(x.get("odd"))) for x in bet.get("values", []) if x.get("odd")]
                if name == "Home/Away" and len(vals) == 2:
                    d = dict(vals)
                    if 'Home' in d and 'Away' in d:
                        ph, pa = _devig(d['Home'], d['Away'])
                        ml.append((ph, pa, d['Home'], d['Away']))
                elif name == "Over/Under":
                    for v, odd in vals:
                        if v.startswith("Over ") and ("Under " + v[5:], ) and v[5:]:
                            pass
                    # agrupar por línea
                    pairs = {}
                    for v, odd in vals:
                        line = v.split(" ", 1)[1]
                        pairs.setdefault(line, {})[v.split(" ")[0]] = odd
                    for line, d in pairs.items():
                        if 'Over' in d and 'Under' in d:
                            po, pu = _devig(d['Over'], d['Under'])
                            totals[line].append((po, pu, d['Over'], d['Under']))
                elif name == "Asian Handicap":
                    pairs = {}
                    for v, odd in vals:
                        side, hc = v.rsplit(" ", 1)
                        pairs.setdefault(hc, {})[side] = odd
                    if "-1.5" in pairs and "+1.5" in pairs:
                        ph, pa = _devig(pairs["-1.5"]["Home"], pairs["+1.5"]["Away"])
                        rl.append((ph, pa, pairs["-1.5"]["Home"], pairs["+1.5"]["Away"]))
    out = {'ml': ml, 'totals': {k: v for k, v in totals.items()}, 'rl': rl}
    return out


def _avg(pairs):
    if not pairs:
        return None
    return tuple(sum(x[i] for x in pairs) / len(pairs) for i in range(4))


class Command(BaseCommand):
    help = "Pipeline diario de líneas + ROI por mercado (MLB)"

    def add_arguments(self, parser):
        parser.add_argument('--backfill-days', type=int, default=0)
        parser.add_argument('--capture', action='store_true')
        parser.add_argument('--settle', action='store_true')

    def handle(self, *args, **options):
        os.makedirs(REPORT_DIR, exist_ok=True)
        if options['backfill_days']:
            self._backfill(options['backfill_days'])
        if options['capture']:
            self._capture()
        if options['settle']:
            self._settle()
        if not any([options['backfill_days'], options['capture'], options['settle']]):
            self.stderr.write("Usa --backfill-days N, --capture y/o --settle")

    # ── Backfill de días pasados (dentro de la ventana de odds) ──
    def _backfill(self, days):
        from datetime import datetime, timedelta, timezone
        today = datetime.now(timezone.utc).date()
        roi = self._load(ROI_PATH)
        processed = set(r['game'] for r in roi.get('bets', []))

        for i in range(1, days + 1):
            d = (today - timedelta(days=i)).isoformat()
            games = mlb_service.fetch_games_by_date(d)
            for g in games:
                if g.get("status", {}).get("long") not in ("Game Finished", "Finished", "After OT"):
                    continue
                if g["id"] in processed:
                    continue
                odds = mlb_service.fetch_odds(g["id"])
                if not odds:
                    continue
                self._settle_one(roi, g, odds)
                processed.add(g["id"])
        self._save(ROI_PATH, roi)
        self._print_roi(roi)

    # ── Captura de próximos partidos ──
    def _capture(self):
        from datetime import datetime, timedelta, timezone
        today = datetime.now(timezone.utc).date()
        pending = self._load(PENDING_PATH)
        for i in range(0, 2):
            d = (today + timedelta(days=i)).isoformat()
            games = mlb_service.fetch_games_by_date(d)
            for g in games:
                if g.get("status", {}).get("long") != "Not Started":
                    continue
                if g["id"] in pending:
                    continue
                odds = mlb_service.fetch_odds(g["id"])
                if not odds:
                    continue
                pending[g["id"]] = {"date": d, "odds": odds}
        self._save(PENDING_PATH, pending)
        self.stdout.write(f"Pendientes capturados: {len(pending)} partidos")

    # ── Liquidación de pendientes ──
    def _settle(self):
        pending = self._load(PENDING_PATH)
        roi = self._load(ROI_PATH)
        settled = set(r['game'] for r in roi.get('bets', []))
        from datetime import datetime, timedelta, timezone
        today = datetime.now(timezone.utc).date()
        for gid, entry in list(pending.items()):
            d = (today - timedelta(days=1)).isoformat()
            games = mlb_service.fetch_games_by_date(d)
            g = next((x for x in games if x["id"] == int(gid)), None)
            if g is None or g.get("status", {}).get("long") not in ("Game Finished", "Finished", "After OT"):
                continue
            if gid not in settled:
                self._settle_one(roi, g, entry["odds"])
                settled.add(gid)
            del pending[gid]
        self._save(PENDING_PATH, pending)
        self._save(ROI_PATH, roi)
        self._print_roi(roi)

    # ── Liquidación de un partido contra sus líneas ──
    def _settle_one(self, roi, api_game, odds_response):
        try:
            game = BaseballGame.objects.get(api_id=api_game["id"])
        except BaseballGame.DoesNotExist:
            return
        if game.home_runs is None or game.away_runs is None:
            return
        # predicción con stats estrictamente anteriores al partido
        prior = BaseballGame.objects.filter(
            home_runs__isnull=False, away_runs__isnull=False,
            status__in=('Game Finished', 'Finished', 'After OT'),
            date__lt=game.date).order_by('date')
        stats = RollingStats()
        for g in prior.iterator():
            stats.update(g)
        pred = predict_matchup(stats, game.home_team_id, game.away_team_id,
                               TOTAL_LINES, FIRST5_LINES)

        hr, ar = game.home_runs, game.away_runs
        total = hr + ar
        collected = _collect_odds(odds_response)

        bets = roi.setdefault('bets', [])
        results = defaultdict(lambda: {'n': 0, 'won': 0, 'stake': 0.0, 'net': 0.0, 'ev_sum': 0.0})

        ml = _avg(collected['ml'])
        if ml:
            ph, pa, oh, oa = ml
            for side, p_model, odds_best, outcome in (
                    ('home', pred['p_home_win'], oh, 1 if hr > ar else 0),
                    ('away', pred['p_away_win'], oa, 1 if ar > hr else 0)):
                if p_model - (1 / odds_best) >= MIN_EDGE:
                    self._record(bets, results, 'moneyline', game, side, odds_best,
                                 p_model, outcome)

        for line, pairs in collected['totals'].items():
            avg = _avg(pairs)
            if not avg or line not in {str(x) for x in TOTAL_LINES}:
                continue
            po, pu, oo, ou = avg
            over = 1 if total > float(line) else 0
            for side, p_model, odds_best, outcome in (
                    ('over', pred['total_line_probs'][line]['over'], oo, over),
                    ('under', pred['total_line_probs'][line]['under'], ou, 1 - over)):
                if p_model - (1 / odds_best) >= MIN_EDGE:
                    self._record(bets, results, 'totals', game, f"{side}_{line}",
                                 odds_best, p_model, outcome)

        rl = _avg(collected['rl'])
        if rl:
            ph, pa, oh, oa = rl
            home_covers = 1 if hr - ar >= 2 else 0
            for side, p_model, odds_best, outcome in (
                    ('home_-1.5', pred['runline_probs']['1.5']['home'], oh, home_covers),
                    ('away_+1.5', pred['runline_probs']['1.5']['away'], oa, 1 - home_covers)):
                if p_model - (1 / odds_best) >= MIN_EDGE:
                    self._record(bets, results, 'runline', game, side, odds_best,
                                 p_model, outcome)

        for mkt, r in results.items():
            agg = roi.setdefault('markets', {}).setdefault(
                mkt, {'n': 0, 'won': 0, 'stake': 0.0, 'net': 0.0, 'ev_sum': 0.0})
            for k in ('n', 'won', 'stake', 'net', 'ev_sum'):
                agg[k] += r[k]

    @staticmethod
    def _record(bets, results, mkt, game, side, odds, p_model, outcome):
        stake = 1.0
        net = (odds - 1) if outcome else -1.0
        r = results[mkt]
        r['n'] += 1
        r['won'] += outcome
        r['stake'] += stake
        r['net'] += net
        r['ev_sum'] += p_model * odds - 1
        bets.append({
            'game': game.api_id, 'date': str(game.date.date()),
            'teams': f"{game.away_team.name} @ {game.home_team.name}",
            'market': mkt, 'side': side, 'odds': odds,
            'p_model': round(p_model, 4), 'outcome': outcome,
            'net': round(net, 2),
        })

    # ── Utilidades ──
    @staticmethod
    def _load(path):
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
        return {'markets': {}, 'bets': []}

    @staticmethod
    def _save(path, data):
        with open(path, 'w') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _print_roi(self, roi):
        self.stdout.write("\n=== ROI acumulado por mercado (líneas reales API) ===")
        for mkt, r in roi.get('markets', {}).items():
            if r['n'] == 0:
                continue
            roi_v = r['net'] / r['stake'] if r['stake'] else 0
            self.stdout.write(
                f"  {mkt:<10} n={r['n']:<4} hit={r['won']/r['n']:.2f} "
                f"ROI={roi_v:+.1%} EV_acum={r['ev_sum']:+.2f}u")
