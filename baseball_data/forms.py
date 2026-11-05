from django import forms
from .models import BaseballTeam


class MLBForm(forms.Form):
    home_team = forms.ModelChoiceField(
        queryset=BaseballTeam.objects.all().order_by('name'),
        empty_label="Selecciona equipo local",
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'home_team'}),
        label="Equipo Local")
    away_team = forms.ModelChoiceField(
        queryset=BaseballTeam.objects.all().order_by('name'),
        empty_label="Selecciona equipo visitante",
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'away_team'}),
        label="Equipo Visitante")

    def clean(self):
        cleaned = super().clean()
        h = cleaned.get('home_team')
        a = cleaned.get('away_team')
        if h and a and h == a:
            raise forms.ValidationError("Los equipos deben ser diferentes.")
        return cleaned
