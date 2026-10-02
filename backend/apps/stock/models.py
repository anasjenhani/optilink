from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum

from core.managers import ParMagasinManager
from core.models import ModeleDeBase


class Article(ModeleDeBase):
    """Article du catalogue, commun à tout le réseau.

    Prototype : une seule table. Les familles recevront leurs tables spécialisées (monture,
    verre, lentille) au lot Vendre.
    """

    class Famille(models.TextChoices):
        MONTURE = "monture", "Monture"
        VERRE = "verre", "Verre"
        LENTILLE = "lentille", "Lentille"
        ACCESSOIRE = "accessoire", "Accessoire"

    reference = models.CharField(max_length=40, unique=True)
    libelle = models.CharField(max_length=200)
    famille = models.CharField(max_length=20, choices=Famille.choices)
    code_barres = models.CharField(max_length=40, blank=True, db_index=True)
    prix_vente_ttc = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0"))]
    )
    taux_tva = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("20.00"))
    est_actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["reference"]
        verbose_name = "article"

    def __str__(self):
        return f"{self.reference} {self.libelle}"


class MouvementStock(models.Model):
    """Entrée ou sortie d'un article dans un magasin. Le stock est la somme des mouvements."""

    class Type(models.TextChoices):
        RECEPTION = "reception", "Réception"
        VENTE = "vente", "Vente"
        RETOUR = "retour", "Retour client"
        AJUSTEMENT = "ajustement", "Ajustement d'inventaire"

    magasin = models.ForeignKey("reseau.Magasin", on_delete=models.PROTECT, related_name="+")
    article = models.ForeignKey(Article, on_delete=models.PROTECT, related_name="mouvements")
    quantite = models.IntegerField(help_text="Positive en entrée, négative en sortie.")
    type = models.CharField(max_length=20, choices=Type.choices)
    horodatage = models.DateTimeField(auto_now_add=True, db_index=True)
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+"
    )
    reference = models.CharField(max_length=60, blank=True, help_text="Pièce d'origine.")

    objects = ParMagasinManager()
    tous = models.Manager()  # noqa: DJ012 (manager non filtré, pris à tort pour un champ)

    class Meta:
        verbose_name = "mouvement de stock"
        verbose_name_plural = "mouvements de stock"
        indexes = [models.Index(fields=["magasin", "article"])]
        constraints = [
            models.CheckConstraint(
                name="mouvement_quantite_non_nulle", condition=~models.Q(quantite=0)
            )
        ]

    def __str__(self):
        return f"{self.get_type_display()} {self.quantite:+d} {self.article}"


def stock_disponible(magasin, article):
    total = MouvementStock.tous.filter(magasin=magasin, article=article).aggregate(
        total=Sum("quantite")
    )["total"]
    return total or 0
