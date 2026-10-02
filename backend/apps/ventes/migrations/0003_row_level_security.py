from django.db import migrations

from core import rls

# Table -> condition de visibilité d'une ligne.
TABLES = {
    "reseau_magasin": "optilink_magasin_visible(id)",
    "stock_mouvementstock": "optilink_magasin_visible(magasin_id)",
    "ventes_compteurfacture": "optilink_magasin_visible(magasin_id)",
    "ventes_vente": "optilink_magasin_visible(magasin_id)",
    # Les lignes et paiements suivent leur vente (la sous-requête est elle-même filtrée).
    "ventes_lignevente": "EXISTS (SELECT 1 FROM ventes_vente v WHERE v.id = vente_id)",
    "ventes_paiement": "EXISTS (SELECT 1 FROM ventes_vente v WHERE v.id = vente_id)",
}


def activer(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(rls.FONCTION)
    for table, condition in TABLES.items():
        schema_editor.execute(rls.activer(table, condition))


def desactiver(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for table in TABLES:
        schema_editor.execute(rls.desactiver(table))
    schema_editor.execute("DROP FUNCTION IF EXISTS optilink_magasin_visible(bigint)")


class Migration(migrations.Migration):
    dependencies = [
        ("reseau", "0001_initial"),
        ("stock", "0001_initial"),
        ("ventes", "0002_droits_des_roles"),
    ]

    operations = [migrations.RunPython(activer, desactiver)]
