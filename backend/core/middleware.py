from .perimetre import definir_perimetre, reinitialiser_perimetre


class PerimetreMagasinMiddleware:
    """Pose le périmètre magasin de l'utilisateur connecté pour toute la durée de la requête."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            ids = user.magasins_autorises()
        else:
            ids = frozenset()
        jeton = definir_perimetre(ids)
        try:
            return self.get_response(request)
        finally:
            reinitialiser_perimetre(jeton)
