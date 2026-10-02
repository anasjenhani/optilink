from django.db import migrations

# Journaux qu'aucune requête, même du propriétaire des tables, ne peut modifier ni supprimer.
JOURNAUX = ["securite_evenementsecurite", "auditlog_logentry"]

FONCTION = """
CREATE OR REPLACE FUNCTION optilink_journal_en_ajout_seul() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Le journal % est en ajout seul : % refusé.', TG_TABLE_NAME, TG_OP
        USING ERRCODE = 'insufficient_privilege';
END
$$;
"""


def verrouiller(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(FONCTION, params=None)  # le SQL contient des % de plpgsql
    for table in JOURNAUX:
        schema_editor.execute(
            f"DROP TRIGGER IF EXISTS ajout_seul ON {table};"
            f"CREATE TRIGGER ajout_seul BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION optilink_journal_en_ajout_seul();"
        )


def deverrouiller(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for table in JOURNAUX:
        schema_editor.execute(f"DROP TRIGGER IF EXISTS ajout_seul ON {table}")
    schema_editor.execute("DROP FUNCTION IF EXISTS optilink_journal_en_ajout_seul()")


class Migration(migrations.Migration):
    dependencies = [
        ("securite", "0002_evenement_securite"),
        ("auditlog", "0017_add_actor_email"),
    ]

    operations = [migrations.RunPython(verrouiller, deverrouiller)]
