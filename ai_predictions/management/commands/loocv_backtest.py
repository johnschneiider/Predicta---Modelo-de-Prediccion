"""
LOOCV (Leave-One-Out Cross-Validation) Backtesting para detección de overfitting.

Para cada partido en la liga: entrena/promedia con TODOS los demás partidos,
predice el resultado de ESE partido, compara con el real.

Esto revela si los modelos están memorizando en vez de generalizar.

Uso:
  python manage.py loocv_backtest --league="Premier League" --n_matches=200
  python manage.py loocv_backtest --league="Serie A" --all
"""

import numpy as np
from collections import defaultdict
from django.core.management.base import BaseCommand
from football_data.models import Match, League
from typing import List, Dict, Tuple


class Command(BaseCommand):
    help = 'LOOCV backtesting para detectar overfitting en predicciones de resultados'

    def add_arguments(self, parser):
        parser.add_argument('--league', type=str, default=None, help='Nombre de liga (o "all" para todas)')
        parser.add_argument('--n_matches', type=int, default=200, help='Número de partidos recientes a testear')
        parser.add_argument('--all', action='store_true', help='Testear todas las ligas con datos')
        parser.add_argument('--full', action='store_true', help='LOOCV completo (todos los partidos)')
        parser.add_argument('--min_matches', type=int, default=50, help='Mínimo de partidos requerido')

    def handle(self, *args, **options):
        if options['all'] or options['full']:
            leagues = League.objects.all()
        elif options['league']:
            leagues = League.objects.filter(name__icontains=options['league'])
            if not leagues.exists():
                self.stdout.write(self.style.ERROR(f"Liga '{options['league']}' no encontrada"))
                return
        else:
            # Default: ligas principales europeas
            target_names = ['Premier League', 'La Liga', 'Serie A', 'Bundesliga', 'Ligue 1']
            leagues = League.objects.filter(name__in=target_names)

        all_results = []
        for league in leagues:
            result = self.backtest_league(league, options)
            if result:
                all_results.append(result)

        # Resumen final
        self.print_summary(all_results)

    def get_matches_with_results(self, league: League, n_matches: int = None):
        """Obtiene partidos con resultados FTR ordenados por fecha"""
        qs = Match.objects.filter(league=league).exclude(
            fthg__isnull=True
        ).exclude(
            ftag__isnull=True
        ).exclude(
            ftr__isnull=True
        ).order_by('-date')

        if n_matches:
            qs = qs[:n_matches]
        return list(qs)

    def compute_team_stats(self, matches: List[Match], exclude_match_id=None) -> Dict:
        """
        Calcula estadísticas agregadas de todos los partidos dados,
        excluyendo opcionalmente un partido específico (LOOCV).
        """
        teams = defaultdict(lambda: {
            'home_goals': [], 'away_goals': [],
            'home_shots': [], 'away_shots': [],
            'home_sot': [], 'away_sot': [],
            'home_conceded': [], 'away_conceded': [],
            'results': [],  # 'H', 'D', 'A'
            'home_results': [],
            'away_results': [],
            'opponents_home': [],
            'opponents_away': [],
        })

        for m in matches:
            if exclude_match_id and m.id == exclude_match_id:
                continue

            ht = m.home_team
            at = m.away_team

            # Goles
            teams[ht]['home_goals'].append(m.fthg or 0)
            teams[ht]['home_conceded'].append(m.ftag or 0)
            teams[at]['away_goals'].append(m.ftag or 0)
            teams[at]['away_conceded'].append(m.fthg or 0)

            # Tiros
            if m.hs is not None:
                teams[ht]['home_shots'].append(m.hs)
            if m.as_field is not None:
                teams[at]['away_shots'].append(m.as_field)
            if m.hst is not None:
                teams[ht]['home_sot'].append(m.hst)
            if m.ast is not None:
                teams[at]['away_sot'].append(m.ast)

            # Resultados
            teams[ht]['home_results'].append(m.ftr)
            teams[at]['away_results'].append(m.ftr)

            # Oponentes
            teams[ht]['opponents_home'].append(at)
            teams[at]['opponents_away'].append(ht)

        return teams

    def predict_match(self, home_team: str, away_team: str, stats: Dict) -> Tuple[str, float, Dict]:
        """
        Predice el resultado de un partido basado en estadísticas históricas
        de TODOS los demás partidos (excluyendo este).
        """
        home = stats.get(home_team, {})
        away = stats.get(away_team, {})

        # === Modelo 1: Poisson basado en goles ===
        home_avg_goals = np.mean(home.get('home_goals', [0])) if home.get('home_goals') else 1.0
        away_avg_goals = np.mean(away.get('away_goals', [0])) if away.get('away_goals') else 1.0
        home_avg_conceded = np.mean(home.get('home_conceded', [0])) if home.get('home_conceded') else 1.0
        away_avg_conceded = np.mean(away.get('away_conceded', [0])) if away.get('away_conceded') else 1.0

        # Poisson lambda
        lambda_home = (home_avg_goals + away_avg_conceded) / 2
        lambda_away = (away_avg_goals + home_avg_conceded) / 2

        # Probabilidades Poisson (simplificadas)
        max_goals = 6
        home_probs = np.array([np.exp(-lambda_home) * (lambda_home**i) / max(np.math.factorial(i), 1) for i in range(max_goals+1)])
        away_probs = np.array([np.exp(-lambda_away) * (lambda_away**i) / max(np.math.factorial(i), 1) for i in range(max_goals+1)])
        home_probs = home_probs / home_probs.sum()
        away_probs = away_probs / away_probs.sum()

        p_home_win = sum(home_probs[i] * sum(away_probs[:i]) for i in range(1, max_goals+1))
        p_draw = sum(home_probs[i] * away_probs[i] for i in range(max_goals+1))
        p_away_win = sum(away_probs[i] * sum(home_probs[:i]) for i in range(1, max_goals+1))

        # === Modelo 2: Frecuencia histórica de resultados ===
        all_home_results = home.get('home_results', [])
        all_away_results = away.get('away_results', [])

        home_win_pct = all_home_results.count('H') / max(len(all_home_results), 1)
        draw_pct_home = all_home_results.count('D') / max(len(all_home_results), 1)
        away_win_pct = all_away_results.count('A') / max(len(all_away_results), 1)
        draw_pct_away = all_away_results.count('D') / max(len(all_away_results), 1)

        # Ensemble: 50% Poisson + 50% frecuencia
        p_h = 0.5 * p_home_win + 0.25 * home_win_pct + 0.25 * (1 - away_win_pct)
        p_d = 0.5 * p_draw + 0.25 * draw_pct_home + 0.25 * draw_pct_away
        p_a = 0.5 * p_away_win + 0.25 * away_win_pct + 0.25 * (1 - home_win_pct)

        # Normalizar
        total = p_h + p_d + p_a
        p_h, p_d, p_a = p_h/total, p_d/total, p_a/total

        probs = {'H': p_h, 'D': p_d, 'A': p_a}
        predicted = max(probs, key=probs.get)
        confidence = probs[predicted]

        details = {
            'lambda_home': round(lambda_home, 2),
            'lambda_away': round(lambda_away, 2),
            'home_goals_avg': round(home_avg_goals, 2),
            'away_goals_avg': round(away_avg_goals, 2),
            'home_matches': len(home.get('home_goals', [])),
            'away_matches': len(away.get('away_goals', [])),
            'p_home': round(p_h, 3),
            'p_draw': round(p_d, 3),
            'p_away': round(p_a, 3),
        }

        return predicted, confidence, details

    def predict_match_odds_based(self, match: Match, all_matches: List[Match]) -> Tuple[str, float]:
        """
        Modelo baseline: usa el promedio de cuotas implícitas del mercado.
        Si las cuotas son eficientes, esto debería ser difícil de batir.
        """
        # Probabilidades implícitas del mercado (Bet365)
        if match.b365h and match.b365d and match.b365a:
            inv_h = 1/float(match.b365h)
            inv_d = 1/float(match.b365d)
            inv_a = 1/float(match.b365a)
            total_inv = inv_h + inv_d + inv_a
            # Quitar overround
            p_h = inv_h / total_inv
            p_d = inv_d / total_inv
            p_a = inv_a / total_inv
            predicted = max([('H', p_h), ('D', p_d), ('A', p_a)], key=lambda x: x[1])[0]
            confidence = max(p_h, p_d, p_a)
            return predicted, confidence
        return None, 0

    def backtest_league(self, league: League, options: dict) -> Dict:
        """Ejecuta LOOCV en una liga"""
        n_matches = None if options.get('full') else options.get('n_matches', 200)
        matches = self.get_matches_with_results(league, n_matches)

        if len(matches) < options.get('min_matches', 50):
            self.stdout.write(f"  {league.name}: {len(matches)} partidos (insuficiente, skip)")
            return None

        self.stdout.write(f"\n{'='*70}")
        self.stdout.write(f"  LOOCV: {league.name} — {len(matches)} partidos")
        self.stdout.write(f"{'='*70}")

        results = {
            'league': league.name,
            'n_matches': len(matches),
            'correct': 0,
            'total': 0,
            'confidences': [],
            'correct_confidences': [],
            'wrong_confidences': [],
            'by_result': {'H': {'correct': 0, 'total': 0}, 'D': {'correct': 0, 'total': 0}, 'A': {'correct': 0, 'total': 0}},
            'confusion': {'H': {'H': 0, 'D': 0, 'A': 0}, 'D': {'H': 0, 'D': 0, 'A': 0}, 'A': {'H': 0, 'D': 0, 'A': 0}},
            'odds_baseline': {'correct': 0, 'total': 0},
            'avg_confidence': 0,
            'per_match_details': [],
        }

        for i, match in enumerate(matches):
            # LOOCV: excluir este partido del training set
            stats = self.compute_team_stats(matches, exclude_match_id=match.id)

            # Predicción basada en todos los demás partidos
            predicted, confidence, details = self.predict_match(match.home_team, match.away_team, stats)
            actual = match.ftr

            results['total'] += 1
            results['confidences'].append(confidence)

            if predicted == actual:
                results['correct'] += 1
                results['correct_confidences'].append(confidence)
            else:
                results['wrong_confidences'].append(confidence)

            results['by_result'][actual]['total'] += 1
            if predicted == actual:
                results['by_result'][actual]['correct'] += 1

            results['confusion'][actual][predicted] += 1

            # Baseline odds
            odds_pred, odds_conf = self.predict_match_odds_based(match, matches)
            if odds_pred:
                results['odds_baseline']['total'] += 1
                if odds_pred == actual:
                    results['odds_baseline']['correct'] += 1

            # Guardar detalle de los primeros 10
            if i < 10:
                results['per_match_details'].append({
                    'date': str(match.date),
                    'match': f"{match.home_team} vs {match.away_team}",
                    'actual': actual,
                    'predicted': predicted,
                    'confidence': round(confidence, 3),
                    'correct': predicted == actual,
                    **details,
                })

            if (i + 1) % 50 == 0:
                acc = results['correct'] / results['total'] * 100
                self.stdout.write(f"  [{i+1}/{len(matches)}] Accuracy: {acc:.1f}%")

        # Métricas finales
        results['accuracy'] = results['correct'] / results['total'] if results['total'] > 0 else 0
        results['avg_confidence'] = np.mean(results['confidences']) if results['confidences'] else 0

        # Métricas de overfitting
        results['confidence_accuracy_gap'] = results['avg_confidence'] - results['accuracy']
        results['correct_avg_conf'] = np.mean(results['correct_confidences']) if results['correct_confidences'] else 0
        results['wrong_avg_conf'] = np.mean(results['wrong_confidences']) if results['wrong_confidences'] else 0
        results['conf_calibration_error'] = abs(results['correct_avg_conf'] - results['wrong_avg_conf'])

        # Baseline odds
        if results['odds_baseline']['total'] > 0:
            results['odds_accuracy'] = results['odds_baseline']['correct'] / results['odds_baseline']['total']

        # Imprimir resultados
        self.print_league_results(results)

        return results

    def print_league_results(self, r: Dict):
        self.stdout.write(f"\n  📊 RESULTADOS LOOCV: {r['league']}")
        self.stdout.write(f"  {'─'*50}")

        acc = r['accuracy'] * 100
        self.stdout.write(f"  ✅ Accuracy general: {acc:.1f}% ({r['correct']}/{r['total']})")

        # Por tipo de resultado
        self.stdout.write(f"\n  🎯 Accuracy por resultado real:")
        for res in ['H', 'D', 'A']:
            data = r['by_result'][res]
            if data['total'] > 0:
                pct = data['correct'] / data['total'] * 100
                label = {'H': 'Local', 'D': 'Empate', 'A': 'Visitante'}[res]
                self.stdout.write(f"     {label} ({res}): {pct:.1f}% ({data['correct']}/{data['total']})")

        # Matriz de confusión
        self.stdout.write(f"\n  🔀 Matriz de confusión (Real → Predicho):")
        self.stdout.write(f"              Pred H   Pred D   Pred A")
        for real in ['H', 'D', 'A']:
            row = r['confusion'][real]
            label = {'H': 'Real Local', 'D': 'Real Empate', 'A': 'Real Visit'}[real]
            self.stdout.write(f"     {label}:   {row['H']:7d}  {row['D']:7d}  {row['A']:7d}")

        # Diagnóstico overfitting
        self.stdout.write(f"\n  🔬 DIAGNÓSTICO OVERFITTING:")
        self.stdout.write(f"     Confianza promedio:          {r['avg_confidence']:.3f}")
        self.stdout.write(f"     Accuracy real:               {acc:.1f}%")
        self.stdout.write(f"     Gap confianza-accuracy:      {r['confidence_accuracy_gap']:.3f} {'⚠️ SOBRECONFIANZA' if r['confidence_accuracy_gap'] > 0.1 else '✅ Calibrado'}")

        conf_gap = r['correct_avg_conf'] - r['wrong_avg_conf']
        self.stdout.write(f"     Confianza en aciertos:       {r['correct_avg_conf']:.3f}")
        self.stdout.write(f"     Confianza en errores:        {r['wrong_avg_conf']:.3f}")
        self.stdout.write(f"     Gap acierto-error:           {conf_gap:.3f} {'⚠️ No discrimina bien' if conf_gap < 0.05 else '✅ Discrimina'}")

        if r['odds_baseline']['total'] > 0:
            odds_acc = r['odds_accuracy'] * 100
            self.stdout.write(f"\n  🏦 Baseline mercado (cuotas):   {odds_acc:.1f}% ({r['odds_baseline']['correct']}/{r['odds_baseline']['total']})")
            beat_odds = acc > odds_acc
            self.stdout.write(f"     ¿Bate al mercado?:           {'🏆 SÍ' if beat_odds else '❌ NO'}")

        # Juicio overfitting
        overfitting_signs = 0
        if r['confidence_accuracy_gap'] > 0.10:
            overfitting_signs += 1
        if r['correct_avg_conf'] - r['wrong_avg_conf'] < 0.05:
            overfitting_signs += 1
        if acc < 40:
            overfitting_signs += 1
        if r.get('odds_accuracy', 0) > 0 and acc <= r['odds_accuracy']:
            overfitting_signs += 1

        if overfitting_signs >= 3:
            verdict = "🔴 OVERFITTING SEVERO — El modelo no generaliza"
        elif overfitting_signs >= 2:
            verdict = "🟡 SOSPECHOSO — Posible overfitting"
        elif overfitting_signs >= 1:
            verdict = "🟢 LEVE — Aceptable pero monitorear"
        else:
            verdict = "🟢 SANO — No hay evidencia de overfitting"

        self.stdout.write(f"\n  🧾 VEREDICTO: {verdict}")

    def print_summary(self, all_results: List[Dict]):
        if not all_results:
            return

        self.stdout.write(f"\n\n{'='*70}")
        self.stdout.write(f"  📋 RESUMEN FINAL — {len(all_results)} ligas evaluadas")
        self.stdout.write(f"{'='*70}")

        self.stdout.write(f"\n  {'Liga':<30} {'Partidos':>8} {'Acc':>7} {'Gap Conf':>9} {'Mercado':>8} {'Veredicto'}")
        self.stdout.write(f"  {'─'*80}")

        for r in sorted(all_results, key=lambda x: x['accuracy'], reverse=True):
            acc = r['accuracy'] * 100
            odds_acc = r.get('odds_accuracy', 0) * 100
            gap = r['confidence_accuracy_gap']
            overfitting = '🔴' if gap > 0.15 or (odds_acc > 0 and acc <= odds_acc) else ('🟡' if gap > 0.10 else '🟢')
            self.stdout.write(
                f"  {r['league']:<30} {r['n_matches']:>8} {acc:>6.1f}% {gap:>8.3f} {odds_acc:>7.1f}%    {overfitting}"
            )

        avg_acc = np.mean([r['accuracy'] for r in all_results])
        self.stdout.write(f"\n  📊 Accuracy promedio global: {avg_acc*100:.1f}%")
        self.stdout.write(f"  📊 Baseline mercado promedio: {np.mean([r.get('odds_accuracy', 0) for r in all_results])*100:.1f}%")
