from django.apps import AppConfig


class TresorerieConfig(AppConfig):
    name = "apps.tresorerie"
    label = "tresorerie"
    verbose_name = "Trésorerie"

    def ready(self):
        from auditlog.registry import auditlog

        from .models import ClotureCaisse, DepenseCaisse

        auditlog.register(ClotureCaisse)
        auditlog.register(DepenseCaisse)
