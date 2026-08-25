"""
Modelos de la capa de datos API-Football.

Fuente única de estadísticas para los motores de Predicta. Sustituye al
scraping de Flashscore y a la tabla legacy `football_data.Match`.
"""

from django.db import models
from django.utils import timezone


class ApiLeague(models.Model):
    """Liga de API-Football con mapeo a BetPlay (Kambi) y Predicta."""

    TYPE_CHOICES = [("League", "Liga"), ("Cup", "Copa")]

    api_id = models.IntegerField(unique=True, verbose_name="API ID")
    name = models.CharField(max_length=200, verbose_name="Nombre API")
    country = models.CharField(max_length=100, blank=True, verbose_name="País")
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="League", verbose_name="Tipo")
    logo = models.URLField(blank=True, verbose_name="Logo")

    # Mapeo BetPlay (Kambi)
    kambi_path = models.CharField(max_length=300, blank=True, verbose_name="Path Kambi")
    kambi_group = models.CharField(max_length=200, blank=True, verbose_name="Grupo BetPlay")

    # Enlace legacy Predicta
    predicta_name = models.CharField(max_length=200, blank=True, verbose_name="Nombre Predicta")
    predicta_league_id = models.IntegerField(null=True, blank=True, verbose_name="Liga Predicta (legacy)")

    active = models.BooleanField(default=True, verbose_name="Activa")

    # Cobertura (probada contra la API)
    has_statistics = models.BooleanField(default=False, verbose_name="Tiene estadísticas")
    has_odds = models.BooleanField(default=False, verbose_name="Tiene cuotas")
    has_predictions = models.BooleanField(default=False, verbose_name="Tiene predicciones")

    seasons = models.JSONField(default=list, blank=True, verbose_name="Temporadas disponibles")
    current_season = models.IntegerField(null=True, blank=True, verbose_name="Temporada actual")

    # Prioridad: 0 = las 44 originales, 1+ = nuevas ligas (una a una)
    priority = models.IntegerField(default=1, verbose_name="Prioridad backfill")

    # Progreso de backfill
    backfill_status = models.CharField(
        max_length=20,
        default="pending",
        choices=[("pending", "Pendiente"), ("backfilling", "Cargando"), ("done", "Completado"), ("error", "Error")],
        verbose_name="Estado backfill",
    )
    last_backfill_at = models.DateTimeField(null=True, blank=True, verbose_name="Último backfill")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priority", "country", "name"]
        verbose_name = "Liga API"
        verbose_name_plural = "Ligas API"

    def __str__(self):
        return f"{self.name} ({self.api_id})"


class ApiTeam(models.Model):
    """Equipo de API-Football (IDs canónicos, únicos globalmente)."""

    api_id = models.IntegerField(unique=True, verbose_name="API ID")
    name = models.CharField(max_length=200, verbose_name="Nombre")
    country = models.CharField(max_length=100, blank=True, verbose_name="País")
    logo = models.URLField(blank=True, verbose_name="Logo")
    kambi_name = models.CharField(max_length=200, blank=True, verbose_name="Nombre BetPlay")
    normalized_name = models.CharField(max_length=200, blank=True, db_index=True, verbose_name="Nombre normalizado")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Equipo API"
        verbose_name_plural = "Equipos API"

    def __str__(self):
        return self.name


class ApiFixture(models.Model):
    """Partido de API-Football."""

    api_id = models.IntegerField(unique=True, verbose_name="API ID")
    league = models.ForeignKey(ApiLeague, on_delete=models.CASCADE, related_name="fixtures", verbose_name="Liga")
    season = models.IntegerField(verbose_name="Temporada")
    round = models.CharField(max_length=100, blank=True, verbose_name="Jornada")

    home_team = models.ForeignKey(ApiTeam, on_delete=models.CASCADE, related_name="home_fixtures", verbose_name="Local")
    away_team = models.ForeignKey(ApiTeam, on_delete=models.CASCADE, related_name="away_fixtures", verbose_name="Visitante")

    date = models.DateTimeField(db_index=True, verbose_name="Fecha/hora")
    status = models.CharField(max_length=10, db_index=True, verbose_name="Estado corto")
    status_long = models.CharField(max_length=50, blank=True, verbose_name="Estado")

    # Marcadores
    home_score = models.IntegerField(null=True, blank=True, verbose_name="Goles local")
    away_score = models.IntegerField(null=True, blank=True, verbose_name="Goles visitante")
    ht_home = models.IntegerField(null=True, blank=True, verbose_name="HT local")
    ht_away = models.IntegerField(null=True, blank=True, verbose_name="HT visitante")
    ft_home = models.IntegerField(null=True, blank=True, verbose_name="FT local")
    ft_away = models.IntegerField(null=True, blank=True, verbose_name="FT visitante")
    et_home = models.IntegerField(null=True, blank=True, verbose_name="ET local")
    et_away = models.IntegerField(null=True, blank=True, verbose_name="ET visitante")
    pen_home = models.IntegerField(null=True, blank=True, verbose_name="Pen local")
    pen_away = models.IntegerField(null=True, blank=True, verbose_name="Pen visitante")

    venue = models.CharField(max_length=200, blank=True, verbose_name="Estadio")
    referee = models.CharField(max_length=200, blank=True, verbose_name="Árbitro")

    has_statistics = models.BooleanField(default=False, verbose_name="Tiene estadísticas")
    raw_json = models.JSONField(default=dict, blank=True, verbose_name="Payload completo")

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]
        verbose_name = "Partido API"
        verbose_name_plural = "Partidos API"
        indexes = [
            models.Index(fields=["league", "season"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.home_team.name} vs {self.away_team.name} ({self.date.date()})"


class TeamFixtureStat(models.Model):
    """Estadísticas de un equipo en un partido (todas las que da la API)."""

    fixture = models.ForeignKey(ApiFixture, on_delete=models.CASCADE, related_name="stats", verbose_name="Partido")
    team = models.ForeignKey(ApiTeam, on_delete=models.CASCADE, related_name="fixture_stats", verbose_name="Equipo")

    shots_on_goal = models.IntegerField(null=True, blank=True, verbose_name="Tiros a puerta")
    shots_off_goal = models.IntegerField(null=True, blank=True, verbose_name="Tiros fuera")
    total_shots = models.IntegerField(null=True, blank=True, verbose_name="Tiros totales")
    blocked_shots = models.IntegerField(null=True, blank=True, verbose_name="Tiros bloqueados")
    shots_insidebox = models.IntegerField(null=True, blank=True, verbose_name="Tiros dentro del área")
    shots_outsidebox = models.IntegerField(null=True, blank=True, verbose_name="Tiros fuera del área")
    fouls = models.IntegerField(null=True, blank=True, verbose_name="Faltas")
    corner_kicks = models.IntegerField(null=True, blank=True, verbose_name="Córners")
    offsides = models.IntegerField(null=True, blank=True, verbose_name="Fueras de juego")
    ball_possession = models.CharField(max_length=10, blank=True, verbose_name="Posesión")
    yellow_cards = models.IntegerField(null=True, blank=True, verbose_name="Amarillas")
    red_cards = models.IntegerField(null=True, blank=True, verbose_name="Rojas")
    goalkeeper_saves = models.IntegerField(null=True, blank=True, verbose_name="Atajadas")
    total_passes = models.IntegerField(null=True, blank=True, verbose_name="Pases totales")
    passes_accurate = models.IntegerField(null=True, blank=True, verbose_name="Pases precisos")
    passes_pct = models.CharField(max_length=10, blank=True, verbose_name="Pases %")
    expected_goals = models.FloatField(null=True, blank=True, verbose_name="xG")
    goals_prevented = models.FloatField(null=True, blank=True, verbose_name="xG evitado (arquero)")

    raw_json = models.JSONField(default=dict, blank=True, verbose_name="Payload completo")

    class Meta:
        unique_together = [("fixture", "team")]
        verbose_name = "Estadística de partido"
        verbose_name_plural = "Estadísticas de partidos"
        indexes = [models.Index(fields=["fixture"])]

    def __str__(self):
        return f"{self.team.name} @ {self.fixture}"


class ApiOdds(models.Model):
    """Cuotas — ESPACIO RESERVADO. No se puebla todavía (fase futura)."""

    fixture = models.ForeignKey(ApiFixture, on_delete=models.CASCADE, related_name="odds", verbose_name="Partido")
    bookmaker = models.CharField(max_length=100, verbose_name="Casa de apuestas")
    market = models.CharField(max_length=200, verbose_name="Mercado")
    outcome = models.CharField(max_length=200, verbose_name="Selección")
    odds = models.FloatField(verbose_name="Cuota")
    line = models.FloatField(null=True, blank=True, verbose_name="Línea")
    captured_at = models.DateTimeField(default=timezone.now, verbose_name="Capturada")

    class Meta:
        verbose_name = "Cuota API"
        verbose_name_plural = "Cuotas API"
        indexes = [models.Index(fields=["fixture", "market"])]


class SyncState(models.Model):
    """Checkpoint de sincronización (reanudar tras rate-limit / tope diario)."""

    key = models.CharField(max_length=100, unique=True, verbose_name="Clave")
    league_api_id = models.IntegerField(null=True, blank=True, verbose_name="Liga (API ID)")
    season = models.IntegerField(null=True, blank=True, verbose_name="Temporada")
    phase = models.CharField(max_length=50, blank=True, verbose_name="Fase")
    cursor = models.JSONField(default=dict, blank=True, verbose_name="Cursor")
    status = models.CharField(
        max_length=20, default="idle",
        choices=[("idle", "Idle"), ("running", "Corriendo"), ("paused", "Pausado"), ("done", "Hecho"), ("error", "Error")],
        verbose_name="Estado",
    )
    error_log = models.TextField(blank=True, verbose_name="Errores")

    requests_today = models.IntegerField(default=0, verbose_name="Requests hoy")
    limit_day = models.IntegerField(default=75000, verbose_name="Límite diario")
    requests_remaining = models.IntegerField(default=75000, verbose_name="Requests restantes")
    quota_date = models.DateField(null=True, blank=True, verbose_name="Fecha de cuota")

    last_run_at = models.DateTimeField(null=True, blank=True, verbose_name="Última corrida")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Estado de sincronización"
        verbose_name_plural = "Estados de sincronización"

    def __str__(self):
        return self.key
