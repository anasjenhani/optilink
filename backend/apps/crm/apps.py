from django.apps import AppConfig


class CrmConfig(AppConfig):
    name = "apps.crm"
    label = "crm"
    verbose_name = "Clients"

    def ready(self):
        from auditlog.registry import auditlog

        from .models import Client

        auditlog.register(Client)
