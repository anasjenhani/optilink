from .models import EvenementSecurite


def adresse_ip(request):
    """Adresse du client ; Nginx remplace X-Forwarded-For par l'adresse qu'il a reçue."""
    if request is None:
        return None
    transmise = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    return transmise or request.META.get("REMOTE_ADDR") or None


def journaliser(type_evenement, request=None, utilisateur=None, identifiant="", details=""):
    if utilisateur is not None and not identifiant:
        identifiant = utilisateur.get_username()
    return EvenementSecurite.objects.create(
        type=type_evenement,
        utilisateur=utilisateur,
        identifiant=identifiant[:150],
        adresse_ip=adresse_ip(request),
        agent_utilisateur=(request.headers.get("User-Agent", "") if request else "")[:255],
        details=details[:255],
    )
