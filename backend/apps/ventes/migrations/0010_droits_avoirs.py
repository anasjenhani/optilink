from django.db import migrations

from apps.securite.roles import PERMISSIONS_AVOIRS, ajouter_aux_roles_existants


def ajouter(apps, schema_editor):
    ajouter_aux_roles_existants(apps, PERMISSIONS_AVOIRS)


class Migration(migrations.Migration):
    dependencies = [
        ("ventes", "0009_avoirs"),
        ("securite", "0002_evenement_securite"),
    ]

    operations = [migrations.RunPython(ajouter, migrations.RunPython.noop)]
