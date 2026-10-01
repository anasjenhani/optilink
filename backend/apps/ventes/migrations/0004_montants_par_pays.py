import django.db.models.deletion
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
        ("crm", "0001_initial"),
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
        # Tickets de caisse et factures : deux suites de numéros ; seules les factures portent
        # le timbre et exigent un client. Les ventes et compteurs existants sont des tickets.
        migrations.AddField(
            "compteurfacture", "type_document",
            models.CharField(choices=[("ticket", "Ticket de caisse"), ("facture", "Facture")], default="ticket", max_length=10),
            preserve_default=False,
        ),
        migrations.RemoveConstraint("compteurfacture", "compteur_unique_par_annee"),
        migrations.AddConstraint(
            "compteurfacture",
            models.UniqueConstraint(fields=("magasin", "annee", "type_document"), name="compteur_unique_par_annee"),
        ),
        migrations.AddField(
            "vente", "type_document",
            models.CharField(choices=[("ticket", "Ticket de caisse"), ("facture", "Facture")], default="ticket", max_length=10),
        ),
        migrations.AddField(
            "vente", "client",
            models.ForeignKey(blank=True, help_text="Obligatoire pour une facture.", null=True, on_delete=django.db.models.deletion.PROTECT, related_name="ventes", to="crm.client"),
        ),
        migrations.AlterField(
            "vente", "timbre_fiscal",
            models.DecimalField(decimal_places=3, default=0, help_text="Droit de timbre du pays, sur les factures seulement.", max_digits=10),
        ),
        migrations.RemoveConstraint("vente", "facture_sans_doublon"),
        migrations.AddConstraint(
            "vente",
            models.UniqueConstraint(fields=("magasin", "annee", "type_document", "sequence"), name="facture_sans_doublon"),
        ),
        migrations.AddConstraint(
            "vente",
            models.CheckConstraint(condition=models.Q(("type_document", "facture"), _negated=True) | models.Q(("client__isnull", False)), name="facture_avec_client"),
        ),
    ]
