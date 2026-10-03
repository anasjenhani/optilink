from django.db import migrations

from apps.securite.roles import PERMISSIONS_RH, ajouter_aux_roles_existants


def ajouter(apps, schema_editor):
    ajouter_aux_roles_existants(apps, PERMISSIONS_RH)


class Migration(migrations.Migration):
    dependencies = [("rh", "0002_row_level_security"), ("tresorerie", "0005_droits_banque")]

    operations = [migrations.RunPython(ajouter, migrations.RunPython.noop)]
