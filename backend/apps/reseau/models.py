from django.db import models

from core.managers import ParMagasinManager
from core.models import ModeleDeBase


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
