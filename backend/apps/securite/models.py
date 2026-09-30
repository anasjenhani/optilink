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
        regions = [a.region_id for a in affectations if a.portee == Affectation.Portee.REGION]
        if regions:
            ids.update(Magasin.tous.filter(region_id__in=regions).values_list("id", flat=True))
        return frozenset(ids)


class Affectation(models.Model):
    """Un rôle donné à un utilisateur sur un périmètre, pour une période."""

    class Portee(models.TextChoices):
        MAGASIN = "magasin", "Magasin"
        REGION = "region", "Région"
        RESEAU = "reseau", "Tout le réseau"

    utilisateur = models.ForeignKey(
        Utilisateur, on_delete=models.CASCADE, related_name="affectations"
    )
    role = models.ForeignKey(Group, on_delete=models.PROTECT, related_name="affectations")
    portee = models.CharField(max_length=10, choices=Portee.choices)
    magasin = models.ForeignKey(
        "reseau.Magasin", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    region = models.ForeignKey(
        "reseau.Region", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    debut = models.DateField(default=timezone.localdate)
    fin = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "affectation"
        constraints = [
            models.CheckConstraint(
                name="affectation_perimetre_coherent",
                condition=(
                    Q(portee="magasin", magasin__isnull=False, region__isnull=True)
                    | Q(portee="region", region__isnull=False, magasin__isnull=True)
                    | Q(portee="reseau", magasin__isnull=True, region__isnull=True)
                ),
            ),
        ]

    def __str__(self):
        cible = self.magasin or self.region or "réseau"
        return f"{self.utilisateur} · {self.role} · {cible}"

    def clean(self):
        attendu = {
            self.Portee.MAGASIN: (True, False),
            self.Portee.REGION: (False, True),
            self.Portee.RESEAU: (False, False),
        }.get(self.portee)
        if attendu and (self.magasin_id is not None, self.region_id is not None) != attendu:
            raise ValidationError("Le magasin ou la région ne correspond pas à la portée choisie.")
        if self.fin and self.fin < self.debut:
            raise ValidationError("La date de fin précède la date de début.")
