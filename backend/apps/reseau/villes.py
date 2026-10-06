"""Liste des villes : retrouver la ville d'une fiche, à la casse et aux accents près."""

import unicodedata

from .models import Ville


def normaliser(texte):
    texte = unicodedata.normalize("NFKD", str(texte or "")).encode("ascii", "ignore").decode()
    return " ".join(texte.lower().replace("-", " ").replace("'", " ").split())


def ville_de_la_liste(texte, pays=None):
    """Nom de la ville tel qu'écrit dans la liste, ou ``None`` si elle n'y est pas."""
    cle = normaliser(texte)
    if not cle:
        return None
    villes = Ville.objects.filter(est_active=True)
    if pays is not None:
        villes = villes.filter(pays=pays)
    return next((v.nom for v in villes if normaliser(v.nom) == cle), None)


def valider_ville(texte, pays=None):
    """Ville saisie à l'écran : vide, ou choisie dans la liste (écrite comme dans la liste)."""
    from django.core.exceptions import ValidationError

    if not (texte or "").strip():
        return ""
    if pays is not None and not Ville.objects.filter(pays=pays, est_active=True).exists():
        return texte.strip()  # Pas encore de liste pour ce pays : ville libre.
    nom = ville_de_la_liste(texte, pays)
    if nom is None:
        raise ValidationError(
            f"« {texte} » n'est pas dans la liste des villes : choisissez-en une, ou ajoutez-la "
            "dans Réseau › Villes."
        )
    return nom


def ville_importee(texte, pays=None):
    """Ville lue dans un fichier : écrite comme dans la liste, ou gardée telle quelle avec une
    alerte (un ancien fichier ne doit pas bloquer l'import pour une ville mal écrite)."""
    texte = (texte or "").strip()
    if not texte:
        return "", None
    nom = ville_de_la_liste(texte, pays)
    if nom is not None:
        return nom, None
    if pays is not None and not Ville.objects.filter(pays=pays, est_active=True).exists():
        return texte, None
    return texte, (
        f"Ville « {texte} » absente de la liste des villes : gardée telle quelle. "
        "Ajoutez-la dans Réseau › Villes ou corrigez la fiche."
    )
