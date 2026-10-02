from django.db import models

from core.managers import ParMagasinManager
from core.models import ModeleDeBase


class Pays(models.Model):
    """Paramètres propres à un pays : monnaie, fiscalité, formats.

    OptiLink démarre en Tunisie et s'ouvrira à d'autres pays : rien de tout cela n'est écrit en
    dur dans le code. Chaque magasin est rattaché à un pays.
    """

    code = models.CharField("code ISO", max_length=2, unique=True, help_text="ISO 3166, ex. TN")
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


class Region(ModeleDeBase):
    code = models.CharField(max_length=20, unique=True)
    nom = models.CharField(max_length=100)

    class Meta:
        ordering = ["code"]
        verbose_name = "région"

    def __str__(self):
        return self.nom


class Magasin(ModeleDeBase):
    code = models.CharField(max_length=20, unique=True)
    nom = models.CharField(max_length=100)
    region = models.ForeignKey(Region, on_delete=models.PROTECT, related_name="magasins")
    pays = models.ForeignKey(Pays, on_delete=models.PROTECT, related_name="magasins")
    adresse = models.CharField(max_length=200, blank=True)
    code_postal = models.CharField(max_length=10, blank=True)
    ville = models.CharField(max_length=100, blank=True)
    telephone = models.CharField(max_length=20, blank=True)
    est_actif = models.BooleanField(default=True)

    objects = ParMagasinManager(champ="id")
    tous = models.Manager()

    class Meta:
        ordering = ["code"]
        verbose_name = "magasin"

    def __str__(self):
        return f"{self.code} {self.nom}"
