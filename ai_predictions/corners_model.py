"""
Modelo INDEPENDIENTE de predicción de corners — v2 con fuente dual de datos.
DataSource primario: Django ORM (Match.hc/ac - ligas europeas)
DataSource secundario: SQLite (corners_brazil.db - ligas suramericanas vía adamchoi)
"""

import logging
import sqlite3
import numpy as np
from scipy.stats import poisson
from typing import Dict, List, Tuple, Optional
from django.db.models import Avg, Count, Sum, Q
from football_data.models import Match, League

logger = logging.getLogger('ai_predictions')

# Ruta de la DB SQLite con datos de adamchoi
SQLITE_DB_PATH = "/var/www/predicta.com.co/data/corners_scraped.db"


class DualDataSource:
    """Acceso unificado a datos de corners: Django ORM + SQLite externo."""

    # Mapping de nombre de liga Django → nombre en SQLite
    LEAGUE_NAME_MAP = {
        'Serie A (Brasil)': 'Serie A',
        'Serie B (Brasil)': 'Serie B',
        'Primera A (Colombia)': 'Primera A',
        'Primera Division (Argentina)': 'Primera Division',
        'Liga MX (Mexico)': 'Liga MX',
        'US MLS (USA)': 'US MLS',
    }

    def __init__(self):
        self._sqlite_conn = None

    def _sqlite_league_name(self, django_league_name: str) -> str:
        """Convierte nombre Django a nombre usado en SQLite."""
        return self.LEAGUE_NAME_MAP.get(django_league_name, django_league_name)

    @property
    def sqlite(self) -> sqlite3.Connection:
        if self._sqlite_conn is None:
            try:
                self._sqlite_conn = sqlite3.connect(SQLITE_DB_PATH)
                self._sqlite_conn.row_factory = sqlite3.Row
            except Exception:
                self._sqlite_conn = None
        return self._sqlite_conn

    # ── Helpers ──

    def _django_home_corners(self, team: str, league_name: str) -> Tuple[float, int]:
        """Corners de un equipo como local (Django)."""
        qs = Match.objects.filter(
            league__name=league_name, home_team=team, hc__isnull=False
        )
        data = list(qs.values_list('hc', flat=True))
        if data:
            return float(np.mean(data)), len(data)
        return 0.0, 0

    def _django_away_corners(self, team: str, league_name: str) -> Tuple[float, int]:
        """Corners de un equipo como visitante (Django)."""
        qs = Match.objects.filter(
            league__name=league_name, away_team=team, ac__isnull=False
        )
        data = list(qs.values_list('ac', flat=True))
        if data:
            return float(np.mean(data)), len(data)
        return 0.0, 0

    def _sqlite_home_corners(self, team: str, league_name: str) -> Tuple[float, int]:
        """Corners de un equipo como local (SQLite)."""
        if not self.sqlite:
            return 0.0, 0
        try:
            row = self.sqlite.execute(
                "SELECT AVG(home_corners), COUNT(*) FROM corners_matches "
                "WHERE home_team = ? AND league = ?",
                (team, league_name)
            ).fetchone()
            if row and row[1] > 0:
                return float(row[0]), row[1]
        except Exception as e:
            logger.debug(f"SQLite home query failed for {team}: {e}")
        return 0.0, 0

    def _sqlite_away_corners(self, team: str, league_name: str) -> Tuple[float, int]:
        """Corners de un equipo como visitante (SQLite)."""
        if not self.sqlite:
            return 0.0, 0
        try:
            row = self.sqlite.execute(
                "SELECT AVG(away_corners), COUNT(*) FROM corners_matches "
                "WHERE away_team = ? AND league = ?",
                (team, league_name)
            ).fetchone()
            if row and row[1] > 0:
                return float(row[0]), row[1]
        except Exception as e:
            logger.debug(f"SQLite away query failed for {team}: {e}")
        return 0.0, 0

    def _sqlite_league_avg(self, league_name: str) -> Tuple[float, int]:
        """Promedio de corners por equipo en la liga desde SQLite."""
        if not self.sqlite:
            return 0.0, 0
        try:
            row = self.sqlite.execute(
                "SELECT AVG(home_corners + away_corners), COUNT(*) "
                "FROM corners_matches WHERE league = ?",
                (league_name,)
            ).fetchone()
            if row and row[1] > 0:
                return float(row[0]) / 2.0, row[1]
        except Exception as e:
            logger.debug(f"SQLite league avg failed: {e}")
        return 0.0, 0

    def _sqlite_forma5(self, team: str, league_name: str, exclude_opponent: str = None) -> Tuple[Optional[float], int]:
        """Últimos 5 partidos de corners del equipo (SQLite).
        Convierte fecha DD-MM-YYYY a YYYY-MM-DD para orden cronológico correcto.
        Si exclude_opponent, excluye el partido más reciente contra ese rival."""
        if not self.sqlite:
            return None, 0
        try:
            # Traer más partidos si vamos a excluir uno
            limit = 6 if exclude_opponent else 5
            rows = self.sqlite.execute(
                "SELECT home_corners, away_corners, home_team, away_team, date "
                "FROM corners_matches WHERE league = ? AND (home_team = ? OR away_team = ?) "
                "ORDER BY substr(date,7,4)||'-'||substr(date,4,2)||'-'||substr(date,1,2) DESC LIMIT ?",
                (league_name, team, team, limit)
            ).fetchall()
            values = []
            for r in rows:
                # Excluir el partido más reciente contra el rival
                if exclude_opponent and (r['home_team'] == exclude_opponent or r['away_team'] == exclude_opponent):
                    exclude_opponent = None  # solo excluir el primero (más reciente)
                    continue
                if r['home_team'] == team:
                    values.append(r['home_corners'])
                else:
                    values.append(r['away_corners'])
                if len(values) >= 5:
                    break
            if values:
                return float(np.mean(values)), len(values)
        except Exception as e:
            logger.debug(f"SQLite forma5 failed for {team}: {e}")
        return None, 0

    # ── API unificada ──

    def ataque_propio_local(self, home_team: str, django_league: str, sqlite_league: str = None) -> Tuple[float, int, str]:
        """Corners promedio del local en casa. Fuente: Django → SQLite."""
        if sqlite_league is None:
            sqlite_league = django_league
        avg_dj, n_dj = self._django_home_corners(home_team, django_league)
        if n_dj >= 5:
            return avg_dj, n_dj, 'predicta_db'
        avg_sq, n_sq = self._sqlite_home_corners(home_team, sqlite_league)
        if n_sq > 0:
            return avg_sq, n_sq, 'scraped_db'
        if n_dj > 0:
            return avg_dj, n_dj, 'predicta_db'
        return 5.0, 0, 'default'

    def ataque_propio_visitante(self, away_team: str, django_league: str, sqlite_league: str = None) -> Tuple[float, int, str]:
        """Corners promedio del visitante fuera."""
        if sqlite_league is None:
            sqlite_league = django_league
        avg_dj, n_dj = self._django_away_corners(away_team, django_league)
        if n_dj >= 5:
            return avg_dj, n_dj, 'predicta_db'
        avg_sq, n_sq = self._sqlite_away_corners(away_team, sqlite_league)
        if n_sq > 0:
            return avg_sq, n_sq, 'scraped_db'
        if n_dj > 0:
            return avg_dj, n_dj, 'predicta_db'
        return 4.5, 0, 'default'

    def defensa_rival_para_local(self, away_team: str, django_league: str, sqlite_league: str = None) -> Tuple[float, int, str]:
        """Corners que recibe el visitante (promedio de corners_local contra él)."""
        if sqlite_league is None:
            sqlite_league = django_league
        dj_qs = Match.objects.filter(
            league__name=django_league, away_team=away_team, hc__isnull=False
        )
        dj_data = list(dj_qs.values_list('hc', flat=True))
        if len(dj_data) >= 5:
            return float(np.mean(dj_data)), len(dj_data), 'predicta_db'
        if self.sqlite:
            try:
                row = self.sqlite.execute(
                    "SELECT AVG(home_corners), COUNT(*) FROM corners_matches "
                    "WHERE away_team = ? AND league = ?",
                    (away_team, sqlite_league)
                ).fetchone()
                if row and row[1] > 0:
                    return float(row[0]), row[1], 'scraped_db'
            except:
                pass
        if dj_data:
            return float(np.mean(dj_data)), len(dj_data), 'predicta_db'
        return 5.0, 0, 'default'

    def defensa_rival_para_visitante(self, home_team: str, django_league: str, sqlite_league: str = None) -> Tuple[float, int, str]:
        """Corners que recibe el local (promedio de corners_visitante contra él)."""
        dj_qs = Match.objects.filter(
            league__name=django_league, home_team=home_team, ac__isnull=False
        )
        dj_data = list(dj_qs.values_list('ac', flat=True))
        if len(dj_data) >= 5:
            return float(np.mean(dj_data)), len(dj_data), 'predicta_db'
        if self.sqlite:
            try:
                row = self.sqlite.execute(
                    "SELECT AVG(away_corners), COUNT(*) FROM corners_matches "
                    "WHERE home_team = ? AND league = ?",
                    (home_team, sqlite_league)
                ).fetchone()
                if row and row[1] > 0:
                    return float(row[0]), row[1], 'scraped_db'
            except:
                pass
        if dj_data:
            return float(np.mean(dj_data)), len(dj_data), 'predicta_db'
        return 4.5, 0, 'default'

    def forma5(self, team: str, django_league: str, sqlite_league: str = None, exclude_opponent: str = None) -> Tuple[Optional[float], int, str]:
        """Últimos 5 partidos de corners del equipo."""
        if sqlite_league is None:
            sqlite_league = django_league
        # Django primero
        qs = Match.objects.filter(
            league__name=django_league, hc__isnull=False, ac__isnull=False
        ).filter(
            Q(home_team=team) | Q(away_team=team)
        ).order_by('-date')[:5]
        values = []
        for m in qs:
            if m.home_team == team:
                values.append(m.hc)
            else:
                values.append(m.ac)
        if len(values) >= 3:
            return float(np.mean(values)), len(values), 'predicta_db'

        # SQLite fallback (con exclusión del rival más reciente si aplica)
        avg_sq, n_sq = self._sqlite_forma5(team, sqlite_league, exclude_opponent)
        if avg_sq is not None:
            return avg_sq, n_sq, 'scraped_db'

        if values:
            return float(np.mean(values)), len(values), 'predicta_db'
        return None, 0, 'default'

    def liga_promedio(self, django_league: str, sqlite_league: str = None) -> Tuple[float, int, str]:
        """Promedio de corners por equipo en la liga."""
        # Django
        agg = Match.objects.filter(
            league__name=django_league, hc__isnull=False, ac__isnull=False
        ).aggregate(
            total_hc=Sum('hc'), total_ac=Sum('ac'), count=Count('id')
        )
        if agg['count'] and agg['count'] > 0:
            avg = (agg['total_hc'] + agg['total_ac']) / (2 * agg['count'])
            return float(avg), agg['count'], 'predicta_db'

        # SQLite fallback
        avg_sq, n_sq = self._sqlite_league_avg(sqlite_league)
        if n_sq > 0:
            return avg_sq, n_sq, 'scraped_db'

        return 5.0, 0, 'default'


# Instancia global compartida
data_source = DualDataSource()


class CornersModel:
    """Modelo independiente de predicción de corners con fórmula dedicada y fuente dual."""

    W_ATAQUE = 0.40
    W_DEFENSA = 0.30
    W_FORMA = 0.15
    W_LIGA = 0.15
    OVER_THRESHOLDS = [8, 10, 12, 15, 20]
    MIN_MATCHES_WARN = 5

    def __init__(self):
        self.ds = data_source

    def _corners_esperados(self, ataque_propio, defensa_rival, forma5, liga_prom) -> float:
        return (
            ataque_propio * self.W_ATAQUE
            + defensa_rival * self.W_DEFENSA
            + forma5 * self.W_FORMA
            + liga_prom * self.W_LIGA
        )

    def _poisson_probs(self, lam: float) -> Dict:
        results = {}
        for linea in np.arange(5.5, 18.6, 1.0):
            k = int(np.floor(linea))
            p_over = float(1.0 - poisson.cdf(k, lam))
            cuota_over = 1.0 / p_over if p_over > 0.0001 else float('inf')
            p_under = 1.0 - p_over
            cuota_under = 1.0 / p_under if p_under > 0.0001 else float('inf')
            results[f'line_{linea}'] = {
                'line': float(linea), 'p_over': p_over, 'cuota_over': cuota_over,
                'p_under': p_under, 'cuota_under': cuota_under,
            }
        return results

    def _monte_carlo(self, lam: float, n_sims: int = 100000) -> Dict:
        np.random.seed(42)
        sims = np.random.poisson(lam, n_sims)
        concordance = {}
        for linea in np.arange(5.5, 18.6, 1.0):
            k = int(np.floor(linea))
            p_over_a = float(1.0 - poisson.cdf(k, lam))
            mc_over = float((sims > k).mean())
            diff = abs(mc_over - p_over_a)
            nivel = 'MUY ALTA' if diff <= 0.02 else ('ALTA' if diff <= 0.05 else ('MEDIA' if diff <= 0.10 else 'BAJA'))
            concordance[f'line_{linea}'] = {'mc_over': mc_over, 'poiss_over': p_over_a, 'diff': diff, 'concordancia': nivel}
        return {'mean_sim': float(sims.mean()), 'std_sim': float(sims.std()), 'concordance': concordance}

    def predecir(self, home_team: str, away_team: str, league: League,
                 prediction_type: str) -> Dict:
        logger.info(f"[CORNERS] Calculando {prediction_type}: {home_team} vs {away_team} ({league.name})")

        league_name = league.name
        sqlite_league = self.ds._sqlite_league_name(league_name)

        # ── PASO 1: Datos de fuente dual ──
        ataque_home, n_ataque_home, src_ah = self.ds.ataque_propio_local(home_team, league_name, sqlite_league)
        ataque_away, n_ataque_away, src_aa = self.ds.ataque_propio_visitante(away_team, league_name, sqlite_league)
        defensa_para_local, n_def_local, src_dl = self.ds.defensa_rival_para_local(away_team, league_name, sqlite_league)
        defensa_para_visitante, n_def_visit, src_dv = self.ds.defensa_rival_para_visitante(home_team, league_name, sqlite_league)
        forma_home, n_forma_home, src_fh = self.ds.forma5(home_team, league_name, sqlite_league, away_team)
        forma_away, n_forma_away, src_fa = self.ds.forma5(away_team, league_name, sqlite_league, home_team)
        liga_prom, n_liga, src_lp = self.ds.liga_promedio(league_name, sqlite_league)

        if forma_home is None:
            forma_home = ataque_home
        if forma_away is None:
            forma_away = ataque_away

        sources_used = set([src_ah, src_aa, src_dl, src_dv, src_fh, src_fa, src_lp])

        # ── PASO 2+3 ──
        ce_local = self._corners_esperados(ataque_home, defensa_para_local, forma_home, liga_prom)
        ce_visitante = self._corners_esperados(ataque_away, defensa_para_visitante, forma_away, liga_prom)
        ce_total = ce_local + ce_visitante

        if prediction_type == 'corners_total':
            prediction = ce_total
        elif prediction_type == 'corners_home':
            prediction = ce_local
        elif prediction_type == 'corners_away':
            prediction = ce_visitante
        else:
            prediction = ce_total

        probabilities = {}
        for t in self.OVER_THRESHOLDS:
            probabilities[f'over_{t}'] = float(1.0 - poisson.cdf(t, ce_total))

        total_data = n_ataque_home + n_ataque_away
        confidence = min(0.90, max(0.35, total_data / 30))

        warnings = []
        for name, n in [
            ('ataque_local', n_ataque_home), ('ataque_visitante', n_ataque_away),
            ('defensa_local', n_def_local), ('defensa_visitante', n_def_visit),
            ('forma_local', n_forma_home), ('forma_visitante', n_forma_away),
        ]:
            if n < self.MIN_MATCHES_WARN:
                warnings.append(f'{name}: solo {n} partidos')

        logger.info(f"[CORNERS] {prediction_type}: {prediction:.2f} "
                     f"(local={ce_local:.2f}, visit={ce_visitante:.2f}, total={ce_total:.2f}) "
                     f"fuentes={sources_used}")

        return {
            'model_name': 'Corners Avanzado (40/30/15/15)',
            'prediction': round(prediction, 2),
            'confidence': round(confidence, 4),
            'probabilities': probabilities,
            'total_matches': total_data,
            'corners_esperados_local': round(ce_local, 2),
            'corners_esperados_visitante': round(ce_visitante, 2),
            'corners_esperados_total': round(ce_total, 2),
            'insumos': {
                'ataque_propio_local': {'valor': round(ataque_home, 2), 'partidos': n_ataque_home, 'fuente': src_ah},
                'ataque_propio_visitante': {'valor': round(ataque_away, 2), 'partidos': n_ataque_away, 'fuente': src_aa},
                'defensa_rival_para_local': {'valor': round(defensa_para_local, 2), 'partidos': n_def_local, 'fuente': src_dl},
                'defensa_rival_para_visitante': {'valor': round(defensa_para_visitante, 2), 'partidos': n_def_visit, 'fuente': src_dv},
                'forma5_local': {'valor': round(forma_home, 2), 'partidos': n_forma_home, 'fuente': src_fh},
                'forma5_visitante': {'valor': round(forma_away, 2), 'partidos': n_forma_away, 'fuente': src_fa},
                'liga_promedio': {'valor': round(liga_prom, 4), 'partidos': n_liga, 'fuente': src_lp},
            },
            'pesos': {'ataque': self.W_ATAQUE, 'defensa': self.W_DEFENSA, 'forma': self.W_FORMA, 'liga': self.W_LIGA},
            'data_sources': sorted(sources_used),
            'poisson_lines': self._poisson_probs(ce_total),
            'monte_carlo': self._monte_carlo(ce_total),
            'warnings': warnings,
        }

    def predecir_todos(self, home_team: str, away_team: str, league: League) -> List[Dict]:
        results = []
        for pt in ['corners_total', 'corners_home', 'corners_away']:
            results.append(self.predecir(home_team, away_team, league, pt))
        return results


corners_model = CornersModel()
