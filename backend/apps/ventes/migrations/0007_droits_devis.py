from django.db import migrations

from apps.securite.roles import PERMISSIONS_DEVIS, ajouter_aux_roles_existants


def ajouter(apps, schema_editor):
    ajouter_aux_roles_existants(apps, PERMISSIONS_DEVIS)


class Migration(migrations.Migration):
    dependencies = [
        ("ventes", "0006_devis"),
        ("securite", "0002_evenement_securite"),
    ]

    operations = [migrations.RunPython(ajouter, migrations.RunPython.noop)]
