from django.conf import settings
from django.db import models

from core.managers import ParMagasinManager
from core.models import ModeleDeBase


class Fournisseur(ModeleDeBase):
    """Fournisseur (laboratoire de verres…), commun à tout le réseau."""

    nom = models.CharField(max_length=200, unique=True)
    pays = models.ForeignKey("reseau.Pays", on_delete=models.PROTECT, related_name="+")
    telephone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    adresse = models.TextField(blank=True)
    est_actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["nom"]
        verbose_name = "fournisseur"

    def __str__(self):
        return self.nom


class CommandeFournisseur(ModeleDeBase):
    """Commande passée par un magasin à un fournisseur pour les verres de ses clients.

    Chaque ligne correspond à une ligne d'une commande client : à la réception, la commande
    client peut être livrée.
    """

    class Statut(models.TextChoices):
        ENVOYEE = "envoyee", "Envoyée"
        RECUE = "recue", "Reçue"
        ANNULEE = "annulee", "Annulée"

    magasin = models.ForeignKey("reseau.Magasin", on_delete=models.PROTECT, related_name="+")
    numero = models.CharField(max_length=40, unique=True)
    annee = models.PositiveSmallIntegerField()
    sequence = models.PositiveIntegerField()
    fournisseur = models.ForeignKey(Fournisseur, on_delete=models.PROTECT, related_name="commandes")
    reference_fournisseur = models.CharField(
        max_length=60, blank=True, help_text="N° donné par le fournisseur."
    )
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.ENVOYEE)
    passee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    recue_le = models.DateTimeField(null=True, blank=True)
    recue_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )

    objects = ParMagasinManager()
    tous = models.Manager()

    class Meta:
        ordering = ["-cree_le"]
        verbose_name = "commande fournisseur"
        verbose_name_plural = "commandes fournisseurs"
        constraints = [
            models.UniqueConstraint(
                fields=["magasin", "annee", "sequence"], name="commande_fournisseur_sans_doublon"
            )
        ]

    def __str__(self):
        return self.numero


class LigneCommandeFournisseur(models.Model):
    commande = models.ForeignKey(
        CommandeFournisseur, on_delete=models.PROTECT, related_name="lignes"
    )
    ligne_vente = models.ForeignKey(
        "ventes.LigneVente", on_delete=models.PROTECT, related_name="commandes_fournisseur"
    )
    article = models.ForeignKey("stock.Article", on_delete=models.PROTECT, related_name="+")
    quantite = models.PositiveIntegerField()
    details = models.CharField(
        max_length=300, blank=True, help_text="Œil, correction, traitement… pour le fournisseur."
    )

    class Meta:
        verbose_name = "ligne de commande fournisseur"

    def __str__(self):
        return f"{self.quantite} × {self.article}"
