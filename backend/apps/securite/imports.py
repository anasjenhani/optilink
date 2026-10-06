"""Création de comptes utilisateurs depuis un fichier Excel (.xlsx) ou CSV.

Chaque compte passe par les mêmes contrôles que l'écran Accès et sécurité : mot de passe
provisoire conforme, identifiant libre, profils et périmètre que le demandeur a le droit de
donner. L'import ne fait que créer : un compte existant se modifie à l'écran.
"""

from types import SimpleNamespace

from django.contrib.auth.models import Group
from django.db import transaction
from rest_framework.exceptions import APIException, ValidationError

from apps.reseau.models import Magasin, Societe
from apps.stock.imports import Rapport, _Annuler, normaliser

from .models import Affectation, Utilisateur

COLONNES_UTILISATEURS = [
    "identifiant",
    "prenom",
    "nom",
    "email",
    "mot_de_passe",
    "profil",
    "magasin",
    "societe",
    "actif",
]

OUI = {"", "oui", "o", "1", "vrai", "actif", "active", "yes", "true"}
NON = {"non", "n", "0", "faux", "inactif", "inactive", "no", "false"}


def _texte_erreur(detail):
    """Message lisible d'une erreur DRF, sans jamais recopier le mot de passe."""
    if isinstance(detail, dict):
        return " ; ".join(f"{cle} : {_texte_erreur(valeur)}" for cle, valeur in detail.items())
    if isinstance(detail, list):
        return " ".join(_texte_erreur(valeur) for valeur in detail)
    return str(detail)


def _affectation(ligne, profils):
    profil = profils.get(normaliser(ligne.get("profil", "")))
    if profil is None:
        raise ValidationError(
            f"profil : « {ligne.get('profil', '')} » inconnu (profils : "
            f"{', '.join(sorted(p.name for p in profils.values()))})."
        )
    if ligne.get("magasin", ""):
        magasin = Magasin.tous.filter(code__iexact=ligne["magasin"]).first()
        if magasin is None:
            raise ValidationError(f"magasin : code « {ligne['magasin']} » inconnu.")
        return {
            "profil": profil.pk,
            "portee": Affectation.Portee.MAGASIN,
            "magasin": magasin.public_id,
        }
    if ligne.get("societe", ""):
        societe = Societe.objects.filter(code__iexact=ligne["societe"]).first()
        if societe is None:
            raise ValidationError(f"societe : code « {ligne['societe']} » inconnu.")
        return {
            "profil": profil.pk,
            "portee": Affectation.Portee.SOCIETE,
            "societe": societe.public_id,
        }
    return {"profil": profil.pk, "portee": Affectation.Portee.RESEAU}


def importer_utilisateurs(lignes, *, demandeur, apercu=False):
    """Une ligne par profil donné ; plusieurs lignes du même identifiant = plusieurs profils."""
    from .api.acces import UtilisateurSerializer

    rapport = Rapport(apercu=apercu, lignes=len(lignes))
    manquantes = {"identifiant", "mot_de_passe", "profil"} - set(lignes[0][1] if lignes else {})
    if manquantes:
        rapport.erreur(1, f"Colonnes obligatoires absentes : {', '.join(sorted(manquantes))}.")
        return rapport
    profils = {normaliser(g.name): g for g in Group.objects.all()}
    comptes = {}
    for numero, ligne in lignes:
        identifiant = ligne["identifiant"]
        if not identifiant:
            rapport.erreur(numero, "identifiant : obligatoire.")
            continue
        try:
            affectation = _affectation(ligne, profils)
        except ValidationError as erreur:
            rapport.erreur(numero, _texte_erreur(erreur.detail))
            continue
        actif = normaliser(ligne.get("actif", ""))
        if actif not in OUI | NON:
            rapport.erreur(numero, f"actif : « {ligne['actif']} » ; écrire oui ou non.")
            continue
        compte = comptes.setdefault(
            identifiant.lower(),
            {
                "premiere": numero,
                "donnees": {
                    "identifiant": identifiant,
                    "prenom": ligne.get("prenom", ""),
                    "nom": ligne.get("nom", ""),
                    "email": ligne.get("email", ""),
                    "mot_de_passe": ligne["mot_de_passe"],
                    "actif": actif not in NON,
                    "affectations": [],
                },
            },
        )
        compte["donnees"]["affectations"].append(affectation)
    if rapport.erreurs:
        return rapport

    contexte = {"request": SimpleNamespace(user=demandeur)}
    try:
        with transaction.atomic():
            for compte in comptes.values():
                identifiant = compte["donnees"]["identifiant"]
                if Utilisateur.objects.filter(username__iexact=identifiant).exists():
                    rapport.erreur(
                        compte["premiere"],
                        f"{identifiant} existe déjà : le modifier dans Accès et sécurité.",
                    )
                    continue
                saisie = UtilisateurSerializer(data=compte["donnees"], context=contexte)
                try:
                    with transaction.atomic():
                        saisie.is_valid(raise_exception=True)
                        saisie.save()
                except APIException as erreur:
                    rapport.erreur(
                        compte["premiere"], f"{identifiant} : {_texte_erreur(erreur.detail)}"
                    )
                    continue
                rapport.crees += 1
            if rapport.erreurs or apercu:
                raise _Annuler
    except _Annuler:
        pass
    return rapport
