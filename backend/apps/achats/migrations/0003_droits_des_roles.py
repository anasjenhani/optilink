from django.db import migrations

from apps.securite.roles import PERMISSIONS_ACHATS, ajouter_aux_roles_existants


def ajouter(apps, schema_editor):
    ajouter_aux_roles_existants(apps, PERMISSIONS_ACHATS)


class Migration(migrations.Migration):
    dependencies = [
        ("achats", "0002_row_level_security"),
        ("securite", "0002_evenement_securite"),
    ]

    operations = [migrations.RunPython(ajouter, migrations.RunPython.noop)]
