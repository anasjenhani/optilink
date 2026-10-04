"""Lecture en français du journal d'audit pour les droits : profils, affectations et comptes."""

import datetime

from django.contrib.auth.models import Permission

from .privileges import PRIVILEGES

LIBELLES_PRIVILEGES = {
    code: libelle for module in PRIVILEGES.values() for code, libelle in module.items()
}

# Champs montrés, avec leur libellé ; les autres (id, dates techniques) sont omis.
CHAMPS = {
    "auth.group": {"name": "Nom du profil"},
    "securite.affectation": {
        "utilisateur": "Utilisateur",
        "role": "Profil",
        "portee": "Portée",
        "magasin": "Magasin",
        "societe": "Société",
        "debut": "Début",
        "fin": "Fin",
    },
    "securite.utilisateur": {
        "username": "Identifiant",
        "first_name": "Prénom",
        "last_name": "Nom",
        "email": "E-mail",
        "is_active": "Compte actif",
        "is_staff": "Accès à l'administration",
        "is_superuser": "Super-administrateur",
    },
}
TYPES = {
    "auth.group": "Profil",
    "securite.affectation": "Profil donné",
    "securite.utilisateur": "Compte",
}
OUI_NON = {"True": "oui", "False": "non"}
VIDE = {"None", ""}


def _cle(entree):
    return f"{entree.content_type.app_label}.{entree.content_type.model}"


def type_d_objet(entree):
    return TYPES.get(_cle(entree), entree.content_type.name)


def libelles_permissions():
    """« Ventes | vente | Peut appliquer une remise » → « Accorder une remise » (catalogue)."""
    libelles = {}
    for permission in Permission.objects.select_related("content_type"):
        code = f"{permission.content_type.app_label}.{permission.codename}"
        libelles[str(permission)] = LIBELLES_PRIVILEGES.get(code, str(permission))
    return libelles


def _afficher(modele, nom, valeur):
    """Valeur enregistrée (texte) → libellé : nom du profil, du magasin, de la portée…"""
    valeur = str(valeur)
    if valeur in VIDE:
        return "(vide)"
    champ = modele._meta.get_field(nom)
    if champ.choices:
        return str(dict(champ.choices).get(valeur, valeur))
    if champ.many_to_one:
        objet = champ.related_model._base_manager.filter(pk=valeur).first()
        return str(objet) if objet else f"n° {valeur} (supprimé)"
    if champ.get_internal_type() == "DateField":
        return datetime.date.fromisoformat(valeur).strftime("%d/%m/%Y")
    return OUI_NON.get(valeur, valeur)


def decrire(entree, libelles=None):
    """Lignes lisibles : « Profil : Vendeur → Caissier », « Privilèges ajoutés : … »."""
    champs = CHAMPS.get(_cle(entree), {})
    lignes = []
    changements = entree.changes_dict or {}
    for nom, valeurs in changements.items():
        if isinstance(valeurs, dict) and valeurs.get("type") == "m2m":
            if libelles is None:
                libelles = libelles_permissions()
            objets = ", ".join(libelles.get(o, o) for o in valeurs.get("objects", []))
            operation = {"add": "ajoutés", "delete": "retirés"}.get(valeurs.get("operation"), "")
            titre = "Privilèges" if nom == "permissions" else "Groupes"
            lignes.append(f"{titre} {operation} : {objets}")
    modele = entree.content_type.model_class()
    for nom, libelle in champs.items():
        if nom not in changements:
            continue
        avant, apres = (_afficher(modele, nom, v) for v in changements[nom])
        if entree.action == entree.Action.UPDATE:
            lignes.append(f"{libelle} : {avant} → {apres}")
            continue
        # Création ou suppression : seulement les champs renseignés.
        valeur = apres if entree.action == entree.Action.CREATE else avant
        if valeur != "(vide)":
            lignes.append(f"{libelle} : {valeur}")
    return lignes
