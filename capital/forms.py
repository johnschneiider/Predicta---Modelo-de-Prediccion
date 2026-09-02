"""
Formulario de gestión de capital (modo de stake por usuario).

Se renderiza DENTRO de la página /auto-betting/configuracion/ (form
AutoBetConfigForm), pero vive en la app `capital` para mantener
modularizado el dominio de capital.
"""

from django import forms

from .models import CapitalConfig


class CapitalConfigForm(forms.ModelForm):
    """Cada usuario elige cómo se calcula el stake de sus apuestas."""

    class Meta:
        model = CapitalConfig
        fields = [
            'modo',
            'porcentaje',
            'balance_inicial',
            'stake_min_cop',
            'stake_max_cop',
        ]
        widgets = {
            'modo': forms.RadioSelect(attrs={'class': 'cfg-radio'}),
            'porcentaje': forms.NumberInput(attrs={
                'class': 'cfg-input', 'step': '0.1', 'min': '0.1', 'max': '100',
            }),
            'balance_inicial': forms.NumberInput(attrs={
                'class': 'cfg-input', 'step': '100', 'min': '0',
                'placeholder': 'Ej. 250000 (COP)',
            }),
            'stake_min_cop': forms.NumberInput(attrs={'class': 'cfg-input', 'step': '100', 'min': '100'}),
            'stake_max_cop': forms.NumberInput(attrs={'class': 'cfg-input', 'step': '100', 'min': '100'}),
        }
        labels = {
            'modo': '¿Cómo se calcula el monto de cada apuesta?',
            'porcentaje': '% del balance por apuesta',
            'balance_inicial': 'Balance actual de tu cuenta BetPlay (COP)',
            'stake_min_cop': 'Stake mínimo (COP)',
            'stake_max_cop': 'Stake máximo (COP)',
        }
        help_texts = {
            'modo': (
                'Fijo: se usa el stake que ya tienes configurado arriba (sin cambios). '
                'Compuesto: el sistema calcula el stake como un % de tu balance paralelo.'
            ),
            'porcentaje': (
                'Se calcula sobre el balance paralelo (balance declarado + ganancias '
                '− pérdidas desde la activación). Ej. 2% con 250.000 COP → stake de 5.000 COP.'
            ),
            'balance_inicial': (
                'Solo se pide UNA vez (al activar el modo compuesto). Si luego lo vuelves '
                'a escribir, se toma como reconciliación: el sistema ajusta la diferencia '
                'sin mover el historial.'
            ),
            'stake_min_cop': (
                'Piso de seguridad. Si el % calculado queda por debajo de este valor, '
                'el sistema NO apuesta ese día (protege de apostar migajas o en saldo residual).'
            ),
            'stake_max_cop': (
                'Techo de seguridad. El stake nunca superará este valor aunque el balance crezca.'
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # El balance declarado se gestiona manualmente en la vista; el campo
        # es opcional a nivel de formulario (la vista valida el primer alta).
        self.fields['balance_inicial'].required = False

    def clean(self):
        cleaned = super().clean()
        modo = cleaned.get('modo')
        porcentaje = cleaned.get('porcentaje')
        balance = cleaned.get('balance_inicial')
        stake_min = cleaned.get('stake_min_cop')
        stake_max = cleaned.get('stake_max_cop')

        if modo == CapitalConfig.MODO_COMPUESTO:
            # Primer alta del modo compuesto: el balance es obligatorio.
            es_primer_alta = self.instance.pk is None or self.instance.ancla is None
            if es_primer_alta and (balance is None or balance <= 0):
                self.add_error(
                    'balance_inicial',
                    'Para activar el interés compuesto debes indicar el balance actual '
                    'de tu cuenta BetPlay (COP).'
                )
            if porcentaje is None or porcentaje <= 0 or porcentaje > 100:
                self.add_error('porcentaje', 'El porcentaje debe estar entre 0.1 y 100.')

        if stake_min is not None and stake_min < 100:
            self.add_error('stake_min_cop', 'El mínimo debe ser al menos 100 COP.')
        if stake_max is not None and stake_min is not None and stake_max < stake_min:
            self.add_error('stake_max_cop', 'El máximo debe ser ≥ al mínimo.')
        return cleaned
