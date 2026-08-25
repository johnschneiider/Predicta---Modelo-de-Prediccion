# Backfill: asigna todos los registros existentes de auto_betting al usuario dueño (superuser).

from django.db import migrations


def backfill_usuario(apps, schema_editor):
    Usuario = apps.get_model('cuentas', 'Usuario')
    AutoBetConfig = apps.get_model('auto_betting', 'AutoBetConfig')
    AutoBet = apps.get_model('auto_betting', 'AutoBet')
    DailyCounter = apps.get_model('auto_betting', 'DailyCounter')
    HistorialApuesta = apps.get_model('auto_betting', 'HistorialApuesta')

    owner = Usuario.objects.filter(is_superuser=True).order_by('id').first()
    if not owner:
        owner = Usuario.objects.order_by('id').first()
    if not owner:
        return

    AutoBetConfig.objects.filter(usuario__isnull=True).update(usuario=owner)
    AutoBet.objects.filter(usuario__isnull=True).update(usuario=owner)
    DailyCounter.objects.filter(usuario__isnull=True).update(usuario=owner)
    HistorialApuesta.objects.filter(usuario__isnull=True).update(usuario=owner)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('auto_betting', '0005_rename_auto_bet_is_sys_date_idx_auto_bettin_is_syst_d6d74e_idx_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_usuario, noop),
    ]
