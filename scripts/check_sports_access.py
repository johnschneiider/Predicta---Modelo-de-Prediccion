#!/usr/bin/env python3
"""Verifica a qué deportes de API-Sports tiene acceso la key de predicta.

Lee la key desde el .env del proyecto (igual que hace Django), consulta el
endpoint /status de cada deporte y reporta plan, cuota y límites.
No imprime la key jamás.
"""
import os
import sys
import json
import urllib.request
import urllib.error

ENV_PATH = "/var/www/predicta.com.co/.env"

SPORTS = {
    "football": "https://v3.football.api-sports.io/status",
    "basketball": "https://v1.basketball.api-sports.io/status",
    "baseball": "https://v1.baseball.api-sports.io/status",
    "volleyball": "https://v1.volleyball.api-sports.io/status",
    "hockey": "https://v1.hockey.api-sports.io/status",
    "handball": "https://v1.handball.api-sports.io/status",
    "rugby": "https://v1.rugby.api-sports.io/status",
    "mma": "https://v1.mma.api-sports.io/status",
    "formula-1": "https://v1.formula-1.api-sports.io/status",
    "american-football": "https://v1.american-football.api-sports.io/status",
    "australian-football": "https://v1.australian-football.api-sports.io/status",
    "golf": "https://v1.golf.api-sports.io/status",
    "cycling": "https://v1.cycling.api-sports.io/status",
    "esports": "https://v1.esports.api-sports.io/status",
}


def load_key():
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line.startswith("APIFOOTBALL_KEY="):
                return line.split("=", 1)[1].strip().strip("'\"")
    raise SystemExit("APIFOOTBALL_KEY no encontrada en .env")


def check(name, url, key):
    req = urllib.request.Request(url, headers={"x-apisports-key": key})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            status = r.status
            body = json.loads(r.read().decode())
        return {"sport": name, "http": status, "ok": True, "body": body}
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode())
        except Exception:
            body = {"raw": str(e)}
        return {"sport": name, "http": e.code, "ok": False, "body": body}
    except Exception as e:
        return {"sport": name, "http": 0, "ok": False, "body": {"error": str(e)}}


def main():
    key = load_key()
    print("=== Verificación de acceso por deporte (API-Sports) ===\n")
    results = []
    for name, url in SPORTS.items():
        r = check(name, url, key)
        results.append(r)
        if r["ok"]:
            b = r["body"].get("response") or {}
            plan = b.get("plan") or "?"
            q = (b.get("requests") or {}).get("limit_day") or "?"
            print(f"[OK]      {name:<22} http={r['http']} plan={plan} cuota_diaria={q}")
        else:
            err = r["body"].get("errors") or r["body"]
            msg = err if isinstance(err, str) else json.dumps(err)[:100]
            print(f"[DENEGADO]{name:<22} http={r['http']} msg={msg}")
    accessible = [x["sport"] for x in results if x["ok"]]
    print("\n=== Resumen ===")
    print(f"Deportes con acceso: {len(accessible)}/{len(SPORTS)}")
    print(f"Lista: {', '.join(accessible) if accessible else 'ninguno'}")


if __name__ == "__main__":
    main()
