"""Restaura los partidos del 31-Ago que quedaron enmascarados (fthg NULL)
desde ApiFixture + TeamFixtureStat (API-Football), sin llamadas a la API."""
import os
import sys
sys.path.insert(0, '/var/www/predicta.com.co')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
import django
django.setup()

from datetime import timedelta

from football_data.models import Match
from football_api.models import ApiFixture
from value_betting.mapping import fuzzy_match_team


def _ftr(h, a):
    if h is None or a is None:
        return None
    return 'H' if h > a else ('D' if h == a else 'A')


def main():
    masked = list(Match.objects.filter(date='2026-08-31', fthg__isnull=True))
    print(f'Filas a restaurar: {len(masked)}')

    # candidatos: fixtures del 30-Ago al 1-Sep (por diferencias de zona horaria)
    fixtures = list(ApiFixture.objects.filter(
        date__date__gte='2026-08-30', date__date__lte='2026-09-01',
    ).select_related('home_team', 'away_team'))

    restored = []
    unmatched = []
    for m in masked:
        fx = None
        for f in fixtures:
            if (fuzzy_match_team(m.home_team, [f.home_team.name], threshold=0.6)
                    and fuzzy_match_team(m.away_team, [f.away_team.name], threshold=0.6)):
                fx = f
                break
        if fx is None:
            unmatched.append(m)
            continue

        stats = {s.team_id: s for s in fx.stats.all()}
        hs = stats.get(fx.home_team_id)
        aws = stats.get(fx.away_team_id)

        m.fthg = fx.home_score
        m.ftag = fx.away_score
        m.ftr = _ftr(fx.home_score, fx.away_score)
        m.hthg = fx.ht_home
        m.htag = fx.ht_away
        m.htr = _ftr(fx.ht_home, fx.ht_away)
        m.hst = hs.shots_on_goal if hs else None
        m.ast = aws.shots_on_goal if aws else None
        m.hc = hs.corner_kicks if hs else None
        m.ac = aws.corner_kicks if aws else None
        m.save(update_fields=['fthg', 'ftag', 'ftr', 'hthg', 'htag', 'htr',
                              'hst', 'ast', 'hc', 'ac'])
        restored.append((m, fx))

    print(f'Restaurados: {len(restored)} | Sin fixture: {len(unmatched)}')
    for m in unmatched:
        print(f'   SIN FIXTURE: {m.home_team} vs {m.away_team} ({m.league.name})')
    for m, fx in restored[:8]:
        print(f'   OK: {m.home_team} vs {m.away_team} → {m.fthg}-{m.ftag} '
              f'(sot {m.hst}/{m.ast}, cor {m.hc}/{m.ac})')


if __name__ == '__main__':
    main()
