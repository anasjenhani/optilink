from django.db import migrations

from apps.securite.roles import PERMISSIONS_CAISSE_STOCK, ajouter_aux_roles_existants


def ajouter(apps, schema_editor):
    ajouter_aux_roles_existants(apps, PERMISSIONS_CAISSE_STOCK)


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("securite", "0002_evenement_securite"),
        ("stock", "0001_initial"),
        ("ventes", "0001_initial"),
    ]

    operations = [migrations.RunPython(ajouter, migrations.RunPython.noop)]
