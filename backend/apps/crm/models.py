from django.db import models

from core.models import ModeleDeBase


class Client(ModeleDeBase):
    """Client partagé par tout le réseau : il peut acheter dans n'importe quel magasin.

    Le magasin d'origine est conservé pour les statistiques et les relances.
    """

    class Civilite(models.TextChoices):
        MADAME = "mme", "Mme"
        MONSIEUR = "m", "M."

    civilite = models.CharField(max_length=3, choices=Civilite.choices, blank=True)
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    date_naissance = models.DateField(null=True, blank=True)
    telephone = models.CharField(max_length=20, blank=True, db_index=True)
    telephone_2 = models.CharField("téléphone 2", max_length=20, blank=True, db_index=True)
    email = models.EmailField(blank=True)
    adresse = models.CharField(max_length=200, blank=True)
    code_postal = models.CharField(max_length=10, blank=True)
    ville = models.CharField(max_length=100, blank=True)
    societe = models.CharField(
        "société",
        max_length=200,
        blank=True,
        help_text="Client professionnel : raison sociale, au nom de laquelle on facture.",
    )
    matricule_fiscal = models.CharField(
        max_length=30,
        blank=True,
        help_text="Client professionnel : identifiant fiscal sur la facture.",
    )
    magasin_origine = models.ForeignKey(
        "reseau.Magasin", on_delete=models.PROTECT, related_name="+"
    )
    accepte_relances = models.BooleanField(
        default=False, help_text="Consentement aux relances par e-mail ou SMS (RGPD)."
    )
    notes = models.TextField(blank=True)
    est_actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["nom", "prenom"]
        verbose_name = "client"
        indexes = [models.Index(fields=["nom", "prenom"])]

    def __str__(self):
        return f"{self.nom.upper()} {self.prenom}"

    @property
    def nom_de_facturation(self):
        """La société pour un client professionnel, sinon la personne."""
        return self.societe or str(self)

    @property
    def adresse_complete(self):
        ville = " ".join(filter(None, [self.code_postal, self.ville]))
        return ", ".join(filter(None, [self.adresse, ville]))
