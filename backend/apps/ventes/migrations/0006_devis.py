import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

from core import rls

MONTANT = {"decimal_places": 3, "max_digits": 14}

TABLES = {
    "ventes_devis": "optilink_magasin_visible(magasin_id)",
    # Les lignes suivent leur devis (la sous-requête est elle-même filtrée).
    "ventes_lignedevis": "EXISTS (SELECT 1 FROM ventes_devis d WHERE d.id = devis_id)",
}


def cloisonner(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        for table, condition in TABLES.items():
            schema_editor.execute(rls.activer(table, condition))


def decloisonner(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        for table in TABLES:
            schema_editor.execute(rls.desactiver(table))


class Migration(migrations.Migration):
    dependencies = [
        ("ventes", "0005_droits_factures"),
        ("crm", "0003_matricule_fiscal"),
        ("optique", "0003_identifiant_prescripteur"),
        ("stock", "0003_droits_parametrage"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            "compteurfacture",
            "type_document",
            models.CharField(
                choices=[("ticket", "Ticket de caisse"), ("facture", "Facture"), ("devis", "Devis")],
                max_length=10,
            ),
        ),
        migrations.CreateModel(
            name="Devis",
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
                ("valable_jusqu_au", models.DateField()),
                (
                    "statut",
                    models.CharField(
                        choices=[("en_cours", "En cours"), ("accepte", "Accepté"), ("refuse", "Refusé"), ("encaisse", "Encaissé")],
                        default="en_cours",
                        max_length=10,
                    ),
                ),
                ("remarques", models.TextField(blank=True)),
                ("client", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="devis", to="crm.client")),
                ("etabli_par", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("magasin", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="reseau.magasin")),
                (
                    "prescription",
                    models.ForeignKey(
                        blank=True,
                        help_text="Ordonnance du client sur laquelle s'appuie le devis.",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="devis",
                        to="optique.prescription",
                    ),
                ),
                (
                    "vente",
                    models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="devis", to="ventes.vente"),
                ),
            ],
            options={"verbose_name": "devis", "verbose_name_plural": "devis", "ordering": ["-cree_le"]},
        ),
        migrations.AddConstraint(
            "devis",
            models.UniqueConstraint(fields=("magasin", "annee", "sequence"), name="devis_numerote_sans_doublon"),
        ),
        migrations.CreateModel(
            name="LigneDevis",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("libelle", models.CharField(max_length=200)),
                (
                    "oeil",
                    models.CharField(
                        blank=True,
                        choices=[("od", "Œil droit"), ("og", "Œil gauche")],
                        help_text="Pour un verre ou une lentille.",
                        max_length=2,
                    ),
                ),
                ("quantite", models.PositiveIntegerField()),
                ("prix_unitaire_ttc", models.DecimalField(**MONTANT)),
                ("remise_pct", models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ("taux_tva", models.DecimalField(decimal_places=2, max_digits=5)),
                ("total_ttc", models.DecimalField(**MONTANT)),
                ("article", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="stock.article")),
                ("devis", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="lignes", to="ventes.devis")),
            ],
            options={"verbose_name": "ligne de devis"},
        ),
        migrations.RunPython(cloisonner, decloisonner),
    ]
