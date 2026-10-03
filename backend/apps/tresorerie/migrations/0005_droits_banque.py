from django.db import migrations

from apps.securite.roles import PERMISSIONS_BANQUE, ajouter_aux_roles_existants


def ajouter(apps, schema_editor):
    ajouter_aux_roles_existants(apps, PERMISSIONS_BANQUE)


class Migration(migrations.Migration):
    dependencies = [("tresorerie", "0004_banque_et_versements")]

    operations = [migrations.RunPython(ajouter, migrations.RunPython.noop)]
