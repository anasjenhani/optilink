from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("crm", "0002_magasins_lisibles_par_le_reseau")]

    operations = [
        migrations.AddField(
            model_name="client",
            name="matricule_fiscal",
            field=models.CharField(
                blank=True,
                help_text="Entreprise cliente : identifiant fiscal sur la facture.",
                max_length=30,
            ),
        ),
    ]
