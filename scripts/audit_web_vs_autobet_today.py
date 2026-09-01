"""
AUDITORÍA (solo lectura, no cambia código): compara el veredicto del motor WEB
(/ai/predict/, pipeline legacy) contra el lado apostado hoy por auto_betting
(que usa el motor poisson_ratings ridge desde 2026-08-31).

Salida: por cada apuesta única de hoy (partido+mercado+línea+lado):
- λ web (legacy) y veredicto web para esa línea
- lado apostado y si el motor web lo contradice (PELIGRO)
"""
import sys
sys.path.insert(0, '/var/www/predicta.com.co')
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
django.setup()
import logging
logging.disable(logging.CRITICAL)

from django.utils import timezone
from auto_betting.models import AutoBet
from football_data.models import League
from ai_predictions.simple_models import SimplePredictionService, ModeloHibridoGeneral
from ai_predictions.official_prediction_model import official_prediction_model
from ai_predictions.corners_model import corners_model
from ai_predictions.shots_prediction_model import shots_prediction_model
from ai_predictions.xg_shots_model import xg_shots_model
from ai_predictions.enhanced_both_teams_score import enhanced_both_teams_score_model
from value_betting.services import compute_poisson_probabilities, poisson_over

def get_league(name):
    lg = League.objects.filter(name=name).first()
    if lg:
        return lg
    lg = League.objects.filter(name__icontains=name.split('(')[0].strip()).first()
    return lg

def web_lambda_goals(home, away, league):
    """Pipeline web para goles: 3 simples + hibrido → official."""
    svc = SimplePredictionService()
    preds = svc.get_all_simple_predictions(home, away, league, 'goals_total')
    try:
        hp = ModeloHibridoGeneral().predecir(home, away, league, 'goals_total')
        if hp and hp.get('prediction', 0) > 0:
            preds.append(hp)
    except Exception:
        pass
    if not preds:
        return None
    off = official_prediction_model.calculate_official_predictions({'goals_total': preds})
    o = off.get('goals_total')
    return float(o['prediction']) if o else None

def web_lambda_corners(home, away, league):
    """Pipeline web para corners: corners_model (40/30/15/15)."""
    try:
        r = corners_model.predecir(home, away, league, 'corners_total')
        if r:
            return float(r.get('corners_esperados_total', r.get('prediction', 0)) or 0)
    except Exception:
        pass
    return None

def web_lambda_sot(home, away, league):
    """Pipeline web para tiros a puerta: shots_prediction_model + xg_shots_model → official."""
    preds = []
    for fn in ['predict_shots_on_target_total']:
        try:
            p1 = getattr(shots_prediction_model, fn)(home, away, league)
            if p1:
                preds.append(p1)
        except Exception:
            pass
        try:
            p2 = getattr(xg_shots_model, fn)(home, away, league)
            if p2:
                preds.append(p2)
        except Exception:
            pass
    if not preds:
        return None
    off = official_prediction_model.calculate_official_predictions({'shots_on_target_total': preds})
    o = off.get('shots_on_target_total')
    return float(o['prediction']) if o else None

def web_btts(home, away, league):
    """Pipeline web para BTTS: simples + enhanced → official (promedio)."""
    svc = SimplePredictionService()
    preds = []
    try:
        preds = svc.get_all_simple_predictions(home, away, league, 'both_teams_score')
    except Exception:
        preds = []
    try:
        p = enhanced_both_teams_score_model.predict(home, away, league)
        if p is not None:
            preds.append({'model_name': 'Enhanced BTS', 'prediction': float(p), 'confidence': 0.8})
    except Exception:
        pass
    if not preds:
        return None
    off = official_prediction_model.calculate_official_predictions({'both_teams_score': preds})
    o = off.get('both_teams_score')
    return float(o['prediction']) if o else None

def veredicto(lambda_val, line):
    """Veredicto over/under del motor web para una línea (Poisson)."""
    if lambda_val is None or line is None:
        return None, None
    p_over = poisson_over(float(line), lambda_val)
    return ('OVER' if p_over > 0.5 else 'UNDER'), round(p_over * 100, 1)

# ── Apuestas únicas de hoy (partido+mercado+línea+lado) ──
bets = AutoBet.objects.filter(creado__date=timezone.localdate())
unique = {}
for b in bets:
    key = (b.home_team, b.away_team, b.liga, b.mercado, b.linea, b.seleccion)
    if key not in unique:
        unique[key] = b
print(f"Apuestas hoy: {bets.count()} (filas) | combinaciones únicas: {len(unique)}\n")

peligro = []
alineadas = []
sin_datos_web = []
for (home, away, liga, mercado, linea, sel), b in unique.items():
    lg = get_league(liga) if liga else None
    if not lg:
        sin_datos_web.append((home, away, liga, mercado, sel, 'liga no encontrada'))
        continue
    m = (mercado or '').lower()
    lam = None
    p_btts = None
    if 'goles' in m:
        lam = web_lambda_goals(home, away, lg)
    elif 'esquina' in m:
        lam = web_lambda_corners(home, away, lg)
    elif 'tiros a puerta' in m:
        lam = web_lambda_sot(home, away, lg)
    elif 'marcan' in m:
        p_btts = web_btts(home, away, lg)

    if 'marcar' in m or 'btts' in m:
        if p_btts is None:
            sin_datos_web.append((home, away, liga, mercado, sel, 'sin modelo web BTTS'))
            continue
        v_web = 'Sí' if p_btts > 0.5 else 'No'
        lado = (sel or '').strip().lower().startswith('sí') or (sel or '').strip().lower() == 'si'
        coincide = (v_web == 'Sí') == lado
        row = (f"{home} vs {away} [{liga}] BTTS | apostó={sel} cuota={b.cuota} P={b.predicta_prob}"
               f" | web: p_sí={p_btts*100:.1f}% → {v_web} | {'✔ alineada' if coincide else '✘ PELIGRO (web contradice)'}")
        (alineadas if coincide else peligro).append((row, b))
        continue

    if lam is None:
        sin_datos_web.append((home, away, liga, mercado, sel, 'sin λ web'))
        continue
    v, p = veredicto(lam, linea)
    if v is None:
        sin_datos_web.append((home, away, liga, mercado, sel, 'sin línea'))
        continue
    lado = (sel or '').strip().lower()
    lado_side = 'OVER' if lado.startswith('over') else 'UNDER'
    coincide = v == lado_side
    row = (f"{home} vs {away} [{liga}] {mercado} {sel}(línea {linea}) cuota={b.cuota} P={b.predicta_prob}"
           f" | web λ={lam:.2f} → {v} {linea} ({p}%) | {'✔ alineada' if coincide else '✘ PELIGRO (web contradice)'}")
    (alineadas if coincide else peligro).append((row, b))

print("═══ APUESTAS EN PELIGRO (motor web contradice el lado apostado) ═══")
for row, b in sorted(peligro, key=lambda x: -x[1].predicta_prob):
    n_filas = AutoBet.objects.filter(home_team=b.home_team, away_team=b.away_team,
                                     mercado=b.mercado, linea=b.linea,
                                     seleccion=b.seleccion, creado__date=timezone.localdate()).count()
    stake = sum(x.stake or 0 for x in AutoBet.objects.filter(home_team=b.home_team, away_team=b.away_team,
                                     mercado=b.mercado, linea=b.linea,
                                     seleccion=b.seleccion, creado__date=timezone.localdate()))
    print(f"  {row} | filas={n_filas} stake_total={stake/1000:.0f} COP")
print(f"\nTotal combinaciones PELIGRO: {len(peligro)}")

print("\n═══ ALINEADAS (web coincide con el lado apostado) ═══")
for row, b in alineadas:
    print(" ", row)
print(f"Total alineadas: {len(alineadas)}")

print("\n═══ SIN DATOS WEB (no se pudo calcular veredicto web) ═══")
for r in sin_datos_web:
    print(" ", r)
