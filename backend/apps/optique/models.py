from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models

from core import chiffrement
from core.models import ModeleDeBase


class Prescription(ModeleDeBase):
    """Ordonnance d'un client : donnée de santé au sens du RGPD.

    Les mesures sont chiffrées par l'application (``core.chiffrement``) ; la base ne voit qu'un
    jeton illisible. Une ordonnance ne se modifie pas : une correction est une nouvelle saisie.
    Elle suit le client dans tout le réseau ; ``magasin_saisie`` dit seulement où elle a été
    enregistrée.
    """

    class Type(models.TextChoices):
        LUNETTES = "lunettes", "Lunettes"
        LENTILLES = "lentilles", "Lentilles"

    client = models.ForeignKey("crm.Client", on_delete=models.PROTECT, related_name="prescriptions")
    type = models.CharField(max_length=10, choices=Type.choices)
    date_prescription = models.DateField()
    prescripteur = models.CharField(max_length=200, help_text="Nom de l'ophtalmologiste.")
    prescripteur_rpps = models.CharField(
        "n° RPPS",
        max_length=11,
        blank=True,
        validators=[RegexValidator(r"^\d{11}$", "Le n° RPPS compte 11 chiffres.")],
    )
    mesures_chiffrees = models.TextField(editable=False)
    magasin_saisie = models.ForeignKey("reseau.Magasin", on_delete=models.PROTECT, related_name="+")
    saisie_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        ordering = ["-date_prescription", "-cree_le"]
        verbose_name = "prescription"

    def __str__(self):
        return f"{self.get_type_display()} du {self.date_prescription:%d/%m/%Y}"

    @property
    def mesures(self):
        return chiffrement.dechiffrer(self.mesures_chiffrees)

    @mesures.setter
    def mesures(self, valeur):
        self.mesures_chiffrees = chiffrement.chiffrer(valeur)


class AccesPrescription(models.Model):
    """Journal de chaque consultation ou saisie d'ordonnance, en ajout seul (verrou en base)."""

    class Action(models.TextChoices):
        CONSULTATION = "consultation", "Consultation"
        SAISIE = "saisie", "Saisie"

    horodatage = models.DateTimeField(auto_now_add=True, db_index=True)
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    prescription = models.ForeignKey(Prescription, on_delete=models.PROTECT, related_name="acces")
    action = models.CharField(max_length=20, choices=Action.choices)
    adresse_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-horodatage"]
        verbose_name = "accès à une prescription"
        verbose_name_plural = "accès aux prescriptions"

    def __str__(self):
        return f"{self.get_action_display()} {self.horodatage:%d/%m/%Y %H:%M}"
