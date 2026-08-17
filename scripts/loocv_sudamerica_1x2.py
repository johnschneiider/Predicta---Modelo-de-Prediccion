"""
LOOCV para ligas suramericanas con datos scrapeados de Flashscore (Agosto 2026).
Analiza overfitting en predicciones de resultado 1X2.
"""
import numpy as np
from collections import defaultdict
import math

# === DATOS SCRAPEADOS DE FLASHSCORE (11-12 Agosto 2026) ===

COLOMBIA = [
    # Round 4 (Clausura 2026)
    ("2026-08-10", "America De Cali", "Atl. Nacional", 1, 0),
    ("2026-08-09", "Jaguares de Cordoba", "Once Caldas", 1, 1),
    ("2026-08-09", "Alianza", "Bucaramanga", 2, 3),
    ("2026-08-09", "Dep. Pasto", "Dep. Cali", 0, 2),
    ("2026-08-08", "Deportes Tolima", "Inter Bogota", 2, 1),
    ("2026-08-08", "Fortaleza", "Cucuta", 2, 0),
    ("2026-08-08", "Santa Fe", "Chico", 2, 0),
    # Round 3
    ("2026-08-06", "Once Caldas", "America De Cali", 0, 1),
    ("2026-08-05", "Inter Bogota", "Jaguares de Cordoba", 1, 0),
    ("2026-08-05", "Millonarios", "Dep. Pasto", 2, 0),
    ("2026-08-04", "Deportes Tolima", "Ind. Medellin", 2, 3),
    ("2026-08-04", "Llaneros", "Fortaleza", 3, 1),
    ("2026-08-04", "Bucaramanga", "Cucuta", 1, 1),
    # Round 2
    ("2026-08-03", "Santa Fe", "Once Caldas", 2, 2),
    ("2026-08-02", "America De Cali", "Chico", 7, 0),
    ("2026-08-02", "Jaguares de Cordoba", "Atl. Nacional", 0, 3),
    ("2026-08-02", "Junior", "Millonarios", 0, 1),
    ("2026-08-01", "Ind. Medellin", "Dep. Cali", 1, 0),
    ("2026-08-01", "Alianza", "Deportes Tolima", 1, 2),
    ("2026-08-01", "Dep. Pasto", "Aguilas", 1, 2),
    ("2026-08-01", "Fortaleza", "Pereira", 0, 0),
    # Round 1
    ("2026-07-31", "Bucaramanga", "Llaneros", 1, 1),
    ("2026-07-27", "Once Caldas", "Cucuta", 5, 1),
    ("2026-07-26", "Alianza", "Fortaleza", 1, 1),
    ("2026-07-26", "Aguilas", "Santa Fe", 2, 1),
    ("2026-07-26", "Inter Bogota", "America De Cali", 0, 2),
    ("2026-07-26", "Deportes Tolima", "Junior", 2, 1),
    ("2026-07-25", "Millonarios", "Bucaramanga", 0, 1),
    ("2026-07-25", "Ind. Medellin", "Dep. Pasto", 3, 2),
    ("2026-07-25", "Dep. Cali", "Jaguares de Cordoba", 2, 0),
    ("2026-07-24", "Llaneros", "Pereira", 1, 0),
    # Round 19 (Apertura)
    ("2026-05-03", "America De Cali", "Pereira", 1, 0),
    ("2026-05-03", "Junior", "Dep. Pasto", 4, 3),
    ("2026-05-03", "Alianza", "Millonarios", 2, 2),
    ("2026-05-03", "Deportes Tolima", "Dep. Cali", 1, 1),
    ("2026-05-03", "Fortaleza", "Bucaramanga", 2, 1),
    ("2026-05-03", "Ind. Medellin", "Aguilas", 1, 2),
    ("2026-05-03", "Santa Fe", "Inter Bogota", 3, 1),
    ("2026-05-02", "Jaguares de Cordoba", "Cucuta", 2, 0),
    ("2026-05-02", "Chico", "Llaneros", 3, 0),
    ("2026-05-01", "Once Caldas", "Atl. Nacional", 1, 0),
]

BRASIL = [
    # Round 22
    ("2026-08-09", "Flamengo RJ", "Vitoria", 2, 0),
    ("2026-08-09", "Bragantino", "Corinthians", 0, 2),
    ("2026-08-09", "Santos", "Athletico-PR", 0, 2),
    ("2026-08-09", "Bahia", "Vasco", 0, 0),
    ("2026-08-09", "Palmeiras", "Internacional", 0, 0),
    ("2026-08-09", "Cruzeiro", "Mirassol", 3, 1),
    ("2026-08-09", "Botafogo RJ", "Fluminense", 1, 1),
    ("2026-08-08", "Coritiba", "Chapecoense-SC", 2, 1),
    ("2026-08-08", "Remo", "Atletico-MG", 2, 2),
    ("2026-08-08", "Gremio", "Sao Paulo", 2, 1),
    # Round 21
    ("2026-07-31", "Coritiba", "Cruzeiro", 0, 1),
    ("2026-07-30", "Corinthians", "Athletico-PR", 0, 0),
    ("2026-07-30", "Fluminense", "Bahia", 0, 0),
    ("2026-07-30", "Vitoria", "Palmeiras", 0, 4),
    ("2026-07-29", "Internacional", "Flamengo RJ", 1, 1),
    ("2026-07-29", "Mirassol", "Remo", 2, 1),
    # Round 20
    ("2026-07-26", "Palmeiras", "Atletico-MG", 1, 2),
    ("2026-07-26", "Remo", "Vitoria", 2, 0),
    ("2026-07-26", "Bragantino", "Coritiba", 0, 0),
    ("2026-07-26", "Flamengo RJ", "Sao Paulo", 1, 1),
    ("2026-07-26", "Gremio", "Fluminense", 1, 1),
    ("2026-07-26", "Bahia", "Corinthians", 1, 1),
    ("2026-07-26", "Cruzeiro", "Botafogo RJ", 0, 1),
    ("2026-07-25", "Vasco", "Mirassol", 1, 1),
    ("2026-07-25", "Athletico-PR", "Internacional", 2, 0),
    ("2026-07-25", "Santos", "Chapecoense-SC", 2, 2),
    # Round 19
    ("2026-07-23", "Botafogo RJ", "Vitoria", 0, 0),
    ("2026-07-23", "Corinthians", "Remo", 3, 0),
    ("2026-07-23", "Chapecoense-SC", "Flamengo RJ", 0, 4),
    ("2026-07-23", "Internacional", "Cruzeiro", 1, 2),
    ("2026-07-23", "Sao Paulo", "Athletico-PR", 1, 2),
    ("2026-07-22", "Coritiba", "Palmeiras", 1, 3),
    ("2026-07-21", "Atletico-MG", "Bahia", 1, 1),
    # Round 18 + prior
    ("2026-07-17", "Fluminense", "Bragantino", 1, 1),
    ("2026-07-17", "Mirassol", "Gremio", 2, 1),
    ("2026-07-17", "Bahia", "Chapecoense-SC", 2, 0),
    ("2026-07-16", "Botafogo RJ", "Santos", 2, 1),
    ("2026-07-16", "Vitoria", "Vasco", 1, 0),
    # Round 17 (May 30)
    ("2026-05-31", "Cruzeiro", "Fluminense", 1, 1),
    ("2026-05-31", "Remo", "Sao Paulo", 1, 0),
    ("2026-05-31", "Palmeiras", "Chapecoense-SC", 1, 0),
    ("2026-05-31", "Vasco", "Atletico-MG", 0, 1),
    ("2026-05-31", "Bragantino", "Internacional", 3, 1),
    ("2026-05-30", "Santos", "Vitoria", 3, 1),
    ("2026-05-30", "Bahia", "Botafogo RJ", 2, 1),
    ("2026-05-30", "Gremio", "Corinthians", 1, 3),
    ("2026-05-30", "Athletico-PR", "Mirassol", 1, 0),
    ("2026-05-30", "Flamengo RJ", "Coritiba", 3, 0),
    # Round 16-15
    ("2026-05-25", "Coritiba", "Bahia", 3, 2),
    ("2026-05-24", "Vasco", "Bragantino", 0, 3),
    ("2026-05-24", "Corinthians", "Atletico-MG", 1, 0),
    ("2026-05-24", "Cruzeiro", "Chapecoense-SC", 2, 1),
    ("2026-05-24", "Remo", "Athletico-PR", 1, 2),
    ("2026-05-24", "Flamengo RJ", "Palmeiras", 0, 3),
    ("2026-05-23", "Gremio", "Santos", 3, 2),
    ("2026-05-23", "Mirassol", "Fluminense", 1, 0),
    ("2026-05-23", "Sao Paulo", "Botafogo RJ", 1, 1),
    ("2026-05-23", "Vitoria", "Internacional", 2, 0),
]

ARGENTINA = [
    # Round 4 (Clausura 2026)
    ("2026-08-11", "Union de Santa Fe", "Central Cordoba", 1, 2),
    ("2026-08-10", "Banfield", "Belgrano", 0, 2),
    ("2026-08-09", "Argentinos Jrs", "Racing Club", 2, 1),
    ("2026-08-09", "Defensa y Justicia", "Newells Old Boys", 2, 1),
    ("2026-08-09", "Gimnasia L.P.", "Barracas Central", 2, 0),
    ("2026-08-09", "San Lorenzo", "Huracan", 0, 2),
    ("2026-08-09", "Independiente", "Platense", 0, 1),
    ("2026-08-09", "Instituto", "Gimnasia Mendoza", 1, 0),
    ("2026-08-08", "Boca Juniors", "Velez Sarsfield", 1, 1),
    ("2026-08-08", "Tigre", "River Plate", 1, 0),
    ("2026-08-08", "Atl. Tucuman", "Sarmiento Junin", 1, 2),
    ("2026-08-08", "Dep. Riestra", "Estudiantes L.P.", 2, 0),
    ("2026-08-08", "Ind. Rivadavia", "Estudiantes Rio Cuarto", 2, 1),
    # Round 2-3
    ("2026-08-07", "Rosario Central", "Aldosivi", 2, 1),
    ("2026-08-06", "Union de Santa Fe", "Lanus", 2, 1),
    ("2026-08-06", "Tigre", "Belgrano", 0, 0),
    ("2026-08-05", "Boca Juniors", "Estudiantes L.P.", 1, 0),
    ("2026-08-04", "Central Cordoba", "San Lorenzo", 1, 0),
    ("2026-08-04", "Huracan", "Atl. Tucuman", 0, 0),
    ("2026-08-03", "Platense", "Talleres Cordoba", 0, 4),
    ("2026-08-03", "Velez Sarsfield", "Independiente", 1, 0),
    ("2026-08-03", "Sarmiento Junin", "Ind. Rivadavia", 2, 1),
    ("2026-08-03", "Lanus", "Instituto", 0, 1),
    ("2026-08-02", "River Plate", "Rosario Central", 0, 1),
    ("2026-08-02", "Newells Old Boys", "Boca Juniors", 2, 2),
    ("2026-08-02", "Aldosivi", "Gimnasia L.P.", 1, 2),
    ("2026-08-02", "Dep. Riestra", "Barracas Central", 0, 1),
    ("2026-08-01", "Racing Club", "Tigre", 1, 3),
    ("2026-08-01", "Belgrano", "Argentinos Jrs", 0, 1),
    ("2026-08-01", "Estudiantes L.P.", "Defensa y Justicia", 3, 0),
    ("2026-08-01", "Estudiantes Rio Cuarto", "Banfield", 0, 0),
    ("2026-08-01", "Gimnasia Mendoza", "Union de Santa Fe", 2, 0),
    # Round 2
    ("2026-07-31", "Central Cordoba", "Atl. Tucuman", 0, 2),
    ("2026-07-31", "Independiente", "Newells Old Boys", 1, 0),
    ("2026-07-30", "Ind. Rivadavia", "Huracan", 2, 1),
    ("2026-07-30", "Talleres Cordoba", "Velez Sarsfield", 1, 3),
    ("2026-07-30", "Instituto", "Platense", 2, 1),
    # Round 1
    ("2026-07-29", "Gimnasia L.P.", "River Plate", 1, 0),
    ("2026-07-29", "Defensa y Justicia", "Dep. Riestra", 2, 1),
    ("2026-07-29", "Barracas Central", "Aldosivi", 1, 0),
    ("2026-07-29", "Argentinos Jrs", "Estudiantes Rio Cuarto", 3, 0),
    ("2026-07-29", "Rosario Central", "Racing Club", 0, 0),
    ("2026-07-28", "Banfield", "Sarmiento Junin", 3, 2),
    ("2026-07-28", "San Lorenzo", "Gimnasia Mendoza", 1, 0),
]


def ftr(hg, ag):
    if hg > ag: return 'H'
    elif hg == ag: return 'D'
    else: return 'A'


def loocv_league(name, matches):
    """LOOCV para predicción 1X2 en una liga"""
    n = len(matches)
    correct = 0
    by_result = {'H': [0,0], 'D': [0,0], 'A': [0,0]}
    confusion = {'H': {'H':0,'D':0,'A':0}, 'D': {'H':0,'D':0,'A':0}, 'A': {'H':0,'D':0,'A':0}}

    for i in range(n):
        date, ht, at, hg, ag = matches[i]
        actual = ftr(hg, ag)

        # LOOCV: excluir este partido
        train = [m for j, m in enumerate(matches) if j != i]

        # Stats solo con training
        teams = defaultdict(lambda: {'hg':[], 'ag':[], 'results':[]})
        for _, h, a, hhg, aag in train:
            teams[h]['hg'].append(hhg)
            teams[a]['ag'].append(aag)
            teams[h]['results'].append(ftr(hhg, aag))
            teams[a]['results'].append(ftr(hhg, aag))

        ht_data = teams.get(ht, {'hg':[1.0], 'results':['H']})
        at_data = teams.get(at, {'ag':[1.0], 'results':['A']})

        # Poisson lambda
        home_avg = np.mean(ht_data['hg']) if ht_data['hg'] else 1.0
        away_avg = np.mean(at_data['ag']) if at_data['ag'] else 1.0

        lambda_h = (home_avg + away_avg * 0.8) / 2  # home advantage
        lambda_a = (away_avg + home_avg * 0.6) / 2

        # Poisson probabilities
        mg = 8
        hp = np.array([max(np.exp(-lambda_h) * lambda_h**k / max(math.factorial(k) if hasattr(np, "math") else __import__("math").factorial(k), 1), 1e-10) for k in range(mg)])
        ap = np.array([max(np.exp(-lambda_a) * lambda_a**k / max(math.factorial(k) if hasattr(np, "math") else __import__("math").factorial(k), 1), 1e-10) for k in range(mg)])
        hp /= hp.sum(); ap /= ap.sum()

        p_h = sum(hp[i] * sum(ap[:i]) for i in range(1, mg))
        p_d = sum(hp[i] * ap[i] for i in range(mg))
        p_a = sum(ap[i] * sum(hp[:i]) for i in range(1, mg))

        # Frequency adjustment
        hr = ht_data['results']
        ar = at_data['results']
        freq_h = hr.count('H')/max(len(hr),1)
        freq_d = (hr.count('D') + ar.count('D'))/(max(len(hr),1)+max(len(ar),1))
        freq_a = ar.count('A')/max(len(ar),1)

        # Ensemble
        p_h = 0.6*p_h + 0.2*freq_h + 0.2*(1-freq_a)
        p_d = 0.6*p_d + 0.2*freq_d + 0.1*(hr.count('D')/max(len(hr),1)) + 0.1*(ar.count('D')/max(len(ar),1))
        p_a = 0.6*p_a + 0.2*freq_a + 0.2*(1-freq_h)

        total = p_h + p_d + p_a
        p_h, p_d, p_a = p_h/total, p_d/total, p_a/total

        pred = max([('H', p_h), ('D', p_d), ('A', p_a)], key=lambda x: x[1])[0]

        if pred == actual:
            correct += 1
        by_result[actual][0] += 1
        if pred == actual:
            by_result[actual][1] += 1
        confusion[actual][pred] += 1

    acc = correct / n * 100
    print(f"\n{'='*60}")
    print(f"  LOOCV 1X2: {name} — {n} partidos")
    print(f"{'='*60}")
    print(f"  ✅ Accuracy: {acc:.1f}% ({correct}/{n})")
    print(f"\n  🎯 Por resultado real:")
    for r, label in [('H','Local'), ('D','Empate'), ('A','Visitante')]:
        t, c = by_result[r]
        if t > 0:
            print(f"     {label} ({r}): {c/t*100:.1f}% ({c}/{t})")

    print(f"\n  🔀 Confusión:")
    print(f"              Pred H   Pred D   Pred A")
    for r, label in [('H','Real Local'), ('D','Real Empate'), ('A','Real Visit')]:
        row = confusion[r]
        print(f"     {label}:   {row['H']:7d}  {row['D']:7d}  {row['A']:7d}")

    # Distribución real
    total = sum(by_result[r][0] for r in ['H','D','A'])
    print(f"\n  📊 Distribución real: H={by_result['H'][0]/total*100:.0f}% D={by_result['D'][0]/total*100:.0f}% A={by_result['A'][0]/total*100:.0f}%")

    return {'name': name, 'n': n, 'accuracy': acc, 'by_result': by_result, 'confusion': confusion}


if __name__ == '__main__':
    results = []
    for name, data in [("Colombia - Primera A", COLOMBIA), ("Brasil - Serie A", BRASIL), ("Argentina - Liga Profesional", ARGENTINA)]:
        r = loocv_league(name, data)
        results.append(r)

    print(f"\n\n{'='*60}")
    print(f"  📋 RESUMEN FINAL SUDAMÉRICA — LOOCV 1X2")
    print(f"{'='*60}")
    print(f"  {'Liga':<30} {'Partidos':>8} {'Acc':>7} {'H':>6} {'D':>6} {'A':>6}")
    print(f"  {'─'*65}")
    total_correct = 0
    total_n = 0
    for r in sorted(results, key=lambda x: x['accuracy'], reverse=True):
        h_acc = r['by_result']['H'][1]/max(r['by_result']['H'][0],1)*100
        d_acc = r['by_result']['D'][1]/max(r['by_result']['D'][0],1)*100
        a_acc = r['by_result']['A'][1]/max(r['by_result']['A'][0],1)*100
        print(f"  {r['name']:<30} {r['n']:>8} {r['accuracy']:>6.1f}% {h_acc:>5.0f}% {d_acc:>5.0f}% {a_acc:>5.0f}%")
        total_correct += r['accuracy'] * r['n'] / 100
        total_n += r['n']

    print(f"\n  📊 Accuracy promedio Suramérica: {total_correct/total_n*100:.1f}%")
    print(f"  📊 Total partidos analizados: {total_n}")
