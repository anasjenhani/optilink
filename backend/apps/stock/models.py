from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum

from core.managers import ParMagasinManager
from core.models import ModeleDeBase


class Article(ModeleDeBase):
    """Article du catalogue, commun à tout le réseau ; son prix dépend du pays (``PrixArticle``).

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
    est_actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["reference"]
        verbose_name = "article"

    def __str__(self):
        return f"{self.reference} {self.libelle}"


class PrixArticle(models.Model):
    """Prix de vente et TVA d'un article dans un pays, dans la monnaie de ce pays.

    Sans prix pour son pays, un article ne peut pas être vendu dans un magasin.
    """

    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="prix")
    pays = models.ForeignKey("reseau.Pays", on_delete=models.PROTECT, related_name="+")
    prix_vente_ttc = models.DecimalField(
        max_digits=14, decimal_places=3, validators=[MinValueValidator(Decimal("0"))]
    )
    taux_tva = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        verbose_name = "prix de vente"
        verbose_name_plural = "prix de vente"
        constraints = [models.UniqueConstraint(fields=["article", "pays"], name="un_prix_par_pays")]

    def __str__(self):
        return f"{self.article.reference} {self.prix_vente_ttc} {self.pays.devise}"

    def clean(self):
        if self.pays_id and not self.pays.taux_tva.filter(taux=self.taux_tva).exists():
            raise ValidationError({"taux_tva": "Taux de TVA inconnu dans ce pays."})
        prix = Decimal(self.prix_vente_ttc or 0)
        if self.pays_id and prix != prix.quantize(Decimal(1).scaleb(-self.pays.decimales)):
            raise ValidationError(
                {"prix_vente_ttc": f"{self.pays.devise} : {self.pays.decimales} décimales au plus."}
            )


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
