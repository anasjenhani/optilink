import django.db.models.deletion
import uuid

from django.conf import settings
from django.db import migrations, models

from core import rls

MONTANT = {"decimal_places": 3, "max_digits": 14}
TYPES = [("ticket", "Ticket de caisse"), ("facture", "Facture")]


def completer(apps, schema_editor):
    Vente = apps.get_model("ventes", "Vente")
    for vente in Vente.objects.select_related("magasin__pays"):
        vente.devise = vente.magasin.pays.devise
        vente.save(update_fields=["devise"])


def cloisonner_factures(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(rls.activer("ventes_facture", "optilink_magasin_visible(magasin_id)"))


def decloisonner_factures(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(rls.desactiver("ventes_facture"))


class Migration(migrations.Migration):
    dependencies = [
        ("ventes", "0003_row_level_security"),
        ("reseau", "0002_pays"),
        ("crm", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Montants à 3 décimales (dinar) et devise du magasin sur chaque vente.
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
        migrations.RunPython(completer, migrations.RunPython.noop),
        migrations.AlterField("vente", "numero", models.CharField(help_text="N° de ticket.", max_length=40, unique=True)),
        migrations.AddField(
            "vente", "client",
            models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="ventes", to="crm.client"),
        ),
        # Tickets et factures : une suite de numéros chacun ; les compteurs existants sont des tickets.
        migrations.AddField(
            "compteurfacture", "type_document",
            models.CharField(choices=TYPES, default="ticket", max_length=10),
            preserve_default=False,
        ),
        migrations.RemoveConstraint("compteurfacture", "compteur_unique_par_annee"),
        migrations.AddConstraint(
            "compteurfacture",
            models.UniqueConstraint(fields=("magasin", "annee", "type_document"), name="compteur_unique_par_annee"),
        ),
        migrations.CreateModel(
            name="Facture",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("cree_le", models.DateTimeField(auto_now_add=True)),
                ("modifie_le", models.DateTimeField(auto_now=True)),
                ("numero", models.CharField(max_length=40, unique=True)),
                ("annee", models.PositiveSmallIntegerField()),
                ("sequence", models.PositiveIntegerField()),
                ("devise", models.CharField(max_length=3)),
                ("total_ht", models.DecimalField(**MONTANT)),
                ("total_tva", models.DecimalField(**MONTANT)),
                ("total_ttc", models.DecimalField(**MONTANT)),
                ("timbre_fiscal", models.DecimalField(decimal_places=3, default=0, max_digits=10)),
                ("net_a_payer", models.DecimalField(help_text="Total TTC + droit de timbre.", **MONTANT)),
                ("mode_paiement_timbre", models.CharField(blank=True, help_text="Comment le client a réglé le timbre.", max_length=20)),
                ("client", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="factures", to="crm.client")),
                ("emise_par", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("magasin", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="reseau.magasin")),
                ("vente", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="facture", to="ventes.vente")),
            ],
            options={"verbose_name": "facture", "ordering": ["-cree_le"]},
        ),
        migrations.AddConstraint(
            "facture",
            models.UniqueConstraint(fields=("magasin", "annee", "sequence"), name="facture_numerotee_sans_doublon"),
        ),
        migrations.RunPython(cloisonner_factures, decloisonner_factures),
    ]
