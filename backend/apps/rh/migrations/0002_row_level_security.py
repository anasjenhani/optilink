from django.db import migrations

from core import rls

TABLES = {
    "rh_employe": "optilink_magasin_visible(magasin_id)",
    "rh_pointage": "optilink_magasin_visible(magasin_id)",
    "rh_demandeconge": "optilink_magasin_visible(magasin_id)",
}


def cloisonner(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        for table, condition in TABLES.items():
            schema_editor.execute(rls.activer(table, condition))


def decloisonner(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        for table in TABLES:
            schema_editor.execute(rls.desactiver(table))


class Migration(migrations.Migration):
    dependencies = [("rh", "0001_initial"), ("tresorerie", "0002_row_level_security")]

    operations = [migrations.RunPython(cloisonner, decloisonner)]
