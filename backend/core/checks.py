from django.core.checks import Tags, Warning, register
from django.db import connections


@register(Tags.database)
def rls_effective(app_configs, databases=None, **kwargs):
    """Avertit si le compte de connexion échappe à la Row-Level Security (lancé par migrate)."""
    alertes = []
    for alias in databases or []:
        connexion = connections[alias]
        if connexion.vendor != "postgresql":
            continue
        with connexion.cursor() as cursor:
            cursor.execute(
                "SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user"
            )
            ligne = cursor.fetchone()
        if ligne and ligne[0]:
            alertes.append(
                Warning(
                    "Le compte PostgreSQL de l'application est super-utilisateur ou BYPASSRLS : "
                    "la Row-Level Security par magasin ne s'applique pas.",
                    hint="Utiliser un compte NOSUPERUSER NOBYPASSRLS propriétaire de la base.",
                    id="optilink.W001",
                )
            )
    return alertes
