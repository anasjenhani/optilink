"""Liste des ophtalmologistes : retrouver un médecin quel que soit sa saisie, sans doublon."""

import re
import unicodedata

from django.core.exceptions import ValidationError


def cle_ophtalmologue(nom):
    """« Dr. Ben-Salah » → « ben salah » : sans titre, accents, casse ni ponctuation."""
    texte = unicodedata.normalize("NFKD", str(nom or "")).encode("ascii", "ignore").decode()
    mots = re.sub(r"[^a-z0-9]+", " ", texte.lower()).split()
    while mots and mots[0] in {"dr", "docteur", "doctor", "pr", "professeur"}:
        mots.pop(0)
    return " ".join(mots)


def ophtalmologue_existant(nom):
    from .models import Ophtalmologue

    cle = cle_ophtalmologue(nom)
    return Ophtalmologue.objects.filter(cle=cle).first() if cle else None


def ophtalmologue_de_l_ordonnance(nom):
    """Médecin de la liste pour ce nom ; ajouté à la liste s'il n'y est pas encore."""
    from .models import Ophtalmologue

    if not cle_ophtalmologue(nom):
        raise ValidationError("Nom de l'ophtalmologiste à préciser.")
    existant = ophtalmologue_existant(nom)
    if existant is not None:
        return existant
    return Ophtalmologue.objects.create(nom=nom)
