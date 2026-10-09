"""Import des listes de référence des verres et des montures (fichier Excel .xlsx ou CSV).

Familles et sous-familles de verres, couleurs, diamètres, matières, marques de monture : une
ligne par élément, repéré par son code. Réimporter le même code met l'élément à jour (une case
vide garde la valeur enregistrée). Tout le fichier est contrôlé avant d'enregistrer quoi que ce
soit, et l'import exige la vérification, comme les autres imports.
"""

from dataclasses import dataclass, field

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.achats.imports import trouver_fournisseur

from .imports import Rapport, _Annuler, _booleen, _choix, _message
from .models import (
    CouleurVerre,
    DiametreVerre,
    FamilleVerre,
    Foyer,
    MarqueMonture,
    MatiereVerre,
    SousFamilleVerre,
)


@dataclass(frozen=True)
class Liste:
    modele: type
    colonnes: list
    obligatoires: set
    textes: tuple = ()
    choix: dict = field(default_factory=dict)


LISTES = {
    "marques_montures": Liste(
        MarqueMonture, ["code", "libelle", "actif"], {"code", "libelle"}, ("libelle",)
    ),
    "matieres_verres": Liste(
        MatiereVerre, ["code", "libelle", "actif"], {"code", "libelle"}, ("libelle",)
    ),
    "familles_verres": Liste(
        FamilleVerre,
        ["code", "fournisseur", "libelle", "foyer", "actif"],
        {"code", "libelle"},
        ("libelle",),
        {"foyer": Foyer.choices},
    ),
    "sous_familles_verres": Liste(
        SousFamilleVerre,
        ["code", "famille", "libelle", "foyer", "actif"],
        {"code", "famille", "libelle"},
        ("libelle",),
        {"foyer": Foyer.choices},
    ),
    "couleurs_verres": Liste(
        CouleurVerre,
        ["code", "fournisseur", "libelle", "famille_couleur", "actif"],
        {"code", "libelle"},
        ("libelle",),
        {"famille_couleur": CouleurVerre.FamilleCouleur.choices},
    ),
    "diametres_verres": Liste(
        DiametreVerre,
        ["code", "fournisseur", "diametre_reel", "diametre_commercial", "actif"],
        {"code", "diametre_commercial"},
        ("diametre_reel", "diametre_commercial"),
    ),
}


def importer_liste(quoi, lignes, *, apercu=False):
    liste = LISTES[quoi]
    rapport = Rapport(apercu=apercu, lignes=len(lignes))
    colonnes = set(lignes[0][1]) if lignes else set()
    manquantes = liste.obligatoires - colonnes
    if lignes and manquantes:
        rapport.erreur(1, f"Colonnes obligatoires absentes : {', '.join(sorted(manquantes))}.")
        return rapport
    vus = {}
    try:
        with transaction.atomic():
            for numero, ligne in lignes:
                code = ligne.get("code", "").strip()
                if code in vus:
                    rapport.erreur(numero, f"code : {code} déjà en ligne {vus[code]}.")
                    continue
                vus[code] = numero
                try:
                    with transaction.atomic():
                        cree = _importer(liste, code, ligne)
                except ValidationError as erreur:
                    rapport.erreur(numero, _message(erreur))
                    continue
                if cree:
                    rapport.crees += 1
                else:
                    rapport.modifies += 1
            if rapport.erreurs or apercu:
                raise _Annuler
    except _Annuler:
        pass
    return rapport


def _importer(liste, code, ligne):
    if not code:
        raise ValidationError("code : obligatoire.")
    objet = liste.modele.objects.filter(code=code).first()
    cree = objet is None
    if cree:
        objet = liste.modele(code=code)
        for champ in liste.obligatoires - {"code", "famille"}:
            if not ligne.get(champ, "").strip():
                raise ValidationError(f"{champ} : obligatoire.")
    for champ in liste.textes:
        valeur = " ".join(ligne.get(champ, "").split())
        if valeur:
            setattr(objet, champ, valeur)
    for champ, choix in liste.choix.items():
        if ligne.get(champ, "").strip():
            setattr(objet, champ, _choix(ligne[champ].strip(), choix, champ))
    if ligne.get("actif", "").strip():
        objet.est_actif = _booleen(ligne["actif"].strip())
    if "fournisseur" in liste.colonnes and ligne.get("fournisseur", "").strip():
        fournisseur = trouver_fournisseur(ligne["fournisseur"])
        if fournisseur is None:
            raise ValidationError(
                f"fournisseur : « {ligne['fournisseur']} » inconnu ; le créer d'abord."
            )
        objet.fournisseur = fournisseur
    if "famille" in liste.colonnes and ligne.get("famille", "").strip():
        famille = FamilleVerre.objects.filter(code=ligne["famille"].strip()).first()
        if famille is None:
            raise ValidationError(
                f"famille : code « {ligne['famille']} » inconnu ; importer d'abord les familles."
            )
        objet.famille = famille
    if cree and "famille" in liste.colonnes and objet.famille_id is None:
        raise ValidationError("famille : obligatoire.")
    objet.full_clean()
    objet.save()
    return cree
