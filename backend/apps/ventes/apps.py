from django.apps import AppConfig


class VentesConfig(AppConfig):
    name = "apps.ventes"
    label = "ventes"
    verbose_name = "Ventes"

    def ready(self):
        from auditlog.registry import auditlog

        from .models import Devis

        # Qui a accepté, refusé ou encaissé un devis, et quand.
        auditlog.register(Devis, include_fields=["statut", "vente"])
