"""Utilisateurs connectés : qui a utilisé OptiLink (application ou /admin/) ces dernières minutes.

Chaque requête d'un compte connecté note l'heure dans le cache (au plus une écriture par minute
et par compte) ; la déconnexion l'efface. Un compte est « connecté » tant que sa dernière
activité date de moins de PRESENCE_MINUTES.
"""

from django.conf import settings
from django.contrib.auth.signals import user_logged_out
from django.core.cache import cache
from django.dispatch import receiver
from django.utils import timezone


def _cle(pk):
    return f"presence:{pk}"


def noter_activite(utilisateur):
    if cache.add(f"presence-maj:{utilisateur.pk}", 1, 60):
        cache.set(_cle(utilisateur.pk), timezone.now(), settings.PRESENCE_MINUTES * 60)


def dernieres_activites(pks):
    """{pk: heure de la dernière activité} des comptes connectés parmi ``pks``."""
    trouves = cache.get_many([_cle(pk) for pk in pks])
    return {int(cle.split(":")[1]): heure for cle, heure in trouves.items()}


def est_connecte(utilisateur):
    return bool(dernieres_activites([utilisateur.pk]))


@receiver(user_logged_out)
def oublier(sender, user, **kwargs):
    if user is not None:
        cache.delete_many([_cle(user.pk), f"presence-maj:{user.pk}"])


class PresenceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            noter_activite(user)
        return self.get_response(request)
