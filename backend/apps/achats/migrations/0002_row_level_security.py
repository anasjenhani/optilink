from django.db import migrations

from core import rls

TABLES = {
    "achats_commandefournisseur": "optilink_magasin_visible(magasin_id)",
    # Les lignes suivent leur commande (la sous-requête est elle-même filtrée).
    "achats_lignecommandefournisseur": (
        "EXISTS (SELECT 1 FROM achats_commandefournisseur c WHERE c.id = commande_id)"
    ),
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
    dependencies = [("achats", "0001_initial"), ("ventes", "0003_row_level_security")]

    operations = [migrations.RunPython(cloisonner, decloisonner)]
