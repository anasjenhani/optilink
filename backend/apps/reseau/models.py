from django.core.validators import RegexValidator
from django.db import models
from django.db.models.functions import Lower

from core.managers import ParMagasinManager
from core.models import ModeleDeBase


class Pays(models.Model):
    """Paramètres propres à un pays : monnaie, fiscalité, formats.

    OptiLink démarre en Tunisie et s'ouvrira à d'autres pays : rien de tout cela n'est écrit en
    dur dans le code. Chaque magasin est rattaché à un pays.
    """

    code_numerique = models.CharField(
        "code ISO",
        max_length=3,
        unique=True,
        validators=[RegexValidator(r"^\d{3}$", "Trois chiffres, ex. 788.")],
        help_text="Code numérique ISO 3166-1, ex. 788 pour la Tunisie.",
    )
    code = models.CharField(
        "code alpha-2", max_length=2, unique=True, help_text="ISO 3166-1 alpha-2, ex. TN"
    )
    nom = models.CharField(max_length=100)
    devise = models.CharField(max_length=3, help_text="Code ISO 4217, ex. TND")
    decimales = models.PositiveSmallIntegerField(
        default=2, help_text="Décimales de la monnaie : 3 pour le dinar (millimes)."
    )
    fuseau_horaire = models.CharField(max_length=50, default="Africa/Tunis")
    indicatif_telephonique = models.CharField(max_length=6, blank=True)
    timbre_fiscal = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=0,
        help_text="Droit de timbre ajouté à chaque facture, pas aux tickets (0 si aucun).",
    )
    libelle_identifiant_prescripteur = models.CharField(
        max_length=100, default="Identifiant du prescripteur"
    )
    format_identifiant_prescripteur = models.CharField(
        max_length=100, blank=True, help_text="Expression régulière ; vide = pas de contrôle."
    )

    class Meta:
        ordering = ["nom"]
        verbose_name = "pays"
        verbose_name_plural = "pays"

    def __str__(self):
        return self.nom


class Ville(models.Model):
    """Ville proposée dans la liste des fiches (client, fournisseur, société, magasin).

    Les fiches gardent le nom de la ville en texte : la liste impose une écriture unique
    (« Ariana », pas « ariena ») sans lier les fiches à une ligne qu'on pourrait supprimer.
    """

    pays = models.ForeignKey(Pays, on_delete=models.PROTECT, related_name="villes")
    nom = models.CharField(max_length=100)
    est_active = models.BooleanField(
        "active", default=True, help_text="Une ville désactivée n'est plus proposée."
    )

    class Meta:
        ordering = ["nom"]
        verbose_name = "ville"
        constraints = [models.UniqueConstraint(Lower("nom"), "pays", name="ville_unique_par_pays")]

    def __str__(self):
        return self.nom


class Banque(models.Model):
    """Banque proposée dans la liste des fiches (fournisseur, société, compte bancaire).

    Le code est celui de la banque dans le RIB (ses 2 premiers chiffres en Tunisie) : il permet
    de retrouver la banque d'un RIB et de signaler un RIB qui ne va pas avec la banque choisie.
    Comme pour les villes, les fiches gardent le nom de la banque en texte.
    """

    pays = models.ForeignKey(Pays, on_delete=models.PROTECT, related_name="banques")
    code = models.CharField(max_length=5, help_text="Code de la banque dans le RIB, ex. 08.")
    nom = models.CharField(max_length=100)
    sigle = models.CharField(max_length=20, blank=True)
    est_active = models.BooleanField(
        "active", default=True, help_text="Une banque désactivée n'est plus proposée."
    )

    class Meta:
        ordering = ["nom"]
        verbose_name = "banque"
        constraints = [
            models.UniqueConstraint(fields=["pays", "code"], name="banque_code_unique_par_pays"),
            models.UniqueConstraint(Lower("nom"), "pays", name="banque_unique_par_pays"),
        ]

    def __str__(self):
        return f"{self.nom} ({self.sigle})" if self.sigle else self.nom


class TauxTva(models.Model):
    pays = models.ForeignKey(Pays, on_delete=models.CASCADE, related_name="taux_tva")
    taux = models.DecimalField(max_digits=5, decimal_places=2)
    libelle = models.CharField(max_length=50)

    class Meta:
        ordering = ["pays", "-taux"]
        verbose_name = "taux de TVA"
        verbose_name_plural = "taux de TVA"
        constraints = [models.UniqueConstraint(fields=["pays", "taux"], name="taux_unique")]

    def __str__(self):
        return f"{self.pays.code} {self.taux} %"


PREFIXE_SOCIETE = "SCTE"


def _code_societe_suivant():
    numeros = [
        int(code[len(PREFIXE_SOCIETE) :])
        for code in Societe.objects.filter(code__regex=rf"^{PREFIXE_SOCIETE}\d+$").values_list(
            "code", flat=True
        )
    ]
    return f"{PREFIXE_SOCIETE}{max(numeros, default=0) + 1:03d}"


class Societe(ModeleDeBase):
    """Société qui exploite un ou plusieurs magasins : identité légale, coordonnées, logo."""

    class FormeJuridique(models.TextChoices):
        SARL = "SARL", "SARL"
        SUARL = "SUARL", "SUARL"
        SA = "SA", "SA"
        SNC = "SNC", "SNC"
        SCS = "SCS", "SCS"
        PERSONNE_PHYSIQUE = "PP", "Personne physique"

    code = models.CharField(
        max_length=20, unique=True, editable=False, help_text="Généré : SCTE001, SCTE002…"
    )
    raison_sociale = models.CharField(max_length=150)
    responsable = models.CharField(max_length=100, blank=True)
    forme_juridique = models.CharField(max_length=5, choices=FormeJuridique.choices, blank=True)
    matricule_fiscal = models.CharField(max_length=30, blank=True)
    registre_commerce = models.CharField("registre de commerce", max_length=30, blank=True)
    numero_cnss = models.CharField("n° CNSS", max_length=30, blank=True)
    banque = models.CharField(max_length=100, blank=True)
    rib = models.CharField(
        "RIB bancaire",
        max_length=34,
        blank=True,
        validators=[RegexValidator(r"^[A-Za-z0-9 ]*$", "Chiffres et lettres seulement.")],
        help_text="20 chiffres en Tunisie, ou IBAN.",
    )
    adresse = models.TextField(blank=True)
    code_postal = models.CharField(max_length=10, blank=True)
    ville = models.CharField(max_length=100, blank=True)
    pays = models.ForeignKey(
        Pays, on_delete=models.PROTECT, null=True, blank=True, related_name="societes"
    )
    telephone_1 = models.CharField("téléphone 1", max_length=20, blank=True)
    telephone_2 = models.CharField("téléphone 2", max_length=20, blank=True)
    fax = models.CharField(max_length=20, blank=True)
    email = models.EmailField("e-mail", blank=True)
    site_web = models.URLField("site web", blank=True)
    facebook = models.CharField(max_length=200, blank=True)
    observation = models.TextField(blank=True)
    code_douane = models.CharField(
        "code douane", max_length=30, blank=True, help_text="Société établie à l'étranger."
    )
    carte_sejour = models.CharField(
        "carte de séjour", max_length=30, blank=True, help_text="Société établie à l'étranger."
    )
    # Le logo est gardé dans la base : il est ainsi compris dans la sauvegarde de chaque nuit.
    logo = models.BinaryField(null=True, blank=True, editable=False)
    logo_type = models.CharField(max_length=20, blank=True, editable=False)

    class Meta:
        ordering = ["code"]
        verbose_name = "société"

    def __str__(self):
        return self.raison_sociale

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = _code_societe_suivant()
        super().save(*args, **kwargs)


class Magasin(ModeleDeBase):
    """Point de vente. Son stock est rangé dans ses dépôts (voir ``Depot``)."""

    code = models.CharField(max_length=20, unique=True)
    nom = models.CharField(max_length=100)
    societe = models.ForeignKey(
        Societe, on_delete=models.PROTECT, related_name="magasins", verbose_name="société"
    )
    pays = models.ForeignKey(Pays, on_delete=models.PROTECT, related_name="magasins")
    adresse = models.CharField(max_length=200, blank=True)
    code_postal = models.CharField(max_length=10, blank=True)
    ville = models.CharField(max_length=100, blank=True)
    telephone = models.CharField(max_length=20, blank=True)
    nombre_peniches = models.PositiveSmallIntegerField(
        "nombre de péniches",
        default=200,
        help_text="Bacs numérotés de 1 à ce nombre où l'on range l'équipement d'une commande.",
    )
    est_actif = models.BooleanField(default=True)

    objects = ParMagasinManager(champ="id")
    tous = models.Manager()

    class Meta:
        ordering = ["code"]
        verbose_name = "magasin"

    def __str__(self):
        return f"{self.code} {self.nom}"

    def save(self, *args, **kwargs):
        nouveau = self._state.adding
        super().save(*args, **kwargs)
        if nouveau and not Depot.objects.filter(magasin=self).exists():
            code = self.code if not Depot.objects.filter(code=self.code).exists() else ""
            Depot.objects.create(
                magasin=self,
                code=code or f"{self.code}-V"[:20],
                nom=f"Dépôt {self.nom}"[:100],
                adresse=self.adresse,
                ville=self.ville,
                telephone=self.telephone,
                type=Depot.Type.VENTE,
            )

    @property
    def est_depot(self):
        """Le magasin abrite le dépôt central : les achats de sa société s'y saisissent."""
        return self.depots.filter(type=Depot.Type.CENTRAL, est_actif=True).exists()

    @property
    def depot_de_vente(self):
        """Dépôt dont sortent les ventes : le dépôt de vente, à défaut le premier dépôt actif."""
        depots = sorted(
            (d for d in self.depots.all() if d.est_actif),
            key=lambda d: (d.type != Depot.Type.VENTE, d.code),
        )
        if not depots:
            raise Depot.DoesNotExist(f"Le magasin {self.nom} n'a aucun dépôt actif.")
        return depots[0]

    @property
    def depot_de_reception(self):
        """Dépôt où entre la marchandise des fournisseurs : le dépôt central s'il est ici."""
        central = self.depots.filter(type=Depot.Type.CENTRAL, est_actif=True).first()
        return central or self.depot_de_vente


class Depot(ModeleDeBase):
    """Lieu de stockage rattaché à un magasin, comme dans l'ancien logiciel (DEPTN, DEPCEN…).

    Le stock se compte par dépôt. Chaque magasin a son dépôt de vente, dont sortent les ventes.
    Le dépôt central reçoit la marchandise des fournisseurs de toute la société, puis l'envoie
    aux magasins par transfert ; le magasin qui l'abrite saisit les achats (BL, factures, bons
    retour). Le dépôt casse garde les articles cassés ou défectueux.
    """

    class Type(models.TextChoices):
        VENTE = "vente", "Dépôt de vente"
        CENTRAL = "central", "Dépôt central"
        CASSE = "casse", "Dépôt casse"

    # Mêmes colonnes que la table Depot de l'ancien logiciel : CodeDepot, Libelle, Adresse,
    # Ville, Tel, CodeMagasin ; EtatInventaire est calculé (inventaire_en_cours).
    code = models.CharField(
        "code dépôt", max_length=20, unique=True, help_text="Ex. DEPTN, DEPCEN, DEPCAS."
    )
    nom = models.CharField("libellé", max_length=100)
    adresse = models.TextField(blank=True)
    ville = models.CharField(max_length=100, blank=True)
    telephone = models.CharField("téléphone", max_length=20, blank=True)
    magasin = models.ForeignKey(Magasin, on_delete=models.PROTECT, related_name="depots")
    type = models.CharField(max_length=10, choices=Type.choices, default=Type.VENTE)
    est_actif = models.BooleanField("actif", default=True)

    class Meta:
        ordering = ["magasin__code", "code"]
        verbose_name = "dépôt"
        constraints = [
            models.UniqueConstraint(
                fields=["magasin"],
                condition=models.Q(type="vente"),
                name="un_depot_de_vente_par_magasin",
            )
        ]

    def __str__(self):
        return f"{self.code} {self.nom}"

    @property
    def pays(self):
        return self.magasin.pays if self.magasin_id else None

    @property
    def inventaire_en_cours(self):
        """EtatInventaire de l'ancien logiciel : un inventaire est ouvert sur ce dépôt."""
        from apps.stock.models import Inventaire

        return Inventaire.objects.filter(
            depot=self, statut__in=[Inventaire.Statut.EN_COURS, Inventaire.Statut.A_VERIFIER]
        ).exists()

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.type == self.Type.CENTRAL and self.est_actif and self.magasin_id:
            autres = Depot.objects.filter(
                type=self.Type.CENTRAL, est_actif=True, magasin__societe_id=self.magasin.societe_id
            ).exclude(pk=self.pk)
            if autres.exists():
                raise ValidationError(
                    {"type": f"La société a déjà un dépôt central : {autres.first()}."}
                )
