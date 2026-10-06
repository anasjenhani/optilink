"""Liste des banques : retrouver la banque d'une fiche par son nom, son sigle ou le RIB."""

import re

from django.core.exceptions import ValidationError

from .models import Banque
from .villes import normaliser


def _banques(pays):
    banques = Banque.objects.filter(est_active=True)
    return banques.filter(pays=pays) if pays is not None else banques


def banque_de_la_liste(texte, pays=None):
    """Banque dont le nom ou le sigle est ``texte`` (à la casse et aux accents près)."""
    cle = normaliser(texte)
    if not cle:
        return None
    return next(
        (b for b in _banques(pays) if cle in (normaliser(b.nom), normaliser(b.sigle))), None
    )


def banque_du_rib(rib, pays=None):
    """Banque désignée par les premiers chiffres du RIB (code banque)."""
    chiffres = re.sub(r"\D", "", rib or "")
    if len(chiffres) < 2:
        return None
    return next((b for b in _banques(pays) if chiffres.startswith(b.code)), None)


def _sans_liste(pays):
    return pays is not None and not _banques(pays).exists()


def valider_banque(texte, rib="", pays=None):
    """Banque saisie à l'écran : vide, ou choisie dans la liste (écrite comme dans la liste).

    Sans banque mais avec un RIB, la banque est déduite du RIB ; un RIB d'une autre banque est
    refusé. Un pays qui n'a pas encore de liste garde la saisie libre.
    """
    texte = (texte or "").strip()
    if _sans_liste(pays):
        return texte
    du_rib = banque_du_rib(rib, pays)
    if not texte:
        return du_rib.nom if du_rib else ""
    banque = banque_de_la_liste(texte, pays)
    if banque is None:
        raise ValidationError(
            {
                "banque": f"« {texte} » n'est pas dans la liste des banques : choisissez-en une, "
                "ou ajoutez-la dans Réseau › Banques."
            }
        )
    if du_rib is not None and du_rib != banque:
        attendue, choisie = du_rib.sigle or du_rib.nom, banque.sigle or banque.nom
        raise ValidationError({"rib": f"Ce RIB est un RIB {attendue}, pas {choisie}."})
    return banque.nom


def banque_importee(texte, rib="", pays=None):
    """Banque lue dans un fichier : écrite comme dans la liste, ou gardée telle quelle avec une
    alerte (un ancien fichier ne doit pas bloquer l'import)."""
    try:
        return valider_banque(texte, rib, pays), None
    except ValidationError as erreur:
        message = " ".join(m for messages in erreur.message_dict.values() for m in messages)
        return (texte or "").strip(), f"{message} Gardée telle quelle."
