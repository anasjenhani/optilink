from django.db import migrations

from apps.securite.roles import PERMISSIONS_PARAMETRAGE, ajouter_aux_roles_existants


def ajouter(apps, schema_editor):
    ajouter_aux_roles_existants(apps, PERMISSIONS_PARAMETRAGE)


class Migration(migrations.Migration):
    dependencies = [
        ("stock", "0002_prix_par_pays"),
        ("reseau", "0002_pays"),
        ("securite", "0002_evenement_securite"),
    ]

    operations = [migrations.RunPython(ajouter, migrations.RunPython.noop)]
