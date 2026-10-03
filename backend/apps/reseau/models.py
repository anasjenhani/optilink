from django.core.validators import RegexValidator
from django.db import models

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
