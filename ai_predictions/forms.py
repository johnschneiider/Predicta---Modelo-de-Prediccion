"""
Formularios para predicciones de IA
"""

from django import forms
from football_data.models import League


class PredictionForm(forms.Form):
    """Formulario para realizar predicciones"""
    
    league = forms.ModelChoiceField(
        queryset=League.objects.all(),
        label='Liga',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'leagueSelect',
            'onchange': 'loadTeams()'
        })
    )
    
    home_team = forms.ChoiceField(
        choices=[],
        label='Equipo Local',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'homeTeamSelect'
        })
    )
    
    away_team = forms.ChoiceField(
        choices=[],
        label='Equipo Visitante',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'awayTeamSelect'
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Cargar equipos si hay una liga seleccionada
        if self.data.get('league'):
            try:
                league_id = self.data.get('league')
                league = League.objects.get(id=league_id)
                teams = self._get_teams_for_league(league)
                
                self.fields['home_team'].choices = teams
                self.fields['away_team'].choices = teams
            except League.DoesNotExist:
                pass
    
    def _get_teams_for_league(self, league):
        """Obtiene equipos únicos de una liga (Django + SQLite fallback)."""
        from football_data.models import Match
        
        home_teams = Match.objects.filter(league=league).values_list('home_team', flat=True).distinct()
        away_teams = Match.objects.filter(league=league).values_list('away_team', flat=True).distinct()
        all_teams = sorted(list(set(list(home_teams) + list(away_teams))))
        
        # Si no hay equipos en Django, buscar en SQLite
        if not all_teams:
            try:
                import sqlite3
                LEAGUE_MAP = {'Serie A (Brasil)': 'Serie A', 'Serie B (Brasil)': 'Serie B',
        'Primera A (Colombia)': 'Primera A', 'Primera Division (Argentina)': 'Primera Division',
        'Liga MX (Mexico)': 'Liga MX',
        'US MLS (USA)': 'US MLS'}
                sqlite_league = LEAGUE_MAP.get(league.name, league.name)
                conn = sqlite3.connect('/var/www/predicta.com.co/data/corners_scraped.db')
                home = conn.execute(
                    "SELECT DISTINCT home_team FROM corners_matches WHERE league=?",
                    (sqlite_league,)
                ).fetchall()
                away = conn.execute(
                    "SELECT DISTINCT away_team FROM corners_matches WHERE league=?",
                    (sqlite_league,)
                ).fetchall()
                conn.close()
                all_teams = sorted(set([r[0] for r in home] + [r[0] for r in away]))
            except Exception:
                pass
        
        return [(team, team) for team in all_teams]
    
    def clean(self):
        cleaned_data = super().clean()
        home_team = cleaned_data.get('home_team')
        away_team = cleaned_data.get('away_team')
        
        if home_team and away_team and home_team == away_team:
            raise forms.ValidationError("El equipo local y visitante deben ser diferentes.")
        
        return cleaned_data


class TrainingForm(forms.Form):
    """Formulario para entrenar modelos"""
    
    PREDICTION_CHOICES = [
        ('shots_total', 'Remates Totales'),
        ('shots_home', 'Remates Local'),
        ('shots_away', 'Remates Visitante'),
        ('shots_on_target', 'Remates a Puerta'),
        ('goals_total', 'Goles Totales'),
        ('goals_home', 'Goles Local'),
        ('goals_away', 'Goles Visitante'),
        ('corners_total', 'Corners Totales'),
        ('corners_home', 'Corners Local'),
        ('corners_away', 'Corners Visitante'),
        ('both_teams_score', 'Ambos Marcan'),
    ]
    
    league = forms.ModelChoiceField(
        queryset=League.objects.all(),
        label='Liga',
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    prediction_type = forms.ChoiceField(
        choices=PREDICTION_CHOICES,
        label='Tipo de Predicción',
        initial='shots_total',
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    model_type = forms.ChoiceField(
        choices=[
            ('linear_regression', 'Regresión Lineal'),
            ('random_forest', 'Random Forest'),
            ('gradient_boosting', 'Gradient Boosting'),
        ],
        label='Tipo de Modelo',
        initial='linear_regression',
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
