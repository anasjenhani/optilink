from django.apps import AppConfig


class ReseauConfig(AppConfig):
    name = "apps.reseau"
    label = "reseau"
    verbose_name = "Réseau de magasins"

    def ready(self):
        from auditlog.registry import auditlog

        from .models import Magasin, Pays, Region, TauxTva

        auditlog.register(Region)
        auditlog.register(Magasin)
        # Fiscalité : tout changement de taux ou de timbre est tracé.
        auditlog.register(Pays)
        auditlog.register(TauxTva)
