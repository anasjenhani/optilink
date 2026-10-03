from django.apps import AppConfig


class RhConfig(AppConfig):
    name = "apps.rh"
    label = "rh"
    verbose_name = "Ressources humaines"

    def ready(self):
        from auditlog.registry import auditlog

        from .models import DemandeConge, Employe, Pointage

        auditlog.register(Employe)
        auditlog.register(Pointage)
        auditlog.register(DemandeConge)
