from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Sum

from core.managers import ParMagasinManager
from core.models import ModeleDeBase


class Article(ModeleDeBase):
    """Article du catalogue, commun à tout le réseau ; son prix dépend du pays (``PrixArticle``).

    Montures, verres et lentilles ont leurs caractéristiques dans une table à part
    (``Monture``, ``Verre``, ``Lentille``) ; les articles divers (étuis, produits d'entretien…)
    n'ont que leur libellé.
    """

    class Famille(models.TextChoices):
        MONTURE = "monture", "Monture"
        VERRE = "verre", "Verre"
        LENTILLE = "lentille", "Lentille"
        DIVERS = "divers", "Divers"

    reference = models.CharField(max_length=40, unique=True)
    libelle = models.CharField(max_length=200)
    famille = models.CharField(max_length=20, choices=Famille.choices)
    code_barres = models.CharField(max_length=40, blank=True, db_index=True)
    fournisseur = models.ForeignKey(
        "achats.Fournisseur",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="articles",
    )
    reference_fournisseur = models.CharField(
        max_length=60, blank=True, help_text="Référence de l'article chez le fournisseur."
    )
    sur_commande = models.BooleanField(
        default=False,
        help_text=(
            "Commandé au fournisseur pour chaque client (verre à commander) : hors stock du "
            "magasin. Décoché, l'article se vend sur le stock (verre de stock, monture…)."
        ),
    )
    est_actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["reference"]
        verbose_name = "article"
        constraints = [
            models.UniqueConstraint(
                fields=["code_barres"],
                condition=~models.Q(code_barres=""),
                name="code_barres_unique",
                violation_error_message="Ce code-barres est déjà celui d'un autre article.",
            )
        ]

    def __str__(self):
        return f"{self.reference} {self.libelle}"

    def clean(self):
        if self.pk is None:
            return
        for famille in (self.Famille.MONTURE, self.Famille.VERRE, self.Famille.LENTILLE):
            if (
                famille != self.famille
                and type(self).objects.filter(pk=self.pk, **{f"{famille}__isnull": False}).exists()
            ):
                raise ValidationError(
                    {"famille": f"L'article a une fiche {famille} : il reste dans cette famille."}
                )

    @property
    def caracteristiques(self):
        """Fiche de la famille de l'article (``Monture``, ``Verre``, ``Lentille``), ou None."""
        if self.famille == self.Famille.DIVERS:
            return None
        return getattr(self, self.famille, None)


class Caracteristiques(models.Model):
    """Fiche propre à une famille, rattachée à un seul article de cette famille."""

    famille = None
    article = models.OneToOneField(Article, on_delete=models.CASCADE, primary_key=True)
    marque = models.CharField(max_length=100, blank=True, db_index=True)

    class Meta:
        abstract = True

    def clean(self):
        if self.article_id and self.article.famille != self.famille:
            raise ValidationError(
                f"Ces caractéristiques vont avec un article de la famille « {self.famille} »."
            )


class Monture(Caracteristiques):
    famille = Article.Famille.MONTURE

    class Type(models.TextChoices):
        CERCLEE = "cerclee", "Cerclée"
        SEMI_CERCLEE = "semi_cerclee", "Semi-cerclée (nylor)"
        PERCEE = "percee", "Percée"

    class Genre(models.TextChoices):
        HOMME = "homme", "Homme"
        FEMME = "femme", "Femme"
        MIXTE = "mixte", "Mixte"
        ENFANT = "enfant", "Enfant"

    article = models.OneToOneField(
        Article, on_delete=models.CASCADE, primary_key=True, related_name="monture"
    )
    modele = models.CharField("modèle", max_length=100, blank=True)
    couleur = models.CharField(max_length=60, blank=True)
    matiere = models.CharField("matière", max_length=60, blank=True)
    type = models.CharField(max_length=20, choices=Type.choices, blank=True)
    genre = models.CharField(max_length=10, choices=Genre.choices, blank=True)
    calibre = models.PositiveSmallIntegerField(null=True, blank=True, help_text="mm")
    pont = models.PositiveSmallIntegerField(null=True, blank=True, help_text="mm")
    branche = models.PositiveSmallIntegerField(null=True, blank=True, help_text="mm")
    solaire = models.BooleanField(default=False)

    class Meta:
        verbose_name = "caractéristiques de la monture"
        verbose_name_plural = "caractéristiques des montures"

    def __str__(self):
        return str(self.article)


class Verre(Caracteristiques):
    famille = Article.Famille.VERRE

    class Geometrie(models.TextChoices):
        UNIFOCAL = "unifocal", "Unifocal"
        PROGRESSIF = "progressif", "Progressif"
        DEGRESSIF = "degressif", "Dégressif"
        BIFOCAL = "bifocal", "Bifocal"

    class Matiere(models.TextChoices):
        ORGANIQUE = "organique", "Organique"
        POLYCARBONATE = "polycarbonate", "Polycarbonate"
        MINERAL = "mineral", "Minéral"

    article = models.OneToOneField(
        Article, on_delete=models.CASCADE, primary_key=True, related_name="verre"
    )
    gamme = models.CharField(max_length=100, blank=True, help_text="Nom commercial du verre.")
    geometrie = models.CharField("géométrie", max_length=20, choices=Geometrie.choices)
    indice = models.DecimalField(
        max_digits=4, decimal_places=3, null=True, blank=True, help_text="1.500, 1.600, 1.670…"
    )
    matiere = models.CharField("matière", max_length=20, choices=Matiere.choices, blank=True)
    traitements = models.CharField(
        max_length=200, blank=True, help_text="Antireflet, durci, filtre lumière bleue…"
    )
    photochromique = models.BooleanField(default=False)
    teinte = models.CharField(max_length=60, blank=True)
    diametre = models.PositiveSmallIntegerField("diamètre", null=True, blank=True, help_text="mm")

    class Meta:
        verbose_name = "caractéristiques du verre"
        verbose_name_plural = "caractéristiques des verres"

    def __str__(self):
        return str(self.article)


class Lentille(Caracteristiques):
    famille = Article.Famille.LENTILLE

    class Renouvellement(models.TextChoices):
        JOURNALIERE = "journaliere", "Journalière"
        BIMENSUELLE = "bimensuelle", "Bimensuelle"
        MENSUELLE = "mensuelle", "Mensuelle"
        TRIMESTRIELLE = "trimestrielle", "Trimestrielle"
        ANNUELLE = "annuelle", "Annuelle"

    class Type(models.TextChoices):
        SPHERIQUE = "spherique", "Sphérique"
        TORIQUE = "torique", "Torique"
        MULTIFOCALE = "multifocale", "Multifocale"

    article = models.OneToOneField(
        Article, on_delete=models.CASCADE, primary_key=True, related_name="lentille"
    )
    modele = models.CharField("modèle", max_length=100, blank=True)
    renouvellement = models.CharField(max_length=20, choices=Renouvellement.choices)
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.SPHERIQUE)
    rayon = models.DecimalField(
        max_digits=3, decimal_places=1, null=True, blank=True, help_text="Rayon de courbure (mm)."
    )
    diametre = models.DecimalField(
        "diamètre", max_digits=3, decimal_places=1, null=True, blank=True, help_text="mm"
    )
    puissance = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    cylindre = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    axe = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(180)]
    )
    addition = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    lentilles_par_boite = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "caractéristiques de la lentille"
        verbose_name_plural = "caractéristiques des lentilles"

    def __str__(self):
        return str(self.article)


class PrixArticle(models.Model):
    """Prix de vente d'un article dans un pays, dans la monnaie de ce pays, et son taux de TVA.

    Le taux est une référence vers les taux du pays : quand l'administrateur modifie un taux,
    tous les articles qui l'utilisent suivent. Une vente déjà faite garde le taux qu'elle a
    appliqué. Sans prix pour son pays, un article ne peut pas être vendu dans un magasin.
    """

    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="prix")
    pays = models.ForeignKey("reseau.Pays", on_delete=models.PROTECT, related_name="+")
    prix_vente_ttc = models.DecimalField(
        max_digits=14, decimal_places=3, validators=[MinValueValidator(Decimal("0"))]
    )
    tva = models.ForeignKey(
        "reseau.TauxTva", on_delete=models.PROTECT, related_name="prix", verbose_name="TVA"
    )

    class Meta:
        verbose_name = "prix de vente"
        verbose_name_plural = "prix de vente"
        constraints = [models.UniqueConstraint(fields=["article", "pays"], name="un_prix_par_pays")]

    def __str__(self):
        return f"{self.article.reference} {self.prix_vente_ttc} {self.pays.devise}"

    def clean(self):
        if self.pays_id and self.tva_id and self.tva.pays_id != self.pays_id:
            raise ValidationError({"tva": "Ce taux de TVA appartient à un autre pays."})
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
