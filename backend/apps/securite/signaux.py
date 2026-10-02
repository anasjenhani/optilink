from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .journal import journaliser
from .models import EvenementSecurite


@receiver(user_logged_in, dispatch_uid="securite_connexion_reussie")
def connexion_reussie(sender, request, user, **kwargs):
    journaliser(EvenementSecurite.Type.CONNEXION_REUSSIE, request, user)


@receiver(user_logged_out, dispatch_uid="securite_deconnexion")
def deconnexion(sender, request, user, **kwargs):
    if user is not None:
        journaliser(EvenementSecurite.Type.DECONNEXION, request, user)


@receiver(user_login_failed, dispatch_uid="securite_connexion_echouee")
def connexion_echouee(sender, credentials, request=None, **kwargs):
    journaliser(
        EvenementSecurite.Type.CONNEXION_ECHOUEE,
        request,
        identifiant=str(credentials.get("username", "")),
    )
