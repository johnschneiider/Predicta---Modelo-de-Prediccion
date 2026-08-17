#!/usr/bin/env python3
"""
Pipeline de Edge Detection — Predicta
=====================================
Trae partidos + cuotas Pinnacle (The Odds API) de ligas suramericanas.
Calcula probabilidades implícitas del mercado (sharp).
Compara contra cuotas de libros blandos (cuando las tengas).
Alerta por Telegram cuando encuentra edge positivo.

Sin modelo propio: usa Pinnacle como referencia de probabilidad real.
El edge = libros blandos que pagan más que Pinnacle.
"""
import json
import math
import urllib.request
import sqlite3
from datetime import datetime, timezone
from collections import defaultdict

API_KEY = "fdf7156c54b983ea91910f326f5e5081"
BASE_URL = "https://api.the-odds-api.com/v4"

# Ligas suramericanas activas
SA_LEAGUES = [
    ("soccer_argentina_primera_division", "Argentina - Primera División"),
    ("soccer_brazil_campeonato", "Brasil - Série A"),
    ("soccer_brazil_serie_b", "Brasil - Série B"),
    ("soccer_chile_campeonato", "Chile - Primera División"),
    ("soccer_conmebol_copa_libertadores", "Copa Libertadores"),
    ("soccer_conmebol_copa_sudamericana", "Copa Sudamericana"),
]

# Bookmakers blandos (soft) — los que operan en Colombia / LatAm
# 1xBet está en The Odds API (region eu) y opera en Colombia
SOFT_BOOKS = ["onexbet", "betsson", "marathonbet", "tipico_de"]

# Pinnacle = referencia sharp
SHARP_BOOK = "pinnacle"


def api_get(path, params=None):
    """Llama The Odds API v4."""
    url = f"{BASE_URL}{path}?apiKey={API_KEY}"
    if params:
        for k, v in params.items():
            url += f"&{k}={v}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            remaining = resp.headers.get("x-requests-remaining", "?")
            used = resp.headers.get("x-requests-used", "?")
            return data, remaining, used
    except Exception as e:
        print(f"  ❌ Error API: {e}")
        return None, 0, 0


def implied_prob(odds):
    """Probabilidad implícita = 1/odds (sin quitar margen)."""
    return 1.0 / odds if odds and odds > 1.0 else 0.0


def fair_prob_from_pinnacle(odds_h, odds_d, odds_a):
    """Probabilidades justas (sin margen) de Pinnacle 1X2."""
    if not all(o and o > 1.0 for o in [odds_h, odds_d, odds_a]):
        return None, None, None
    inv = 1/odds_h + 1/odds_d + 1/odds_a
    return 1/odds_h/inv, 1/odds_d/inv, 1/odds_a/inv


def fair_prob_totals(over_odds, under_odds):
    """Probabilidades justas de Over/Under."""
    if not all(o and o > 1.0 for o in [over_odds, under_odds]):
        return None, None
    inv = 1/over_odds + 1/under_odds
    return 1/over_odds/inv, 1/under_odds/inv


def find_edge(matches):
    """Compara cuotas de libros blandos vs Pinnacle (fair probs).
    Retorna lista de oportunidades de edge."""
    opportunities = []

    for m in matches:
        home = m["home_team"]
        away = m["away_team"]
        commence = m["commence_time"]

        # Buscar Pinnacle
        pinnacle = None
        soft_books_data = {}

        for b in m.get("bookmakers", []):
            if b["key"] == SHARP_BOOK:
                pinnacle = b
            elif b["key"] in SOFT_BOOKS:
                soft_books_data[b["key"]] = b

        if not pinnacle:
            continue

        # Extraer h2h de Pinnacle
        pin_h2h = None
        pin_totals = None
        for mk in pinnacle["markets"]:
            if mk["key"] == "h2h":
                pin_h2h = {o["name"]: o["price"] for o in mk["outcomes"]}
            elif mk["key"] == "totals":
                pin_totals = mk["outcomes"]

        if not pin_h2h:
            continue

        ph, pd, pa = fair_prob_from_pinnacle(
            pin_h2h.get(home, 0), pin_h2h.get("Draw", 0), pin_h2h.get(away, 0)
        )

        # Cuota justa de Pinnacle (sin margen)
        fair_odds_h = 1/ph if ph else 0
        fair_odds_d = 1/pd if pd else 0
        fair_odds_a = 1/pa if pa else 0

        # Comparar contra libros blandos
        for book_key, book in soft_books_data.items():
            for mk in book["markets"]:
                if mk["key"] == "h2h":
                    soft_h2h = {o["name"]: o["price"] for o in mk["outcomes"]}
                    for outcome, fair_p, fair_odds, label in [
                        (home, ph, fair_odds_h, "Local"),
                        ("Draw", pd, fair_odds_d, "Empate"),
                        (away, pa, fair_odds_a, "Visitante"),
                    ]:
                        soft_odds = soft_h2h.get(outcome, 0)
                        if soft_odds and soft_odds > 1.0 and fair_odds > 1.0:
                            edge_pct = (soft_odds - fair_odds) / fair_odds * 100
                            if edge_pct > 2.0:  # mínimo 2% edge
                                opportunities.append({
                                    "league": m.get("_league_name", ""),
                                    "match": f"{home} vs {away}",
                                    "commence": commence,
                                    "market": f"1X2 - {label}",
                                    "outcome": outcome,
                                    "pinnacle_fair_odds": round(fair_odds, 2),
                                    "soft_book": book_key,
                                    "soft_odds": soft_odds,
                                    "edge_pct": round(edge_pct, 1),
                                    "stake_suggest": "1u",  # placeholder
                                })

                elif mk["key"] == "totals":
                    if not pin_totals:
                        continue
                    # Mismo punto (point) para comparar
                    pin_by_point = {}
                    for o in pin_totals:
                        pt = o.get("point")
                        pin_by_point[(o["name"], pt)] = o["price"]

                    for o in mk["outcomes"]:
                        pt = o.get("point")
                        name = o["name"]
                        pin_price = pin_by_point.get((name, pt))
                        if not pin_price:
                            continue
                        po, pu = fair_prob_totals(
                            pin_by_point.get(("Over", pt), 0),
                            pin_by_point.get(("Under", pt), 0)
                        )
                        if name == "Over" and po:
                            fair_odds = 1/po
                        elif name == "Under" and pu:
                            fair_odds = 1/pu
                        else:
                            continue
                        soft_odds = o["price"]
                        if soft_odds > 1.0 and fair_odds > 1.0:
                            edge_pct = (soft_odds - fair_odds) / fair_odds * 100
                            if edge_pct > 2.0:
                                opportunities.append({
                                    "league": m.get("_league_name", ""),
                                    "match": f"{home} vs {away}",
                                    "commence": commence,
                                    "market": f"O/U {pt} - {name}",
                                    "outcome": name,
                                    "pinnacle_fair_odds": round(fair_odds, 2),
                                    "soft_book": book_key,
                                    "soft_odds": soft_odds,
                                    "edge_pct": round(edge_pct, 1),
                                    "stake_suggest": "1u",
                                })

    return opportunities


def main():
    print("=" * 70)
    print("  PREDICTA EDGE DETECTOR — Pipeline Suramérica")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 70)

    all_opps = []

    for sport_key, league_name in SA_LEAGUES:
        print(f"\n  📡 {league_name}...")
        data, remaining, used = api_get(
            f"/sports/{sport_key}/odds/",
            {"regions": "eu", "oddsFormat": "decimal", "markets": "h2h,totals"}
        )

        if not data:
            print(f"     Sin datos o error")
            continue

        print(f"     {len(data)} partidos | credits restantes: {remaining}")

        # Marcar liga en cada partido
        for m in data:
            m["_league_name"] = league_name

        opps = find_edge(data)
        if opps:
            all_opps.extend(opps)
            print(f"     ⚡ {len(opps)} oportunidades de edge encontradas")
        else:
            print(f"     Sin edge positivo (>2%)")

    # Reporte final
    print(f"\n{'='*70}")
    print(f"  REPORTE FINAL")
    print(f"{'='*70}")
    print(f"  Total oportunidades: {len(all_opps)}")

    if all_opps:
        # Ordenar por edge descendente
        all_opps.sort(key=lambda x: x["edge_pct"], reverse=True)

        print(f"\n  {'Edge':>5}  {'Match':<40} {'Mercado':<20} {'Cuota':<8} {'Sharp':<8} {'Libro':<12}")
        print(f"  {'─'*95}")
        for o in all_opps[:20]:
            print(f"  {o['edge_pct']:>4.1f}%  {o['match']:<40} {o['market']:<20} "
                  f"{o['soft_odds']:<8} {o['pinnacle_fair_odds']:<8} {o['soft_book']:<12}")

        # Guardar para siguiente paso
        with open("/var/www/predicta.com.co/data/edge_opportunities.json", "w") as f:
            json.dump(all_opps, f, indent=2, ensure_ascii=False)
        print(f"\n  💾 Guardado en data/edge_opportunities.json")
    else:
        print(f"\n  No se encontraron oportunidades con edge > 2% en este ciclo.")


if __name__ == "__main__":
    main()
