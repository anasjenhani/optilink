from . import rls
from .perimetre import definir_perimetre, reinitialiser_perimetre


class PerimetreMagasinMiddleware:
    """Pose le périmètre magasin de l'utilisateur connecté pour toute la durée de la requête.

    Il est posé deux fois : pour le filtre de l'ORM, et dans la session PostgreSQL pour la
    Row-Level Security (``core.rls``).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            ids = user.magasins_autorises()
        else:
            ids = frozenset()
        jeton = definir_perimetre(ids)
        rls.poser(ids)
        try:
            return self.get_response(request)
        finally:
            reinitialiser_perimetre(jeton)
            # La connexion est réutilisée par la requête suivante : ne rien lui laisser.
            rls.effacer()
