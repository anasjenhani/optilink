from django.conf import settings
from django.db import models

from core.managers import ParMagasinManager
from core.models import ModeleDeBase


class TypeDocument(models.TextChoices):
    TICKET = "ticket", "Ticket de caisse"
    FACTURE = "facture", "Facture"


# Préfixe du numéro : M01-T2026-000001 pour un ticket, M01-F2026-000001 pour une facture.
PREFIXES = {TypeDocument.TICKET: "T", TypeDocument.FACTURE: "F"}


class CompteurFacture(models.Model):
    """Dernier numéro attribué par magasin, année et type de document (numérotation sans trou).

    Tickets et factures ont chacun leur suite.
    """

    magasin = models.ForeignKey("reseau.Magasin", on_delete=models.PROTECT, related_name="+")
    annee = models.PositiveSmallIntegerField()
    type_document = models.CharField(max_length=10, choices=TypeDocument.choices)
    dernier = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "compteur de factures"
        constraints = [
            models.UniqueConstraint(
                fields=["magasin", "annee", "type_document"], name="compteur_unique_par_annee"
            )
        ]

    def __str__(self):
        return f"{self.magasin_id}/{self.annee}/{self.type_document} : {self.dernier}"


class Vente(ModeleDeBase):
    """Vente encaissée et facturée. Jamais modifiée : une correction passera par un avoir."""

    magasin = models.ForeignKey("reseau.Magasin", on_delete=models.PROTECT, related_name="+")
    type_document = models.CharField(
        max_length=10, choices=TypeDocument.choices, default=TypeDocument.TICKET
    )
    numero = models.CharField(max_length=40, unique=True)
    annee = models.PositiveSmallIntegerField()
    sequence = models.PositiveIntegerField()
    client = models.ForeignKey(
        "crm.Client",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ventes",
        help_text="Obligatoire pour une facture.",
    )
    vendeur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    devise = models.CharField(max_length=3, help_text="Monnaie du pays du magasin à la vente.")
    total_ht = models.DecimalField(max_digits=14, decimal_places=3)
    total_tva = models.DecimalField(max_digits=14, decimal_places=3)
    total_ttc = models.DecimalField(max_digits=14, decimal_places=3)
    timbre_fiscal = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=0,
        help_text="Droit de timbre du pays, sur les factures seulement.",
    )
    net_a_payer = models.DecimalField(
        max_digits=14, decimal_places=3, help_text="Total TTC + droit de timbre."
    )

    objects = ParMagasinManager()
    tous = models.Manager()

    class Meta:
        ordering = ["-cree_le"]
        verbose_name = "vente"
        permissions = [("appliquer_remise", "Peut appliquer une remise")]
        constraints = [
            models.UniqueConstraint(
                fields=["magasin", "annee", "type_document", "sequence"],
                name="facture_sans_doublon",
            ),
            models.CheckConstraint(
                name="facture_avec_client",
                condition=~models.Q(type_document="facture") | models.Q(client__isnull=False),
            ),
        ]

    def __str__(self):
        return self.numero


class LigneVente(models.Model):
    vente = models.ForeignKey(Vente, on_delete=models.PROTECT, related_name="lignes")
    article = models.ForeignKey("stock.Article", on_delete=models.PROTECT, related_name="+")
    libelle = models.CharField(max_length=200)
    quantite = models.PositiveIntegerField()
    prix_unitaire_ttc = models.DecimalField(max_digits=14, decimal_places=3)
    remise_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    taux_tva = models.DecimalField(max_digits=5, decimal_places=2)
    total_ttc = models.DecimalField(max_digits=14, decimal_places=3)

    class Meta:
        verbose_name = "ligne de vente"

    def __str__(self):
        return f"{self.quantite} × {self.libelle}"


class Paiement(models.Model):
    class Mode(models.TextChoices):
        CARTE = "carte", "Carte bancaire"
        ESPECES = "especes", "Espèces"
        CHEQUE = "cheque", "Chèque"

    vente = models.ForeignKey(Vente, on_delete=models.PROTECT, related_name="paiements")
    mode = models.CharField(max_length=20, choices=Mode.choices)
    montant = models.DecimalField(max_digits=14, decimal_places=3)

    class Meta:
        verbose_name = "paiement"

    def __str__(self):
        return f"{self.get_mode_display()} {self.montant}"
