"""
Walk-forward GOLES O/U — PASO 1: construcción del dataset histórico con cuotas.

Fuente: CSVs football-data.co.uk en /var/www/predicta.com.co/media/excel_files/
  (121.732 partidos deduplicados 1999-2026, 16 ligas)
Columnas de cuotas O/U 2.5:
  BbAv>2.5 / BbAv<2.5  → media del mercado (BetBrain) — cuota "realista"
  BbMx>2.5 / BbMx<2.5  → máxima del mercado — cuota "techo"

Salida: wf_goals_dataset.pkl  (date, div, home, away, fthg, ftag, o_over, o_under,
        o_over_max, o_under_max, season, tot)
NO toca producción. Solo lectura de CSV + escritura de artefacto de análisis.
"""
import glob
import os
import sys

import pandas as pd

BASE = '/var/www/predicta.com.co/media/excel_files'
OUT = '/var/www/predicta.com.co/scripts/walkforward_goals/wf_goals_dataset.pkl'

USECOLS = ('Div', 'Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG',
           'BbMx>2.5', 'BbAv>2.5', 'BbMx<2.5', 'BbAv<2.5')


def parse_dates(s):
    s = s.astype(str).str.strip()
    for fmt in ('%d/%m/%Y', '%d/%m/%y', '%Y-%m-%d'):
        try:
            out = pd.to_datetime(s, format=fmt, errors='coerce')
            if out.notna().mean() > 0.5:
                return out
        except Exception:
            continue
    return pd.to_datetime(s, errors='coerce', dayfirst=True)


def load_csvs():
    files = sorted(glob.glob(f'{BASE}/*.csv'))
    frames, bad = [], 0
    for f in files:
        try:
            df = pd.read_csv(f, usecols=lambda c: c in USECOLS, dtype=str)
            if 'Date' not in df.columns or 'FTHG' not in df.columns:
                bad += 1
                continue
            frames.append(df)
        except Exception:
            bad += 1
    print(f'CSV: {len(files)} archivos, {bad} ilegibles, {len(frames)} ok')
    return pd.concat(frames, ignore_index=True)


def load_xlsx():
    """xlsx recientes (best effort, mismos headers en general)."""
    files = glob.glob(f'{BASE}/*.xlsx')
    frames = []
    for f in files:
        try:
            df = pd.read_excel(f, dtype=str)
            cols = {c.strip(): c for c in df.columns}
            keep = {}
            for want in USECOLS:
                for c in df.columns:
                    if c.strip() == want:
                        keep[c] = want
                        break
            if len(keep) >= 6:
                sub = df[list(keep)].rename(columns=keep)
                frames.append(sub)
        except Exception:
            pass
    if frames:
        print(f'XLSX: {len(frames)} archivos añadidos')
        return pd.concat(frames, ignore_index=True)
    return None


def main():
    df = load_csvs()
    x = load_xlsx()
    if x is not None:
        df = pd.concat([df, x], ignore_index=True)

    for c in ('Div', 'Date', 'HomeTeam', 'AwayTeam'):
        df[c] = df[c].astype(str).str.strip()
    df['date'] = parse_dates(df['Date'])

    for c in ('FTHG', 'FTAG', 'BbMx>2.5', 'BbAv>2.5', 'BbMx<2.5', 'BbAv<2.5'):
        df[c] = pd.to_numeric(df[c], errors='coerce')

    df = df.dropna(subset=['date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG'])
    df = df[df['Div'].str.len() > 0]
    df = df.drop_duplicates(subset=['Div', 'date', 'HomeTeam', 'AwayTeam'])

    df = df.rename(columns={
        'BbAv>2.5': 'o_over', 'BbAv<2.5': 'o_under',
        'BbMx>2.5': 'o_over_max', 'BbMx<2.5': 'o_under_max',
        'FTHG': 'fthg', 'FTAG': 'ftag', 'Div': 'div',
        'HomeTeam': 'home', 'AwayTeam': 'away',
    })
    df = df[['date', 'div', 'home', 'away', 'fthg', 'ftag',
             'o_over', 'o_under', 'o_over_max', 'o_under_max']]

    # temporada europea: jul→jun; año = el de la primera mitad
    df['season'] = df['date'].dt.year.where(df['date'].dt.month >= 7,
                                            df['date'].dt.year - 1)
    df['tot'] = df['fthg'] + df['ftag']

    # cuota combinada disponible (preferir media; fallback máximo)
    con_odds = df['o_over'].notna() & df['o_under'].notna()
    con_odds_max = df['o_over_max'].notna() & df['o_under_max'].notna()
    print(f'Total dedup: {len(df)}')
    print(f'  con BbAv O/U: {con_odds.sum()} ({con_odds.mean()*100:.1f}%)')
    print(f'  con BbMx O/U: {con_odds_max.sum()} ({con_odds_max.mean()*100:.1f}%)')
    print(f'  con ambos o fallback: {(con_odds | con_odds_max).sum()}')

    df = df[con_odds | con_odds_max].copy()
    print(f'Rango: {df["date"].min().date()} → {df["date"].max().date()}')
    print('\nPor liga (con cuotas):')
    for d, g in df.groupby('div'):
        print(f'  {d}: {len(g)} | {g["date"].min().date()} → {g["date"].max().date()}')
    print('\nPor temporada:')
    for s, g in df.groupby('season'):
        print(f'  {s}: {len(g)}')

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    df.to_pickle(OUT)
    print(f'\nGuardado: {OUT}')


if __name__ == '__main__':
    main()
