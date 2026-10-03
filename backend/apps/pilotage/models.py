from django.db import models


class Alerte(models.Model):
    """Entrée « Alertes » de l'administration : rien n'est stocké, la page est calculée."""

    class Meta:
        managed = False
        default_permissions = ()
        verbose_name = "alerte"
        verbose_name_plural = "alertes"

    def __str__(self):
        return "Alertes"


class Reporting(models.Model):
    """Entrée « Reporting » de l'administration : rien n'est stocké, la page est calculée."""

    class Meta:
        managed = False
        default_permissions = ()
        verbose_name = "reporting des ventes"
        verbose_name_plural = "reporting des ventes"

    def __str__(self):
        return "Reporting des ventes"
