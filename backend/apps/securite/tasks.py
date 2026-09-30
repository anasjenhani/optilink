import datetime

from celery import shared_task
from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from .journal import journaliser
from .models import EvenementSecurite, Utilisateur


@shared_task
def desactiver_comptes_inactifs():
    """Désactive les comptes sans connexion depuis COMPTES_INACTIFS_JOURS jours.

    Les super-utilisateurs, réservés à l'amorçage, ne sont pas concernés.
    """
    limite = timezone.now() - datetime.timedelta(days=settings.COMPTES_INACTIFS_JOURS)
    inactifs = Utilisateur.objects.filter(is_active=True, is_superuser=False).filter(
        Q(last_login__lt=limite) | Q(last_login__isnull=True, date_joined__lt=limite)
    )
    noms = []
    for utilisateur in inactifs:
        utilisateur.is_active = False
        utilisateur.save(update_fields=["is_active"])
        journaliser(
            EvenementSecurite.Type.COMPTE_DESACTIVE,
            utilisateur=utilisateur,
            details=f"Aucune connexion depuis {settings.COMPTES_INACTIFS_JOURS} jours",
        )
        noms.append(utilisateur.get_username())
    return noms
