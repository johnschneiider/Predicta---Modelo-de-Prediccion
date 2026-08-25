# Hace NOT NULL los campos usuario (backfill ya los pobló en 0006).

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('auto_betting', '0006_backfill_usuario'),
    ]

    operations = [
        migrations.AlterField(
            model_name='autobet',
            name='usuario',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='auto_bets', to=settings.AUTH_USER_MODEL, verbose_name='Usuario'),
        ),
        migrations.AlterField(
            model_name='autobetconfig',
            name='usuario',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='auto_bet_config', to=settings.AUTH_USER_MODEL, verbose_name='Usuario'),
        ),
        migrations.AlterField(
            model_name='dailycounter',
            name='usuario',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='daily_counters', to=settings.AUTH_USER_MODEL, verbose_name='Usuario'),
        ),
        migrations.AlterField(
            model_name='historialapuesta',
            name='usuario',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='historial_apuestas', to=settings.AUTH_USER_MODEL, verbose_name='Usuario'),
        ),
    ]
