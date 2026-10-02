import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

from core import rls

MONTANT = {"decimal_places": 3, "max_digits": 14}

TABLES = {
    "ventes_avoir": "optilink_magasin_visible(magasin_id)",
    # Les lignes suivent leur avoir (la sous-requête est elle-même filtrée).
    "ventes_ligneavoir": "EXISTS (SELECT 1 FROM ventes_avoir a WHERE a.id = avoir_id)",
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
        ("ventes", "0008_commandes"),
        ("crm", "0003_matricule_fiscal"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            "compteurfacture",
            "type_document",
            models.CharField(
                choices=[
                    ("ticket", "Ticket de caisse"),
                    ("facture", "Facture"),
                    ("devis", "Devis"),
                    ("avoir", "Avoir"),
                ],
                max_length=10,
            ),
        ),
        migrations.AlterField(
            "vente",
            "statut",
            models.CharField(
                choices=[("en_commande", "En commande"), ("livree", "Livrée"), ("annulee", "Annulée")],
                default="livree",
                max_length=12,
            ),
        ),
        migrations.CreateModel(
            name="Avoir",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("cree_le", models.DateTimeField(auto_now_add=True)),
                ("modifie_le", models.DateTimeField(auto_now=True)),
                ("numero", models.CharField(max_length=40, unique=True)),
                ("annee", models.PositiveSmallIntegerField()),
                ("sequence", models.PositiveIntegerField()),
                ("annulation", models.BooleanField(default=False, help_text="Annule toute la vente.")),
                ("motif", models.CharField(max_length=300)),
                ("devise", models.CharField(max_length=3)),
                ("total_ht", models.DecimalField(**MONTANT)),
                ("total_tva", models.DecimalField(**MONTANT)),
                ("total_ttc", models.DecimalField(**MONTANT)),
                ("montant_rembourse", models.DecimalField(**MONTANT)),
                ("mode_remboursement", models.CharField(blank=True, max_length=20)),
                (
                    "client",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="avoirs", to="crm.client"),
                ),
                ("emis_par", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
                (
                    "facture",
                    models.ForeignKey(
                        blank=True,
                        help_text="Facture corrigée, si la vente avait été facturée.",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="avoirs",
                        to="ventes.facture",
                    ),
                ),
                ("magasin", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="reseau.magasin")),
                ("vente", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="avoirs", to="ventes.vente")),
            ],
            options={"verbose_name": "avoir", "ordering": ["-cree_le"]},
        ),
        migrations.AddConstraint(
            "avoir",
            models.UniqueConstraint(fields=("magasin", "annee", "sequence"), name="avoir_numerote_sans_doublon"),
        ),
        migrations.CreateModel(
            name="LigneAvoir",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("libelle", models.CharField(max_length=200)),
                ("quantite", models.PositiveIntegerField()),
                ("taux_tva", models.DecimalField(decimal_places=2, max_digits=5)),
                ("total_ttc", models.DecimalField(**MONTANT)),
                (
                    "remis_en_stock",
                    models.BooleanField(default=True, help_text="Faux pour un article défectueux ou fait sur mesure."),
                ),
                ("avoir", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="lignes", to="ventes.avoir")),
                ("ligne_vente", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="retours", to="ventes.lignevente")),
            ],
            options={"verbose_name": "ligne d'avoir"},
        ),
        migrations.RunPython(cloisonner, decloisonner),
    ]
