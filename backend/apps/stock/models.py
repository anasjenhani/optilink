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
        SUPPLEMENT = "supplement", "Supplément verre"

    reference = models.CharField(max_length=40, unique=True)
    libelle = models.CharField(max_length=200)
    famille = models.CharField(max_length=20, choices=Famille.choices)
    code_barres = models.CharField(max_length=40, blank=True, db_index=True)
    # Obligatoire à la saisie et à l'import ; vide seulement pour les articles d'avant.
    fournisseur = models.ForeignKey(
        "achats.Fournisseur",
        on_delete=models.PROTECT,
        null=True,
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
    suivi_numero_serie = models.BooleanField(
        "numéro de série", default=False, help_text="Chaque pièce a son numéro de série."
    )
    promotion = models.BooleanField(default=False)
    etui_special = models.BooleanField("étui spécial", default=False)
    fodec = models.BooleanField(
        "FODEC", default=False, help_text="Achat soumis au FODEC (1 % du net HT)."
    )
    observation = models.TextField(blank=True)
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="créé par",
    )

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
        if self.famille in (self.Famille.DIVERS, self.Famille.SUPPLEMENT):
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

    class Categorie(models.TextChoices):
        OPTIQUE = "optique", "Lunette Optique"
        SOLAIRE = "solaire", "Lunette Solaire"
        APPLIQUE = "applique", "Lunette Applique"

    class Matiere(models.TextChoices):
        ACETATE = "acetate", "Acétate"
        TITANE = "titane", "Titane"
        ACIER = "acier", "Acier"
        TR90 = "tr90", "TR90"
        CORNE = "corne", "Corne"
        BOIS = "bois", "Bois"
        METAL = "metal", "Métal"

    class TrancheAge(models.TextChoices):
        ADULTE = "adulte", "Adulte"
        JUNIOR = "junior", "Junior"
        ENFANT = "enfant", "Enfant"
        BEBE = "bebe", "Bébé"

    article = models.OneToOneField(
        Article, on_delete=models.CASCADE, primary_key=True, related_name="monture"
    )
    categorie = models.CharField(
        "famille", max_length=10, choices=Categorie.choices, default=Categorie.OPTIQUE
    )
    modele = models.CharField("modèle", max_length=100, blank=True)
    couleur = models.CharField("couleur monture", max_length=60, blank=True)
    couleur_verres = models.CharField(max_length=60, blank=True)
    matiere = models.CharField("matière", max_length=60, choices=Matiere.choices, blank=True)
    type = models.CharField(max_length=20, choices=Type.choices, blank=True)
    forme = models.CharField(max_length=40, blank=True, help_text="Ronde, rectangle, papillon…")
    genre = models.CharField(max_length=10, choices=Genre.choices, blank=True)
    tranche_age = models.CharField(
        "tranche d'âge", max_length=10, choices=TrancheAge.choices, blank=True
    )
    calibre = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Taille du verre, mm."
    )
    pont = models.PositiveSmallIntegerField(null=True, blank=True, help_text="mm")
    branche = models.PositiveSmallIntegerField(null=True, blank=True, help_text="mm")
    # Suit la famille (« Lunette Solaire ») : la vente au comptoir filtre dessus.
    solaire = models.BooleanField(default=False, editable=False)

    class Meta:
        verbose_name = "caractéristiques de la monture"
        verbose_name_plural = "caractéristiques des montures"

    def __str__(self):
        return str(self.article)

    def save(self, *args, **kwargs):
        self.solaire = self.categorie == self.Categorie.SOLAIRE
        if kwargs.get("update_fields") is not None and "categorie" in kwargs["update_fields"]:
            kwargs["update_fields"] = {*kwargs["update_fields"], "solaire"}
        super().save(*args, **kwargs)


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
    matiere = models.CharField("matière", max_length=60, choices=Matiere.choices, blank=True)
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
    prix_achat_ht = models.DecimalField(
        "prix d'achat HT",
        max_digits=14,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Prix d'achat brut, avant remise.",
    )
    taux_remise_achat = models.DecimalField(
        "remise à l'achat (%)",
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
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
        RETOUR_FOURNISSEUR = "retour_fournisseur", "Retour au fournisseur"
        TRANSFERT_SORTIE = "transfert_sortie", "Transfert envoyé"
        TRANSFERT_ENTREE = "transfert_entree", "Transfert reçu"

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


class TransfertStock(ModeleDeBase):
    """Envoi d'articles d'un magasin (le dépôt central en général) vers un autre.

    À l'envoi, les articles sortent du stock de départ ; ils entrent dans le stock du magasin
    destinataire quand il le réceptionne. Entre les deux, ils sont « en route ».
    """

    class Statut(models.TextChoices):
        ENVOYE = "envoye", "Envoyé (en route)"
        RECU = "recu", "Reçu"
        ANNULE = "annule", "Annulé"

    magasin = models.ForeignKey(
        "reseau.Magasin",
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="magasin de départ",
    )
    destination = models.ForeignKey(
        "reseau.Magasin",
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="magasin destinataire",
    )
    numero = models.CharField(max_length=40, unique=True)
    annee = models.PositiveSmallIntegerField()
    sequence = models.PositiveIntegerField()
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.ENVOYE)
    observation = models.TextField(blank=True)
    envoye_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    recu_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    recu_le = models.DateTimeField(null=True, blank=True)
    annule_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    annule_le = models.DateTimeField(null=True, blank=True)

    # Deux magasins par transfert : le périmètre est filtré par l'API (départ ou destination)
    # et par la RLS de la base.
    objects = models.Manager()
    tous = models.Manager()

    class Meta:
        ordering = ["-annee", "-sequence"]
        verbose_name = "transfert de stock"
        verbose_name_plural = "transferts de stock"
        constraints = [
            models.UniqueConstraint(
                fields=["magasin", "annee", "sequence"], name="transfert_sans_doublon"
            ),
            models.CheckConstraint(
                name="transfert_vers_un_autre_magasin",
                condition=~models.Q(destination=models.F("magasin")),
            ),
        ]

    def __str__(self):
        return self.numero


class LigneTransfert(models.Model):
    transfert = models.ForeignKey(TransfertStock, on_delete=models.CASCADE, related_name="lignes")
    article = models.ForeignKey(Article, on_delete=models.PROTECT, related_name="+")
    quantite = models.PositiveIntegerField("quantité")

    class Meta:
        verbose_name = "ligne de transfert"
        verbose_name_plural = "lignes de transfert"

    def __str__(self):
        return f"{self.quantite} × {self.article}"


class Inventaire(ModeleDeBase):
    """Comptage physique du stock d'un magasin (ou du dépôt) : tout le stock, ou une partie
    (famille, marque, nature de monture, fournisseur).

    Trois étapes : le comptage (« en cours »), puis la vérification où le responsable contrôle
    les écarts et corrige les quantités, puis la validation finale avec une observation. À la
    validation, l'écart entre le compté et le stock de l'application devient un mouvement
    d'ajustement ; un article en stock mais non compté est considéré comme absent (0).
    """

    class Statut(models.TextChoices):
        EN_COURS = "en_cours", "En cours de comptage"
        A_VERIFIER = "a_verifier", "En vérification"
        VALIDE = "valide", "Validé"
        ANNULE = "annule", "Annulé"

    magasin = models.ForeignKey("reseau.Magasin", on_delete=models.PROTECT, related_name="+")
    numero = models.CharField(max_length=40, unique=True)
    annee = models.PositiveSmallIntegerField()
    sequence = models.PositiveIntegerField()
    famille = models.CharField(
        max_length=20,
        choices=Article.Famille.choices,
        blank=True,
        help_text="Vide : tout le stock du magasin.",
    )
    marque = models.CharField(max_length=100, blank=True, help_text="Montures de cette marque.")
    nature = models.CharField(
        max_length=10,
        choices=Monture.Categorie.choices,
        blank=True,
        help_text="Montures optiques, solaires ou appliques.",
    )
    fournisseur = models.ForeignKey(
        "achats.Fournisseur", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.EN_COURS)
    observation = models.TextField(blank=True)
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    valide_le = models.DateTimeField(null=True, blank=True)
    comptage_termine_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    comptage_termine_le = models.DateTimeField(null=True, blank=True)
    observation_validation = models.TextField(
        blank=True, help_text="Saisie à la validation finale (écarts expliqués, recomptages…)."
    )

    objects = ParMagasinManager()
    tous = models.Manager()  # noqa: DJ012

    class Meta:
        ordering = ["-annee", "-sequence"]
        verbose_name = "inventaire"
        constraints = [
            models.UniqueConstraint(
                fields=["magasin", "annee", "sequence"], name="inventaire_sans_doublon"
            )
        ]
        permissions = [("valider_inventaire", "Peut valider un inventaire (corrige le stock)")]

    def __str__(self):
        return self.numero


class LigneInventaire(models.Model):
    """Article compté ; ``stock_theorique`` et ``ecart`` sont figés à la validation."""

    inventaire = models.ForeignKey(Inventaire, on_delete=models.CASCADE, related_name="lignes")
    article = models.ForeignKey(Article, on_delete=models.PROTECT, related_name="+")
    quantite_comptee = models.PositiveIntegerField("quantité comptée", default=0)
    stock_theorique = models.IntegerField("stock de l'application", null=True, blank=True)
    ecart = models.IntegerField(null=True, blank=True)
    observation = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "ligne d'inventaire"
        verbose_name_plural = "lignes d'inventaire"
        constraints = [
            models.UniqueConstraint(
                fields=["inventaire", "article"], name="inventaire_article_unique"
            )
        ]

    def __str__(self):
        return f"{self.quantite_comptee} × {self.article}"


def stock_disponible(magasin, article):
    total = MouvementStock.tous.filter(magasin=magasin, article=article).aggregate(
        total=Sum("quantite")
    )["total"]
    return total or 0
