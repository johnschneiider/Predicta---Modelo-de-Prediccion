"""
Modelos para el motor de Value Betting (BetPlay vs Predicta)
"""

from django.db import models
from django.utils import timezone


class KambiMatch(models.Model):
    """Partido traído desde la API de Kambi (BetPlay)"""
    
    kambi_event_id = models.BigIntegerField(unique=True, verbose_name="Kambi Event ID")
    home_team = models.CharField(max_length=200, verbose_name="Equipo Local")
    away_team = models.CharField(max_length=200, verbose_name="Equipo Visitante")
    league_name_kambi = models.CharField(max_length=200, verbose_name="Liga (Kambi)")
    league_path_kambi = models.CharField(max_length=300, verbose_name="Path Kambi")
    start_time = models.DateTimeField(verbose_name="Inicio del partido")
    sport = models.CharField(max_length=50, default="FOOTBALL", verbose_name="Deporte")
    state = models.CharField(max_length=30, default="NOT_STARTED", verbose_name="Estado")
    
    # Mapeo a Predicta
    predicta_league = models.ForeignKey(
        'football_data.League',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="Liga Predicta"
    )
    mapped_home_team = models.CharField(max_length=200, blank=True, null=True, verbose_name="Equipo mapeado (local)")
    mapped_away_team = models.CharField(max_length=200, blank=True, null=True, verbose_name="Equipo mapeado (visitante)")
    mapping_confidence = models.FloatField(default=0.0, verbose_name="Confianza del mapeo")
    
    fetched_at = models.DateTimeField(default=timezone.now, verbose_name="Obtenido a las")
    
    class Meta:
        verbose_name = "Partido Kambi"
        verbose_name_plural = "Partidos Kambi"
        ordering = ['start_time']
    
    def __str__(self):
        return f"{self.home_team} vs {self.away_team} ({self.start_time.strftime('%Y-%m-%d %H:%M')})"


class KambiBetOffer(models.Model):
    """Cuota de BetPlay para un partido y mercado específico"""
    
    match = models.ForeignKey(KambiMatch, on_delete=models.CASCADE, related_name='bet_offers')
    kambi_offer_id = models.BigIntegerField(verbose_name="Kambi Offer ID")
    criterion_label = models.CharField(max_length=200, verbose_name="Mercado")
    criterion_id = models.BigIntegerField(verbose_name="Criterion ID")
    offer_type = models.CharField(max_length=100, verbose_name="Tipo de oferta")
    
    # Datos del outcome
    outcome_label = models.CharField(max_length=100, verbose_name="Selección")
    outcome_type = models.CharField(max_length=50, verbose_name="Tipo de outcome")
    odds = models.IntegerField(verbose_name="Cuota (entero Kambi)")
    odds_decimal = models.FloatField(verbose_name="Cuota decimal")
    line = models.FloatField(null=True, blank=True, verbose_name="Línea")
    status = models.CharField(max_length=30, default="OPEN", verbose_name="Estado")
    
    # Categoria Kambi
    category_id = models.IntegerField(null=True, blank=True, verbose_name="Category ID")
    
    fetched_at = models.DateTimeField(default=timezone.now, verbose_name="Obtenido a las")
    
    class Meta:
        verbose_name = "Cuota BetPlay"
        verbose_name_plural = "Cuotas BetPlay"
        ordering = ['match', 'criterion_label', 'outcome_label']
        indexes = [
            models.Index(fields=['match', 'criterion_label']),
        ]
    
    @property
    def implied_probability(self):
        """Probabilidad implícita de la cuota"""
        if self.odds_decimal > 0:
            return 1.0 / self.odds_decimal
        return 0.0
    
    def __str__(self):
        return f"{self.match.home_team} vs {self.match.away_team} | {self.criterion_label} | {self.outcome_label} @ {self.odds_decimal:.2f}"


class ValueOpportunity(models.Model):
    """Oportunidad de value betting detectada"""
    
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('executed', 'Ejecutada'),
        ('expired', 'Expirada'),
        ('dismissed', 'Descartada'),
    ]
    
    match = models.ForeignKey(KambiMatch, on_delete=models.CASCADE, related_name='opportunities')
    
    # Mercado y selección
    market = models.CharField(max_length=200, verbose_name="Mercado")
    selection = models.CharField(max_length=100, verbose_name="Selección")
    bet_instruction = models.CharField(max_length=300, default="", verbose_name="Instrucción de apuesta")
    
    # Cuota de BetPlay
    betplay_odds = models.FloatField(verbose_name="Cuota BetPlay")
    betplay_implied_prob = models.FloatField(verbose_name="Prob. implícita BetPlay")
    
    # Predicción de Predicta
    predicta_probability = models.FloatField(verbose_name="Prob. Predicta")
    predicta_prediction = models.FloatField(null=True, blank=True, verbose_name="Valor predicho")
    predicta_confidence = models.FloatField(default=0.0, verbose_name="Confianza")
    predicta_model = models.CharField(max_length=200, blank=True, verbose_name="Modelo usado")
    
    # Value
    edge = models.FloatField(verbose_name="Edge (%)")
    ev = models.FloatField(verbose_name="EV (valor esperado)")
    is_value = models.BooleanField(default=False, verbose_name="¿Es value bet?")
    
    # Estado
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Línea si aplica
    line = models.FloatField(null=True, blank=True, verbose_name="Línea")
    
    created_at = models.DateTimeField(default=timezone.now, verbose_name="Detectada el")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizada el")
    
    class Meta:
        verbose_name = "Oportunidad de Value"
        verbose_name_plural = "Oportunidades de Value"
        ordering = ['-edge', '-created_at']
        indexes = [
            models.Index(fields=['is_value', '-edge']),
            models.Index(fields=['status', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.match.home_team} vs {self.match.away_team} | {self.market} | {self.selection} @ {self.betplay_odds:.2f} | edge={self.edge:.1f}%"
    
    @property
    def home_team(self):
        return self.match.home_team
    
    @property
    def away_team(self):
        return self.match.away_team


class ScanRun(models.Model):
    """Registro de cada ejecución del motor de escaneo"""
    
    STATUS_CHOICES = [
        ('running', 'En progreso'),
        ('completed', 'Completado'),
        ('failed', 'Fallido'),
    ]
    
    started_at = models.DateTimeField(default=timezone.now, verbose_name="Iniciado")
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name="Finalizado")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='running')
    
    # Stats
    matches_fetched = models.IntegerField(default=0, verbose_name="Partidos obtenidos")
    matches_mapped = models.IntegerField(default=0, verbose_name="Partidos mapeados")
    predictions_generated = models.IntegerField(default=0, verbose_name="Predicciones generadas")
    opportunities_found = models.IntegerField(default=0, verbose_name="Oportunidades encontradas")
    value_bets_found = models.IntegerField(default=0, verbose_name="Value bets encontrados")
    
    # Errores
    errors = models.TextField(blank=True, default="", verbose_name="Errores")
    
    class Meta:
        verbose_name = "Escaneo"
        verbose_name_plural = "Escaneos"
        ordering = ['-started_at']
    
    def __str__(self):
        return f"Escaneo {self.started_at.strftime('%Y-%m-%d %H:%M')} | {self.status} | {self.value_bets_found} value bets"