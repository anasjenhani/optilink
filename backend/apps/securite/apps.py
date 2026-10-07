from django.apps import AppConfig
from django.db.models.signals import post_migrate


class SecuriteConfig(AppConfig):
    name = "apps.securite"
    label = "securite"
    verbose_name = "Sécurité"

    def ready(self):
        from auditlog.registry import auditlog
        from django.contrib.auth.models import Group

        from . import presence, signaux  # noqa: F401
        from .models import Affectation, Utilisateur
        from .roles import initialiser_roles

        post_migrate.connect(initialiser_roles, dispatch_uid="securite_initialiser_roles")

        auditlog.register(
            Utilisateur,
            exclude_fields=["password", "last_login"],
            m2m_fields={"groups", "user_permissions"},
        )
        auditlog.register(Affectation)
        auditlog.register(Group, m2m_fields={"permissions"})
