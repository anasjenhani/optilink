from decimal import Decimal

from django.conf import settings
from django.db import models

from core.managers import ParMagasinManager
from core.models import ModeleDeBase

JOURS = {"max_digits": 5, "decimal_places": 1}


class Employe(ModeleDeBase):
    """Fiche d'un membre du personnel, rattachée au magasin où il travaille."""

    magasin = models.ForeignKey("reseau.Magasin", on_delete=models.PROTECT, related_name="+")
    utilisateur = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employe",
        help_text="Compte OptiLink de l'employé, pour qu'il demande ses congés lui-même.",
    )
    matricule = models.CharField(max_length=20, unique=True, editable=False)
    nom = models.CharField(max_length=80)
    prenom = models.CharField("prénom", max_length=80)
    cin = models.CharField("CIN", max_length=20, blank=True)
    telephone = models.CharField("téléphone", max_length=30, blank=True)
    poste = models.CharField(max_length=80, help_text="Ex. opticien, vendeur, caissier.")
    date_embauche = models.DateField("date d'embauche")
    date_sortie = models.DateField(null=True, blank=True)
    conges_par_mois = models.DecimalField(
        "jours de congé par mois",
        **JOURS,
        default=Decimal("1.0"),
        help_text="Code du travail tunisien : un jour par mois de travail effectif.",
    )
    solde_conges_initial = models.DecimalField(
        "solde de congés de départ",
        **JOURS,
        default=0,
        help_text="Jours déjà acquis à la création de la fiche (reprise de l'ancien logiciel).",
    )

    objects = ParMagasinManager()
    tous = models.Manager()

    class Meta:
        ordering = ["nom", "prenom"]
        verbose_name = "employé"

    def __str__(self):
        return f"{self.prenom} {self.nom}"

    def save(self, *args, **kwargs):
        if not self.matricule:
            from apps.reseau.models import Magasin

            code = Magasin.tous.get(pk=self.magasin_id).code
            prefixe = f"{code}-E"
            existants = Employe.tous.filter(matricule__startswith=prefixe).values_list(
                "matricule", flat=True
            )
            rang = max((int(m.removeprefix(prefixe)) for m in existants), default=0) + 1
            self.matricule = f"{prefixe}{rang:03d}"
        super().save(*args, **kwargs)


class Pointage(ModeleDeBase):
    """Présence d'un employé un jour donné, saisie par le responsable du magasin."""

    class Statut(models.TextChoices):
        PRESENT = "present", "Présent"
        RETARD = "retard", "En retard"
        ABSENT_JUSTIFIE = "absent_justifie", "Absent justifié"
        ABSENT = "absent", "Absent non justifié"

    employe = models.ForeignKey(Employe, on_delete=models.PROTECT, related_name="pointages")
    magasin = models.ForeignKey("reseau.Magasin", on_delete=models.PROTECT, related_name="+")
    date = models.DateField()
    statut = models.CharField(max_length=20, choices=Statut.choices)
    arrivee = models.TimeField("arrivée", null=True, blank=True)
    depart = models.TimeField("départ", null=True, blank=True)
    commentaire = models.CharField(max_length=200, blank=True)
    saisi_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )

    objects = ParMagasinManager()
    tous = models.Manager()

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(fields=["employe", "date"], name="un_pointage_par_jour")
        ]


class DemandeConge(ModeleDeBase):
    """Demande de congé : l'employé (ou son responsable) la saisit, un responsable décide."""

    class Type(models.TextChoices):
        ANNUEL = "annuel", "Congé annuel payé"
        MALADIE = "maladie", "Congé maladie"
        EXCEPTIONNEL = "exceptionnel", "Congé exceptionnel (mariage, décès…)"
        MATERNITE = "maternite", "Congé de maternité ou de paternité"
        SANS_SOLDE = "sans_solde", "Congé sans solde"

    class Statut(models.TextChoices):
        DEMANDEE = "demandee", "En attente"
        ACCEPTEE = "acceptee", "Acceptée"
        REFUSEE = "refusee", "Refusée"
        ANNULEE = "annulee", "Annulée"

    employe = models.ForeignKey(Employe, on_delete=models.PROTECT, related_name="conges")
    magasin = models.ForeignKey("reseau.Magasin", on_delete=models.PROTECT, related_name="+")
    type = models.CharField(max_length=20, choices=Type.choices)
    debut = models.DateField("du")
    fin = models.DateField("au")
    jours = models.DecimalField(**JOURS, help_text="Jours ouvrables, dimanches exclus.")
    motif = models.CharField(max_length=200, blank=True)
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.DEMANDEE)
    demandee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    decidee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    decidee_le = models.DateTimeField(null=True, blank=True)
    commentaire_decision = models.CharField(max_length=200, blank=True)

    objects = ParMagasinManager()
    tous = models.Manager()

    class Meta:
        ordering = ["-debut"]
        verbose_name = "demande de congé"
        verbose_name_plural = "demandes de congé"
        permissions = [("decider_demandeconge", "Peut accepter ou refuser une demande de congé")]
