from django.contrib.auth.models import AbstractUser, Group
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Utilisateur(AbstractUser):
    """Compte OptiLink. Les droits viennent des affectations (rôle + périmètre)."""

    def affectations_actives(self, jour=None):
        jour = jour or timezone.localdate()
        return self.affectations.filter(debut__lte=jour).filter(
            Q(fin__isnull=True) | Q(fin__gte=jour)
        )

    def magasins_autorises(self):
        """Magasins visibles : ``None`` pour tout le réseau, sinon un ensemble d'identifiants."""
        from apps.reseau.models import Magasin

        if not self.is_active:
            return frozenset()
        if self.is_superuser:
            return None
        affectations = list(self.affectations_actives())
        if any(a.portee == Affectation.Portee.RESEAU for a in affectations):
            return None
        ids = {a.magasin_id for a in affectations if a.portee == Affectation.Portee.MAGASIN}
        societes = [a.societe_id for a in affectations if a.portee == Affectation.Portee.SOCIETE]
        if societes:
            ids.update(Magasin.tous.filter(societe_id__in=societes).values_list("id", flat=True))
        return frozenset(ids)


class Affectation(models.Model):
    """Un rôle donné à un utilisateur sur un périmètre, pour une période."""

    class Portee(models.TextChoices):
        MAGASIN = "magasin", "Magasin"
        SOCIETE = "societe", "Société"
        RESEAU = "reseau", "Tout le réseau"

    utilisateur = models.ForeignKey(
        Utilisateur, on_delete=models.CASCADE, related_name="affectations"
    )
    role = models.ForeignKey(Group, on_delete=models.PROTECT, related_name="affectations")
    portee = models.CharField(max_length=10, choices=Portee.choices)
    magasin = models.ForeignKey(
        "reseau.Magasin", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    societe = models.ForeignKey(
        "reseau.Societe",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="société",
    )
    debut = models.DateField(default=timezone.localdate)
    fin = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "affectation"
        constraints = [
            models.CheckConstraint(
                name="affectation_perimetre_coherent",
                condition=(
                    Q(portee="magasin", magasin__isnull=False, societe__isnull=True)
                    | Q(portee="societe", societe__isnull=False, magasin__isnull=True)
                    | Q(portee="reseau", magasin__isnull=True, societe__isnull=True)
                ),
            ),
        ]

    def __str__(self):
        cible = self.magasin or self.societe or "réseau"
        return f"{self.utilisateur} · {self.role} · {cible}"

    def clean(self):
        attendu = {
            self.Portee.MAGASIN: (True, False),
            self.Portee.SOCIETE: (False, True),
            self.Portee.RESEAU: (False, False),
        }.get(self.portee)
        if attendu and (self.magasin_id is not None, self.societe_id is not None) != attendu:
            raise ValidationError("Le magasin ou la société ne correspond pas à la portée choisie.")
        if self.fin and self.fin < self.debut:
            raise ValidationError("La date de fin précède la date de début.")


class EvenementSecurite(models.Model):
    """Journal des connexions et opérations MFA, en ajout seul."""

    class Type(models.TextChoices):
        CONNEXION_REUSSIE = "connexion_reussie", "Connexion réussie"
        CONNEXION_ECHOUEE = "connexion_echouee", "Connexion échouée"
        DECONNEXION = "deconnexion", "Déconnexion"
        MFA_REUSSIE = "mfa_reussie", "Code MFA accepté"
        MFA_ECHOUEE = "mfa_echouee", "Code MFA refusé"
        MFA_ACTIVEE = "mfa_activee", "MFA activée"
        COMPTE_DESACTIVE = "compte_desactive", "Compte désactivé pour inactivité"

    horodatage = models.DateTimeField(auto_now_add=True, db_index=True)
    type = models.CharField(max_length=30, choices=Type.choices, db_index=True)
    utilisateur = models.ForeignKey(
        Utilisateur, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    identifiant = models.CharField(
        max_length=150, blank=True, help_text="Identifiant saisi, conservé même sans compte."
    )
    adresse_ip = models.GenericIPAddressField(null=True, blank=True)
    agent_utilisateur = models.CharField(max_length=255, blank=True)
    details = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "événement de sécurité"
        verbose_name_plural = "événements de sécurité"
        ordering = ["-horodatage"]

    def __str__(self):
        return f"{self.horodatage:%Y-%m-%d %H:%M} · {self.get_type_display()} · {self.identifiant}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValueError("Un événement de sécurité ne se modifie pas.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Un événement de sécurité ne se supprime pas.")
