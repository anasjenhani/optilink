from django.db import migrations

# Un client est partagé par le réseau et pointe vers son magasin d'origine, qui peut être hors du
# périmètre de l'utilisateur. La liste des magasins devient donc lisible par tous dans la base
# (ce n'est pas une donnée sensible) ; créer, modifier ou supprimer un magasin reste cloisonné.
# L'API, elle, ne liste toujours que les magasins du périmètre (ParMagasinManager).
LECTURE = """
DROP POLICY IF EXISTS lecture_reseau ON reseau_magasin;
CREATE POLICY lecture_reseau ON reseau_magasin FOR SELECT USING (true);
"""


def ouvrir(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(LECTURE)


def refermer(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("DROP POLICY IF EXISTS lecture_reseau ON reseau_magasin")


class Migration(migrations.Migration):
    dependencies = [
        ("crm", "0001_initial"),
        ("ventes", "0003_row_level_security"),
    ]

    operations = [migrations.RunPython(ouvrir, refermer)]
