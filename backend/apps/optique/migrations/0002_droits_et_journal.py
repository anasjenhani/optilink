from django.db import migrations

from apps.securite.roles import PERMISSIONS_CLIENTS_OPTIQUE, ajouter_aux_roles_existants


def ajouter_droits(apps, schema_editor):
    ajouter_aux_roles_existants(apps, PERMISSIONS_CLIENTS_OPTIQUE)


def verrouiller_journal(apps, schema_editor):
    # Même verrou que les journaux de sécurité (securite 0003) : ni UPDATE ni DELETE.
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        "DROP TRIGGER IF EXISTS ajout_seul ON optique_accesprescription;"
        "CREATE TRIGGER ajout_seul BEFORE UPDATE OR DELETE ON optique_accesprescription "
        "FOR EACH ROW EXECUTE FUNCTION optilink_journal_en_ajout_seul();"
    )


def deverrouiller_journal(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("DROP TRIGGER IF EXISTS ajout_seul ON optique_accesprescription")


class Migration(migrations.Migration):
    dependencies = [
        ("optique", "0001_initial"),
        ("crm", "0001_initial"),
        ("securite", "0003_journaux_en_ajout_seul"),
        ("ventes", "0002_droits_des_roles"),
    ]

    operations = [
        migrations.RunPython(ajouter_droits, migrations.RunPython.noop),
        migrations.RunPython(verrouiller_journal, deverrouiller_journal),
    ]
