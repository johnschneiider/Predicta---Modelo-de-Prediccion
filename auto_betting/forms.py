"""Formularios del auto_betting: configuración por usuario (BetPlay) y
configuración global de umbrales por submercado (solo admin)."""

from django import forms

from .models import AutoBetConfig, MarketFilterConfig

# Submercados: por cada uno hay 5 campos (p, confidence, enabled, ev, cuota).
_SUBMERCADOS = [
    'goals_over', 'goals_under',
    'corners_over', 'corners_under',
    'shots_on_target_over', 'shots_on_target_under',
    'btts_si', 'btts_no',
]
_GLOBALES = [
    'cuota_minima_global', 'stop_loss_diario_cop',
    'max_exposicion_evento_cop', 'calib_cap',
]
# Filtro por línea (Fix 2026-08-31): solo tiros a puerta over/under.
_LINE_FIELDS = [
    'shots_on_target_over_min_line', 'shots_on_target_over_max_line',
    'shots_on_target_under_min_line', 'shots_on_target_under_max_line',
]


class AutoBetConfigForm(forms.ModelForm):
    """Permite a cada usuario ver/editar SU propia configuración de auto-apuestas."""

    class Meta:
        model = AutoBetConfig
        fields = [
            'ticket',
            'punter_id',
            'cuota_minima',
            'stake',
            'max_apuestas_diarias',
            'horas_adelante',
            'activo',
        ]
        widgets = {
            'ticket': forms.Textarea(attrs={
                'rows': 3,
                'class': 'cfg-input',
                'placeholder': 'Ticket de login de BetPlay (ej. TU-TICKET-AQUI, ver SOUL.md §2)',
            }),
            'punter_id': forms.TextInput(attrs={'class': 'cfg-input', 'placeholder': 'Tu Punter ID de BetPlay'}),
            'cuota_minima': forms.NumberInput(attrs={'class': 'cfg-input', 'step': '0.05'}),
            'stake': forms.NumberInput(attrs={
                'class': 'cfg-input', 'step': '100', 'min': '100',
                'placeholder': 'Ej. 500 (quinientos pesos)',
            }),
            'max_apuestas_diarias': forms.NumberInput(attrs={'class': 'cfg-input'}),
            'horas_adelante': forms.NumberInput(attrs={'class': 'cfg-input'}),
            'activo': forms.CheckboxInput(attrs={'class': 'cfg-check'}),
        }
        labels = {
            'stake': 'Stake por apuesta (COP)',
        }
        help_texts = {
            'ticket': (
                'Credencial de sesión de BetPlay. Se obtiene logueándote en betplay.com.co '
                'y copiando el "ticket" desde las DevTools (Red → punter/login). Es sensible: '
                'equivale a acceso a tu cuenta.'
            ),
            'punter_id': 'Tu Punter ID de BetPlay (identificador de cuenta).',
            'cuota_minima': 'Cuota mínima (>) para colocar una apuesta. Default 2.0.',
            'stake': 'Monto real de cada apuesta en pesos colombianos.',
            'max_apuestas_diarias': 'Límite de apuestas por día (default 20).',
            'horas_adelante': 'Ventana de escaneo de partidos (horas hacia adelante). Default 24.',
            'activo': 'Activa/desactiva el auto-betting para tu cuenta.',
        }

    def clean_stake(self):
        """
        El usuario escribe COP (dinero real). La BD guarda unidades Kambi
        (COP × 1000), así que la conversión se hace aquí por detrás.
        """
        cop = self.cleaned_data.get('stake')
        if cop is None:
            return cop
        try:
            cop_int = int(float(cop))
        except (TypeError, ValueError):
            raise forms.ValidationError('Escribe un número válido en pesos.')
        if cop_int <= 0:
            raise forms.ValidationError('El stake debe ser mayor a 0 pesos.')
        return cop_int * 1000


class MarketFilterConfigForm(forms.ModelForm):
    """
    Formulario GLOBAL de umbrales por submercado (P mínima / confianza mínima
    para cada mercado+lado: goles over/under, córners over/under, tiros a
    puerta over/under, BTTS sí/no).

    Aplica a TODOS los usuarios del auto-betting por igual. Solo un
    superusuario (admin) puede acceder a este formulario (ver
    views.configuracion_umbrales / decorador user_passes_test).
    """

    _SUBS = _SUBMERCADOS
    # Campos que representan probabilidad/EV en rango [0, 1].
    _PROB_SUFFIXES = ('_min_p', '_min_confidence', '_min_ev')

    class Meta:
        model = MarketFilterConfig
        fields = (
            [f'{s}_min_p' for s in _SUBMERCADOS]
            + [f'{s}_min_confidence' for s in _SUBMERCADOS]
            + [f'{s}_enabled' for s in _SUBMERCADOS]
            + [f'{s}_min_ev' for s in _SUBMERCADOS]
            + [f'{s}_min_cuota' for s in _SUBMERCADOS]
            + _LINE_FIELDS
            + _GLOBALES
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        prob_step = {'class': 'cfg-input', 'step': '0.01', 'min': '0', 'max': '1'}
        cuota_step = {'class': 'cfg-input', 'step': '0.05', 'min': '0'}
        cop_step = {'class': 'cfg-input', 'step': '1000'}
        line_step = {'class': 'cfg-input', 'step': '0.5', 'min': '0'}
        for name, field in self.fields.items():
            if name.endswith('_enabled'):
                field.widget = forms.CheckboxInput(attrs={'class': 'cfg-check'})
            elif name.endswith('_min_line') or name.endswith('_max_line'):
                field.widget = forms.NumberInput(attrs=line_step)
            elif name.endswith('_min_cuota') or name == 'cuota_minima_global':
                field.widget = forms.NumberInput(attrs=cuota_step)
            elif name in ('stop_loss_diario_cop', 'max_exposicion_evento_cop'):
                field.widget = forms.NumberInput(attrs=cop_step)
            elif name == 'calib_cap':
                field.widget = forms.NumberInput(attrs=prob_step)
            else:  # _min_p, _min_confidence, _min_ev
                field.widget = forms.NumberInput(attrs=prob_step)

    def clean(self):
        cleaned = super().clean()
        # Validación defensiva: probabilidades/EV/cap en [0, 1].
        prob_names = (
            [n for n in cleaned if n.endswith(self._PROB_SUFFIXES)]
            + ['calib_cap']
        )
        for name in prob_names:
            value = cleaned.get(name)
            if value is None:
                continue
            if value < 0 or value > 1:
                self.add_error(name, 'Debe estar entre 0.0 y 1.0.')
        # Cuotas mínimas: ≥ 0 (0 = usa global).
        for name in [f'{s}_min_cuota' for s in self._SUBS] + ['cuota_minima_global']:
            value = cleaned.get(name)
            if value is not None and value < 0:
                self.add_error(name, 'No puede ser negativa.')
        # Líneas: ≥ 0 (0 = sin tope).
        for name in _LINE_FIELDS:
            value = cleaned.get(name)
            if value is not None and value < 0:
                self.add_error(name, 'No puede ser negativa.')
        return cleaned
