"""
Migración 0004: agrega campos de CLV (closing_odds, clv), flag is_system,
y nuevo modelo OddsSnapshot.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('auto_betting', '0003_historialapuesta'),
    ]

    operations = [
        # Campos nuevos en HistorialApuesta
        migrations.AddField(
            model_name='historialapuesta',
            name='closing_odds',
            field=models.FloatField(blank=True, null=True, verbose_name='Cuota de cierre'),
        ),
        migrations.AddField(
            model_name='historialapuesta',
            name='clv',
            field=models.FloatField(blank=True, null=True, verbose_name='CLV % (negativo = sin valor)'),
        ),
        migrations.AddField(
            model_name='historialapuesta',
            name='is_system',
            field=models.BooleanField(default=False, verbose_name='Apuesta del sistema'),
        ),
        migrations.AddIndex(
            model_name='historialapuesta',
            index=models.Index(fields=['is_system', '-placed_date'], name='auto_bet_is_sys_date_idx'),
        ),
        migrations.AddIndex(
            model_name='historialapuesta',
            index=models.Index(fields=['outcome_id', '-placed_date'], name='auto_bet_outcome_place_idx'),
        ),

        # Nuevo modelo OddsSnapshot
        migrations.CreateModel(
            name='OddsSnapshot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('outcome_id', models.BigIntegerField(db_index=True, verbose_name='Outcome ID')),
                ('event_id', models.BigIntegerField(db_index=True, verbose_name='Event ID')),
                ('market', models.CharField(max_length=250, verbose_name='Mercado')),
                ('seleccion', models.CharField(blank=True, default='', max_length=200, verbose_name='Selección')),
                ('linea', models.FloatField(blank=True, null=True, verbose_name='Línea')),
                ('side', models.CharField(blank=True, default='', max_length=20, verbose_name='Lado (over/under/1/x/2/si/no)')),
                ('odds_decimal', models.FloatField(verbose_name='Cuota decimal')),
                ('captured_at', models.DateTimeField(auto_now_add=True, verbose_name='Capturado')),
            ],
            options={
                'verbose_name': 'Snapshot de Cuota',
                'verbose_name_plural': 'Snapshots de Cuotas',
                'ordering': ['-captured_at'],
            },
        ),
        migrations.AddIndex(
            model_name='oddssnapshot',
            index=models.Index(fields=['outcome_id', '-captured_at'], name='oddssnap_outcome_capt_idx'),
        ),
        migrations.AddIndex(
            model_name='oddssnapshot',
            index=models.Index(fields=['event_id'], name='oddssnap_event_id_idx'),
        ),
    ]
