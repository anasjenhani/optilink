from django.db import migrations, models


def verres_sur_commande(apps, schema_editor):
    apps.get_model("stock", "Article").objects.filter(famille="verre").update(sur_commande=True)


class Migration(migrations.Migration):
    dependencies = [("stock", "0003_droits_parametrage")]

    operations = [
        migrations.AddField(
            "article",
            "sur_commande",
            models.BooleanField(
                default=False,
                help_text="Commandé au fournisseur pour chaque client (verres…) : hors stock du magasin.",
            ),
        ),
        migrations.RunPython(verres_sur_commande, migrations.RunPython.noop),
    ]
