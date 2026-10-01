from django.apps import AppConfig


class AchatsConfig(AppConfig):
    name = "apps.achats"
    label = "achats"
    verbose_name = "Achats"

    def ready(self):
        from auditlog.registry import auditlog

        from .models import CommandeFournisseur, Fournisseur

        auditlog.register(Fournisseur)
        auditlog.register(CommandeFournisseur, include_fields=["statut", "recue_le"])
