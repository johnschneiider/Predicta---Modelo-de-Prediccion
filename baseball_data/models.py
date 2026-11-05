"""
Modelos para datos de MLB (béisbol) usando API-Sports baseball.
"""
from django.db import models


class BaseballTeam(models.Model):
    api_id = models.IntegerField(unique=True, verbose_name="API ID")
    name = models.CharField(max_length=100, verbose_name="Nombre")
    code = models.CharField(max_length=10, blank=True, verbose_name="Abreviatura")
    logo = models.URLField(blank=True, verbose_name="Logo")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Equipo MLB"
        verbose_name_plural = "Equipos MLB"
        ordering = ['name']

    def __str__(self):
        return self.name


class BaseballGame(models.Model):
    api_id = models.IntegerField(unique=True, verbose_name="API Game ID")
    season = models.IntegerField(verbose_name="Temporada")
    date = models.DateTimeField(verbose_name="Fecha (UTC)")
    status = models.CharField(max_length=40, blank=True, verbose_name="Estado")

    home_team = models.ForeignKey(
        BaseballTeam, on_delete=models.CASCADE, related_name='home_games',
        verbose_name="Equipo Local")
    away_team = models.ForeignKey(
        BaseballTeam, on_delete=models.CASCADE, related_name='away_games',
        verbose_name="Equipo Visitante")

    home_runs = models.IntegerField(null=True, blank=True, verbose_name="Carreras Local")
    away_runs = models.IntegerField(null=True, blank=True, verbose_name="Carreras Visitante")
    home_hits = models.IntegerField(null=True, blank=True, verbose_name="Hits Local")
    away_hits = models.IntegerField(null=True, blank=True, verbose_name="Hits Visitante")
    home_errors = models.IntegerField(null=True, blank=True, verbose_name="Errores Local")
    away_errors = models.IntegerField(null=True, blank=True, verbose_name="Errores Visitante")
    innings_home = models.JSONField(default=dict, blank=True, verbose_name="Carreras por entrada (Local)")
    innings_away = models.JSONField(default=dict, blank=True, verbose_name="Carreras por entrada (Visitante)")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Partido MLB"
        verbose_name_plural = "Partidos MLB"
        ordering = ['-date']

    def __str__(self):
        return f"{self.away_team} @ {self.home_team} - {self.date:%Y-%m-%d}"

    @property
    def total_runs(self):
        if self.home_runs is not None and self.away_runs is not None:
            return self.home_runs + self.away_runs
        return None

    @property
    def is_finished(self):
        return self.status in ('Game Finished', 'Finished', 'After OT')


class BaseballPrediction(models.Model):
    game = models.ForeignKey(
        BaseballGame, on_delete=models.CASCADE, related_name='predictions',
        verbose_name="Partido")
    model_name = models.CharField(max_length=100, verbose_name="Modelo")

    pred_home_runs = models.FloatField(verbose_name="λ carreras local")
    pred_away_runs = models.FloatField(verbose_name="λ carreras visitante")

    p_home_win = models.FloatField(null=True, blank=True, verbose_name="P(Gana Local)")
    p_away_win = models.FloatField(null=True, blank=True, verbose_name="P(Gana Visitante)")

    # {"7.5": {"over": 0.55, "under": 0.45}, ...}
    total_line_probs = models.JSONField(default=dict, blank=True, verbose_name="Probabilidades total de carreras")
    # {"1.5": {"home": 0.5, "away": 0.5}, ...}
    runline_probs = models.JSONField(default=dict, blank=True, verbose_name="Probabilidades run line")
    # {"2.5": {"over": ...}} primeros 5 innings
    first5_probs = models.JSONField(default=dict, blank=True, verbose_name="Probabilidades primeros 5 innings")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Predicción MLB"
        verbose_name_plural = "Predicciones MLB"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.model_name} {self.game} - {self.pred_home_runs:.1f} vs {self.pred_away_runs:.1f}"
