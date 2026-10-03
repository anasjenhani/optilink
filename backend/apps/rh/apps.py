from django.apps import AppConfig


class RhConfig(AppConfig):
    name = "apps.rh"
    label = "rh"
    verbose_name = "Ressources humaines"

    def ready(self):
        from auditlog.registry import auditlog

        from .models import Acompte, DemandeConge, Employe, Pointage, Prime

        auditlog.register(Employe)
        auditlog.register(Pointage)
        auditlog.register(DemandeConge)
        auditlog.register(Acompte)
        auditlog.register(Prime)
