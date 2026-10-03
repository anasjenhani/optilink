from django.db import migrations

from apps.securite.roles import PERMISSIONS_TRESORERIE, ajouter_aux_roles_existants


def ajouter(apps, schema_editor):
    ajouter_aux_roles_existants(apps, PERMISSIONS_TRESORERIE)


class Migration(migrations.Migration):
    dependencies = [
        ("tresorerie", "0002_row_level_security"),
        ("securite", "0005_profils"),
    ]

    operations = [migrations.RunPython(ajouter, migrations.RunPython.noop)]
