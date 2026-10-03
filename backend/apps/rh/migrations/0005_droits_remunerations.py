from django.db import migrations

from apps.securite.roles import PERMISSIONS_REMUNERATIONS, ajouter_aux_roles_existants


def ajouter(apps, schema_editor):
    ajouter_aux_roles_existants(apps, PERMISSIONS_REMUNERATIONS)


def cloisonner(apps, schema_editor):
    from core import rls

    if schema_editor.connection.vendor == "postgresql":
        for table in ("rh_acompte", "rh_prime"):
            schema_editor.execute(rls.activer(table, "optilink_magasin_visible(magasin_id)"))


def decloisonner(apps, schema_editor):
    from core import rls

    if schema_editor.connection.vendor == "postgresql":
        for table in ("rh_acompte", "rh_prime"):
            schema_editor.execute(rls.desactiver(table))


class Migration(migrations.Migration):
    dependencies = [("rh", "0004_acomptes_et_primes")]

    operations = [
        migrations.RunPython(cloisonner, decloisonner),
        migrations.RunPython(ajouter, migrations.RunPython.noop),
    ]
