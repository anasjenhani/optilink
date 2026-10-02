from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("optique", "0002_droits_et_journal")]

    operations = [
        migrations.RenameField("prescription", "prescripteur_rpps", "prescripteur_identifiant"),
        migrations.AlterField(
            "prescription",
            "prescripteur_identifiant",
            models.CharField(
                blank=True,
                help_text="Selon le pays : n° d'inscription à l'Ordre des médecins, n° RPPS…",
                max_length=30,
            ),
        ),
    ]
