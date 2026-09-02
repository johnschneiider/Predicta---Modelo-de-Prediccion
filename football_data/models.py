"""
Modelos para datos históricos de fútbol
"""

from django.db import models
from django.utils import timezone


class League(models.Model):
    """Modelo para ligas/divisiones"""
    name = models.CharField(max_length=100, unique=True)
    country = models.CharField(max_length=50, blank=True)
    season = models.CharField(max_length=20, blank=True)
    active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Liga"
        verbose_name_plural = "Ligas"
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} {self.season}"


class Match(models.Model):
    """Modelo para partidos de fútbol con datos históricos"""
    league = models.ForeignKey(League, on_delete=models.CASCADE, related_name='matches')
    # Archivo de origen (para poder borrar por archivo)
    source_file = models.ForeignKey('ExcelFile', on_delete=models.SET_NULL, null=True, blank=True, related_name='matches')
    
    # Información básica
    date = models.DateField()
    time = models.TimeField(null=True, blank=True)
    home_team = models.CharField(max_length=100)
    away_team = models.CharField(max_length=100)
    
    # Resultados
    fthg = models.IntegerField(null=True, blank=True, verbose_name="Full Time Home Goals")
    ftag = models.IntegerField(null=True, blank=True, verbose_name="Full Time Away Goals")
    ftr = models.CharField(max_length=1, choices=[('H', 'Home'), ('D', 'Draw'), ('A', 'Away')], 
                          null=True, blank=True, verbose_name="Full Time Result")
    
    # Resultados al descanso
    hthg = models.IntegerField(null=True, blank=True, verbose_name="Half Time Home Goals")
    htag = models.IntegerField(null=True, blank=True, verbose_name="Half Time Away Goals")
    htr = models.CharField(max_length=1, choices=[('H', 'Home'), ('D', 'Draw'), ('A', 'Away')], 
                          null=True, blank=True, verbose_name="Half Time Result")
    
    # Estadísticas del partido
    hs = models.IntegerField(null=True, blank=True, verbose_name="Home Shots")
    as_field = models.IntegerField(null=True, blank=True, verbose_name="Away Shots", db_column='as_field')
    hst = models.IntegerField(null=True, blank=True, verbose_name="Home Shots on Target")
    ast = models.IntegerField(null=True, blank=True, verbose_name="Away Shots on Target")
    hf = models.IntegerField(null=True, blank=True, verbose_name="Home Fouls")
    af = models.IntegerField(null=True, blank=True, verbose_name="Away Fouls")
    hc = models.IntegerField(null=True, blank=True, verbose_name="Home Corners")
    ac = models.IntegerField(null=True, blank=True, verbose_name="Away Corners")
    hy = models.IntegerField(null=True, blank=True, verbose_name="Home Yellow Cards")
    ay = models.IntegerField(null=True, blank=True, verbose_name="Away Yellow Cards")
    hr = models.IntegerField(null=True, blank=True, verbose_name="Home Red Cards")
    ar = models.IntegerField(null=True, blank=True, verbose_name="Away Red Cards")
    
    # Expected Goals (xG) desde Flashscore
    xg_home = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True, verbose_name="xG Home")
    xg_away = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True, verbose_name="xG Away")
    
    # Corners detallados
    corners_total = models.IntegerField(null=True, blank=True, verbose_name="Total Corners")
    corners_home = models.IntegerField(null=True, blank=True, verbose_name="Home Corners")
    corners_away = models.IntegerField(null=True, blank=True, verbose_name="Away Corners")
    corners_1h = models.IntegerField(null=True, blank=True, verbose_name="Corners 1st Half")
    corners_2h = models.IntegerField(null=True, blank=True, verbose_name="Corners 2nd Half")
    
    # Ambos marcan
    both_teams_score = models.BooleanField(null=True, blank=True, verbose_name="Both Teams Score")
    
    # Cuotas Bet365
    b365h = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Bet365 Home")
    b365d = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Bet365 Draw")
    b365a = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Bet365 Away")
    
    # Cuotas adicionales
    bfdh = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="BFD Home")
    bfdd = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="BFD Draw")
    bfda = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="BFD Away")
    
    bmgmh = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="BMGM Home")
    bmgmd = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="BMGM Draw")
    bmgma = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="BMGM Away")
    
    bvh = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="BV Home")
    bvd = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="BV Draw")
    bva = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="BV Away")
    
    clh = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="CL Home")
    cld = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="CL Draw")
    cla = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="CL Away")
    
    lbh = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="LB Home")
    lbd = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="LB Draw")
    lba = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="LB Away")
    
    bfeh = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="BFE Home")
    bfed = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="BFE Draw")
    bfea = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="BFE Away")
    
    # Cuotas Blue Square
    bwh = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Blue Square Home")
    bwd = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Blue Square Draw")
    bwa = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Blue Square Away")
    
    # Cuotas Interwetten
    iwh = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Interwetten Home")
    iwd = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Interwetten Draw")
    iwa = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Interwetten Away")
    
    # Cuotas Pinnacle
    psh = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Pinnacle Home")
    psd = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Pinnacle Draw")
    psa = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Pinnacle Away")
    
    # Cuotas William Hill
    whh = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="William Hill Home")
    whd = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="William Hill Draw")
    wha = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="William Hill Away")
    
    # Cuotas VC Bet
    vch = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="VC Bet Home")
    vcd = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="VC Bet Draw")
    vca = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="VC Bet Away")
    
    # Análisis de cuotas
    maxh = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Max Home")
    maxd = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Max Draw")
    maxa = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Max Away")
    avgh = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Avg Home")
    avgd = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Avg Draw")
    avga = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Avg Away")
    
    # Mercados de goles
    b365_over_25 = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Bet365 Over 2.5")
    b365_under_25 = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Bet365 Under 2.5")
    p_over_25 = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Pinnacle Over 2.5")
    p_under_25 = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Pinnacle Under 2.5")
    max_over_25 = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Max Over 2.5")
    max_under_25 = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Max Under 2.5")
    avg_over_25 = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Avg Over 2.5")
    avg_under_25 = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Avg Under 2.5")
    bfe_over_25 = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="BFE Over 2.5")
    bfe_under_25 = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="BFE Under 2.5")
    
    # Handicap Asiático
    ahh = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Asian Handicap Home")
    b365ahh = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Bet365 AH Home")
    b365aha = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Bet365 AH Away")
    pahh = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Pinnacle AH Home")
    paha = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Pinnacle AH Away")
    maxahh = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Max AH Home")
    maxaha = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Max AH Away")
    avgahh = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Avg AH Home")
    avgaha = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Avg AH Away")
    bfeahh = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="BFE AH Home")
    bfeaha = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="BFE AH Away")
    
    # Cuotas de Corners
    b365ch = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Bet365 Corners Home")
    b365cd = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Bet365 Corners Draw")
    b365ca = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Bet365 Corners Away")
    
    bfdch = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="BFD Corners Home")
    bfdcd = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="BFD Corners Draw")
    bfdca = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="BFD Corners Away")
    
    bmgmch = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="BMGM Corners Home")
    bmgmcd = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="BMGM Corners Draw")
    bmgmca = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="BMGM Corners Away")
    
    bvch = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="BV Corners Home")
    bvcd = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="BV Corners Draw")
    bvca = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="BV Corners Away")
    
    bwch = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="BW Corners Home")
    bwcd = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="BW Corners Draw")
    bwca = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="BW Corners Away")
    
    clch = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="CL Corners Home")
    clcd = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="CL Corners Draw")
    clca = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="CL Corners Away")
    
    lbch = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="LB Corners Home")
    lbcd = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="LB Corners Draw")
    lbca = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="LB Corners Away")
    
    psch = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="PS Corners Home")
    pscd = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="PS Corners Draw")
    psca = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="PS Corners Away")
    
    maxch = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Max Corners Home")
    maxcd = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Max Corners Draw")
    maxca = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Max Corners Away")
    
    avgch = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Avg Corners Home")
    avgcd = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Avg Corners Draw")
    avgca = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Avg Corners Away")
    
    bfech = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="BFE Corners Home")
    bfecd = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="BFE Corners Draw")
    bfeca = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="BFE Corners Away")
    
    # Mercados de corners Over/Under
    b365c_over_25 = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Bet365 Corners Over 2.5")
    b365c_under_25 = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Bet365 Corners Under 2.5")
    pc_over_25 = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="PS Corners Over 2.5")
    pc_under_25 = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="PS Corners Under 2.5")
    maxc_over_25 = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Max Corners Over 2.5")
    maxc_under_25 = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Max Corners Under 2.5")
    avgc_over_25 = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Avg Corners Over 2.5")
    avgc_under_25 = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Avg Corners Under 2.5")
    bfec_over_25 = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="BFE Corners Over 2.5")
    bfec_under_25 = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="BFE Corners Under 2.5")
    
    # Handicap Asiático de Corners
    ahch = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Asian Handicap Corners")
    b365cahh = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Bet365 AH Corners Home")
    b365caha = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Bet365 AH Corners Away")
    pcahh = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="PS AH Corners Home")
    pcaha = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="PS AH Corners Away")
    maxcahh = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Max AH Corners Home")
    maxcaha = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Max AH Corners Away")
    avgcahh = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Avg AH Corners Home")
    avgcaha = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Avg AH Corners Away")
    bfecahh = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="BFE AH Corners Home")
    bfecaha = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="BFE AH Corners Away")
    
    # Metadatos
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Partido"
        verbose_name_plural = "Partidos"
        ordering = ['-date', 'home_team']
        unique_together = ['league', 'date', 'home_team', 'away_team']
    
    def __str__(self):
        return f"{self.home_team} vs {self.away_team} ({self.date})"
    
    @property
    def total_goals(self):
        """Total de goles en el partido"""
        if self.fthg is not None and self.ftag is not None:
            return self.fthg + self.ftag
        return None
    
    @property
    def is_over_25(self):
        """¿Fue Over 2.5 goles?"""
        total = self.total_goals
        return total > 2.5 if total is not None else None
    
    @property
    def total_corners(self):
        """Total de corners en el partido"""
        if self.hc is not None and self.ac is not None:
            return self.hc + self.ac
        return None
    
    @property
    def is_both_teams_score(self):
        """¿Ambos equipos marcaron?"""
        if self.fthg is not None and self.ftag is not None:
            return self.fthg > 0 and self.ftag > 0
        return None
    
    @property
    def best_home_odds(self):
        """Mejor cuota para el equipo local"""
        odds = [self.b365h, self.bwh, self.iwh, self.psh, self.whh, self.vch]
        valid_odds = [odd for odd in odds if odd is not None]
        return max(valid_odds) if valid_odds else None
    
    @property
    def best_draw_odds(self):
        """Mejor cuota para el empate"""
        odds = [self.b365d, self.bwd, self.iwd, self.psd, self.whd, self.vcd]
        valid_odds = [odd for odd in odds if odd is not None]
        return max(valid_odds) if valid_odds else None
    
    @property
    def best_away_odds(self):
        """Mejor cuota para el equipo visitante"""
        odds = [self.b365a, self.bwa, self.iwa, self.psa, self.wha, self.vca]
        valid_odds = [odd for odd in odds if odd is not None]
        return max(valid_odds) if valid_odds else None


class ExcelFile(models.Model):
    """Modelo para rastrear archivos Excel importados"""
    name = models.CharField(max_length=200)
    file = models.FileField(upload_to='excel_files/', null=True, blank=True)
    file_path = models.CharField(max_length=500, blank=True)
    league = models.ForeignKey(League, on_delete=models.CASCADE, related_name='excel_files')
    
    # Estadísticas de importación
    total_rows = models.IntegerField(default=0)
    imported_rows = models.IntegerField(default=0)
    failed_rows = models.IntegerField(default=0)
    
    # Metadatos
    imported_at = models.DateTimeField(auto_now_add=True)
    file_size = models.BigIntegerField(default=0)
    
    class Meta:
        verbose_name = "Archivo Excel"
        verbose_name_plural = "Archivos Excel"
        ordering = ['-imported_at']
    
    def __str__(self):
        return f"{self.name} - {self.league.name}"
    
    @property
    def success_rate(self):
        """Tasa de éxito de importación"""
        if self.total_rows > 0:
            return (self.imported_rows / self.total_rows) * 100
        return 0