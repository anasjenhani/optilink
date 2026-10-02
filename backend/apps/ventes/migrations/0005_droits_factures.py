from django.db import migrations

from apps.securite.roles import PERMISSIONS_FACTURES, ajouter_aux_roles_existants


def ajouter(apps, schema_editor):
    ajouter_aux_roles_existants(apps, PERMISSIONS_FACTURES)


class Migration(migrations.Migration):
    dependencies = [
        ("ventes", "0004_montants_par_pays"),
        ("securite", "0002_evenement_securite"),
    ]

    operations = [migrations.RunPython(ajouter, migrations.RunPython.noop)]
