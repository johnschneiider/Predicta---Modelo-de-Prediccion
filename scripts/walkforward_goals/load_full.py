"""
Walk-forward GOLES O/U — PASO 1b: dataset completo (todas las filas, con flag de cuotas).

Diferencia vs load_dataset.py: conserva TODAS las filas deduplicadas (incluso sin
cuotas) para que el estado walk-forward tenga historia completa desde 1999; las filas
sin cuotas se marcan has_odds=False y solo sirven como historia de entrenamiento.

Salida: wf_goals_full.pkl
"""
import glob
import os

import pandas as pd

BASE = '/var/www/predicta.com.co/media/excel_files'
OUT = '/var/www/predicta.com.co/scripts/walkforward_goals/wf_goals_full.pkl'

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


def main():
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
    df = pd.concat(frames, ignore_index=True)
    print(f'CSV: {len(files)} archivos, {bad} ilegibles | raw rows: {len(df)}')

    for f in glob.glob(f'{BASE}/*.xlsx'):
        try:
            x = pd.read_excel(f, dtype=str)
            keep = {c: c.strip() for c in x.columns if c.strip() in USECOLS}
            if len(keep) >= 6:
                df = pd.concat([df, x[list(keep)].rename(columns=keep)], ignore_index=True)
        except Exception:
            pass

    for c in ('Div', 'Date', 'HomeTeam', 'AwayTeam'):
        df[c] = df[c].astype(str).str.strip()
    df['date'] = parse_dates(df['Date'])
    n0 = len(df)
    df = df.dropna(subset=['date', 'HomeTeam', 'AwayTeam'])
    print(f'  dropna date/teams: {n0} -> {len(df)}')
    df = df[df['Div'].str.len() > 0]
    df['date'] = df['date'].dt.normalize()

    for c in ('FTHG', 'FTAG', 'BbMx>2.5', 'BbAv>2.5', 'BbMx<2.5', 'BbAv<2.5'):
        df[c] = pd.to_numeric(df[c], errors='coerce')

    # dedup: prefer filas con resultado y cuotas
    df['prio'] = (df['FTHG'].notna() & df['FTAG'].notna()).astype(int) * 2 + \
                 (df['BbAv>2.5'].notna()).astype(int)
    df = df.sort_values('prio', ascending=False)
    n1 = len(df)
    df = df.drop_duplicates(subset=['Div', 'date', 'HomeTeam', 'AwayTeam'])
    print(f'  dedup: {n1} -> {len(df)}')

    df = df.rename(columns={
        'FTHG': 'fthg', 'FTAG': 'ftag', 'Div': 'div',
        'HomeTeam': 'home', 'AwayTeam': 'away',
        'BbAv>2.5': 'o_over', 'BbAv<2.5': 'o_under',
        'BbMx>2.5': 'o_over_max', 'BbMx<2.5': 'o_under_max',
    })
    df['has_odds'] = df['o_over'].notna() & df['o_under'].notna() & \
                     (df['o_over'] > 1.0) & (df['o_under'] > 1.0)
    df['has_goal'] = df['fthg'].notna() & df['ftag'].notna()

    df = df[['date', 'div', 'home', 'away', 'fthg', 'ftag',
             'o_over', 'o_under', 'o_over_max', 'o_under_max', 'has_odds', 'has_goal']]
    df = df.sort_values(['date', 'div']).reset_index(drop=True)
    df['season'] = df['date'].dt.year.where(df['date'].dt.month >= 7,
                                            df['date'].dt.year - 1)

    print(f'Total: {len(df)} | con resultado: {df["has_goal"].sum()} | '
          f'con cuotas: {df["has_odds"].sum()} | ambos: {(df["has_goal"] & df["has_odds"]).sum()}')
    print(f'Rango: {df["date"].min().date()} → {df["date"].max().date()}')
    print('\nPor liga:')
    for d, g in df.groupby('div'):
        print(f'  {d}: {len(g)} | con cuotas: {g["has_odds"].sum()}')

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    df.to_pickle(OUT)
    print(f'\nGuardado: {OUT}')


if __name__ == '__main__':
    main()
