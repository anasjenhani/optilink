from django.db import IntegrityError, models, transaction
from django.db.models import Max

from core.models import ModeleDeBase


class Organisme(ModeleDeBase):
    """Organisme qui prend en charge une partie des lunettes : CNAM, assurance ou mutuelle."""

    class Type(models.TextChoices):
        CAISSE = "caisse", "Caisse d'assurance maladie"
        ASSURANCE = "assurance", "Assurance"
        MUTUELLE = "mutuelle", "Mutuelle"

    nom = models.CharField(max_length=120)
    type = models.CharField(max_length=10, choices=Type.choices)
    pays = models.ForeignKey("reseau.Pays", on_delete=models.PROTECT, related_name="+")
    est_actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["nom"]
        verbose_name = "organisme de prise en charge"
        verbose_name_plural = "organismes de prise en charge"
        constraints = [
            models.UniqueConstraint(fields=["pays", "nom"], name="organisme_unique_par_pays")
        ]

    def __str__(self):
        return self.nom


class Client(ModeleDeBase):
    """Client partagé par tout le réseau : il peut acheter dans n'importe quel magasin.

    Le magasin d'origine est conservé pour les statistiques et les relances.
    """

    class Civilite(models.TextChoices):
        MADAME = "mme", "Mme"
        MONSIEUR = "m", "M."

    numero = models.PositiveIntegerField(
        "n° de fiche",
        unique=True,
        editable=False,
        help_text="Numéro de fiche client, attribué à la création, commun à tout le réseau.",
    )
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
    reference_externe = models.CharField(
        "ancien n° de fiche",
        max_length=60,
        blank=True,
        db_index=True,
        help_text="N° de la fiche dans l'ancien logiciel, conservé à l'import des clients.",
    )
    organisme = models.ForeignKey(
        Organisme,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="clients",
        verbose_name="prise en charge",
        help_text="CNAM, assurance ou mutuelle du client (PEC client).",
    )
    numero_affilie = models.CharField(
        "n° d'affilié", max_length=40, blank=True, help_text="N° d'assuré ou d'adhérent."
    )
    notes = models.TextField(blank=True)
    est_actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["nom", "prenom"]
        verbose_name = "client"
        indexes = [models.Index(fields=["nom", "prenom"])]
        constraints = [
            models.UniqueConstraint(
                fields=["reference_externe"],
                condition=~models.Q(reference_externe=""),
                name="client_reference_externe_unique",
            )
        ]

    def __str__(self):
        return f"{self.nom.upper()} {self.prenom}"

    def save(self, *args, **kwargs):
        if self.numero:
            return super().save(*args, **kwargs)
        # Numéro suivant ; si deux fiches sont créées au même instant, la seconde réessaie.
        for essai in range(5):
            self.numero = (Client.objects.aggregate(dernier=Max("numero"))["dernier"] or 0) + 1
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError:
                self.numero = None
                if essai == 4:
                    raise

    @property
    def nom_de_facturation(self):
        """La société pour un client professionnel, sinon la personne."""
        return self.societe or str(self)

    @property
    def adresse_complete(self):
        ville = " ".join(filter(None, [self.code_postal, self.ville]))
        return ", ".join(filter(None, [self.adresse, ville]))
