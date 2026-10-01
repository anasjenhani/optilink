from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.managers import ParMagasinManager
from core.models import ModeleDeBase


class TypeDocument(models.TextChoices):
    TICKET = "ticket", "Ticket de caisse"
    FACTURE = "facture", "Facture"
    DEVIS = "devis", "Devis"


# Préfixe du numéro : M01-T2026-000001 pour un ticket, M01-F2026-000001 pour une facture,
# M01-D2026-000001 pour un devis. Chaque type de document a sa propre suite de numéros.
PREFIXES = {TypeDocument.TICKET: "T", TypeDocument.FACTURE: "F", TypeDocument.DEVIS: "D"}


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
    """Vente enregistrée en caisse, avec son ticket. Jamais modifiée : une correction passera
    par un avoir.

    Une vente est soit remise tout de suite (payée en totalité), soit une **commande** : le
    client verse un acompte, l'équipement est préparé (verres commandés au fournisseur), puis
    il est livré contre le solde. La facture est une étape à part (``Facture``), possible
    seulement quand la vente est entièrement payée.
    """

    class Statut(models.TextChoices):
        EN_COMMANDE = "en_commande", "En commande"
        LIVREE = "livree", "Livrée"

    magasin = models.ForeignKey("reseau.Magasin", on_delete=models.PROTECT, related_name="+")
    numero = models.CharField(max_length=40, unique=True, help_text="N° de ticket.")
    annee = models.PositiveSmallIntegerField()
    sequence = models.PositiveIntegerField()
    client = models.ForeignKey(
        "crm.Client", on_delete=models.PROTECT, null=True, blank=True, related_name="ventes"
    )
    vendeur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    devise = models.CharField(max_length=3, help_text="Monnaie du pays du magasin à la vente.")
    total_ht = models.DecimalField(max_digits=14, decimal_places=3)
    total_tva = models.DecimalField(max_digits=14, decimal_places=3)
    total_ttc = models.DecimalField(max_digits=14, decimal_places=3)
    statut = models.CharField(max_length=12, choices=Statut.choices, default=Statut.LIVREE)
    livraison_prevue_le = models.DateField(null=True, blank=True)
    livree_le = models.DateTimeField(null=True, blank=True)
    livree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )

    objects = ParMagasinManager()
    tous = models.Manager()

    class Meta:
        ordering = ["-cree_le"]
        verbose_name = "vente"
        permissions = [("appliquer_remise", "Peut appliquer une remise")]
        constraints = [
            models.UniqueConstraint(
                fields=["magasin", "annee", "sequence"], name="facture_sans_doublon"
            )
        ]

    def __str__(self):
        return self.numero

    @property
    def reste_a_payer(self):
        paye = sum((p.montant for p in self.paiements.all()), Decimal("0"))
        return self.total_ttc - paye


class Facture(ModeleDeBase):
    """Facture émise à part, au nom d'un client, pour une vente entièrement payée.

    Numérotée sans trou par magasin et par année (suite distincte des tickets), jamais modifiée.
    Elle porte le droit de timbre du pays.
    """

    magasin = models.ForeignKey("reseau.Magasin", on_delete=models.PROTECT, related_name="+")
    vente = models.OneToOneField(Vente, on_delete=models.PROTECT, related_name="facture")
    client = models.ForeignKey("crm.Client", on_delete=models.PROTECT, related_name="factures")
    numero = models.CharField(max_length=40, unique=True)
    annee = models.PositiveSmallIntegerField()
    sequence = models.PositiveIntegerField()
    devise = models.CharField(max_length=3)
    total_ht = models.DecimalField(max_digits=14, decimal_places=3)
    total_tva = models.DecimalField(max_digits=14, decimal_places=3)
    total_ttc = models.DecimalField(max_digits=14, decimal_places=3)
    timbre_fiscal = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    net_a_payer = models.DecimalField(
        max_digits=14, decimal_places=3, help_text="Total TTC + droit de timbre."
    )
    mode_paiement_timbre = models.CharField(
        max_length=20, blank=True, help_text="Comment le client a réglé le timbre."
    )
    emise_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )

    objects = ParMagasinManager()
    tous = models.Manager()

    class Meta:
        ordering = ["-cree_le"]
        verbose_name = "facture"
        constraints = [
            models.UniqueConstraint(
                fields=["magasin", "annee", "sequence"], name="facture_numerotee_sans_doublon"
            )
        ]

    def __str__(self):
        return self.numero


class Devis(ModeleDeBase):
    """Devis d'équipement remis à un client, avec ses prix figés jusqu'à la date de validité.

    Il peut s'appuyer sur une ordonnance du client. Accepté, il s'encaisse en caisse au prix
    du devis, même si le tarif a changé entre-temps. Ses lignes ne se modifient pas : une
    autre proposition est un nouveau devis.
    """

    class Statut(models.TextChoices):
        EN_COURS = "en_cours", "En cours"
        ACCEPTE = "accepte", "Accepté"
        REFUSE = "refuse", "Refusé"
        ENCAISSE = "encaisse", "Encaissé"

    magasin = models.ForeignKey("reseau.Magasin", on_delete=models.PROTECT, related_name="+")
    numero = models.CharField(max_length=40, unique=True)
    annee = models.PositiveSmallIntegerField()
    sequence = models.PositiveIntegerField()
    client = models.ForeignKey("crm.Client", on_delete=models.PROTECT, related_name="devis")
    prescription = models.ForeignKey(
        "optique.Prescription",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="devis",
        help_text="Ordonnance du client sur laquelle s'appuie le devis.",
    )
    etabli_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    devise = models.CharField(max_length=3)
    total_ht = models.DecimalField(max_digits=14, decimal_places=3)
    total_tva = models.DecimalField(max_digits=14, decimal_places=3)
    total_ttc = models.DecimalField(max_digits=14, decimal_places=3)
    valable_jusqu_au = models.DateField()
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.EN_COURS)
    vente = models.OneToOneField(
        Vente, on_delete=models.PROTECT, null=True, blank=True, related_name="devis"
    )
    remarques = models.TextField(blank=True)

    objects = ParMagasinManager()
    tous = models.Manager()

    class Meta:
        ordering = ["-cree_le"]
        verbose_name = "devis"
        verbose_name_plural = "devis"
        constraints = [
            models.UniqueConstraint(
                fields=["magasin", "annee", "sequence"], name="devis_numerote_sans_doublon"
            )
        ]

    def __str__(self):
        return self.numero


class LigneDevis(models.Model):
    class Oeil(models.TextChoices):
        DROIT = "od", "Œil droit"
        GAUCHE = "og", "Œil gauche"

    devis = models.ForeignKey(Devis, on_delete=models.PROTECT, related_name="lignes")
    article = models.ForeignKey("stock.Article", on_delete=models.PROTECT, related_name="+")
    libelle = models.CharField(max_length=200)
    oeil = models.CharField(
        max_length=2, choices=Oeil.choices, blank=True, help_text="Pour un verre ou une lentille."
    )
    quantite = models.PositiveIntegerField()
    prix_unitaire_ttc = models.DecimalField(max_digits=14, decimal_places=3)
    remise_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    taux_tva = models.DecimalField(max_digits=5, decimal_places=2)
    total_ttc = models.DecimalField(max_digits=14, decimal_places=3)

    class Meta:
        verbose_name = "ligne de devis"

    def __str__(self):
        return f"{self.quantite} × {self.libelle}"


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
    """Règlement reçu : tout le prix en caisse, ou acompte puis solde pour une commande."""

    class Mode(models.TextChoices):
        CARTE = "carte", "Carte bancaire"
        ESPECES = "especes", "Espèces"
        CHEQUE = "cheque", "Chèque"

    vente = models.ForeignKey(Vente, on_delete=models.PROTECT, related_name="paiements")
    mode = models.CharField(max_length=20, choices=Mode.choices)
    montant = models.DecimalField(max_digits=14, decimal_places=3)
    recu_le = models.DateTimeField(default=timezone.now)
    recu_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+"
    )

    class Meta:
        verbose_name = "paiement"

    def __str__(self):
        return f"{self.get_mode_display()} {self.montant}"
