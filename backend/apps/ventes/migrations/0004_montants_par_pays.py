from django.db import migrations, models

MONTANT = {"decimal_places": 3, "max_digits": 14}


def completer(apps, schema_editor):
    Vente = apps.get_model("ventes", "Vente")
    for vente in Vente.objects.select_related("magasin__pays"):
        vente.devise = vente.magasin.pays.devise
        vente.net_a_payer = vente.total_ttc
        vente.save(update_fields=["devise", "net_a_payer"])


class Migration(migrations.Migration):
    dependencies = [
        ("ventes", "0003_row_level_security"),
        ("reseau", "0002_pays"),
    ]

    operations = [
        migrations.AlterField("vente", "total_ht", models.DecimalField(**MONTANT)),
        migrations.AlterField("vente", "total_tva", models.DecimalField(**MONTANT)),
        migrations.AlterField("vente", "total_ttc", models.DecimalField(**MONTANT)),
        migrations.AlterField("lignevente", "prix_unitaire_ttc", models.DecimalField(**MONTANT)),
        migrations.AlterField("lignevente", "total_ttc", models.DecimalField(**MONTANT)),
        migrations.AlterField("paiement", "montant", models.DecimalField(**MONTANT)),
        migrations.AddField(
            "vente", "devise",
            models.CharField(default="", help_text="Monnaie du pays du magasin à la vente.", max_length=3),
            preserve_default=False,
        ),
        migrations.AddField(
            "vente", "timbre_fiscal",
            models.DecimalField(decimal_places=3, default=0, help_text="Droit de timbre du pays.", max_digits=10),
        ),
        migrations.AddField(
            "vente", "net_a_payer",
            models.DecimalField(default=0, help_text="Total TTC + droit de timbre.", **MONTANT),
            preserve_default=False,
        ),
        migrations.RunPython(completer, migrations.RunPython.noop),
    ]
