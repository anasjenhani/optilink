"""Import de la liste des ophtalmologistes (fichier Excel .xlsx ou CSV).

Le fichier « Medecin » de l'ancien logiciel s'importe tel quel (CodeMedecin, Nom, Prenom,
TelCabinet, TelPortable1…). Un médecin présent plusieurs fois (« Rekik Riadh » sur trois
lignes, « Nasri Dhahak » et « Dhahak Nasri ») n'a qu'une fiche : les lignes sont regroupées et
les téléphones manquants complétés. Tout le fichier est contrôlé avant d'enregistrer quoi que
ce soit, et l'import exige la vérification.
"""

import re

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.reseau.villes import ville_importee
from apps.stock.imports import Rapport, _Annuler, _message

from .models import Ophtalmologue
from .ophtalmologues import cle_ophtalmologue

COLONNES_OPHTALMOLOGUES = [
    "ancien_code",
    "nom",
    "prenom",
    "telephone",
    "telephone_2",
    "email",
    "adresse",
    "ville",
]

# Colonnes de l'ancien logiciel (normalisées), par ordre de préférence.
SYNONYMES = {
    "ancien_code": ["codemedecin", "code_medecin", "code"],
    "telephone": ["telcabinet", "tel_cabinet", "tel"],
    "telephone_2": ["telportable1", "telportable2", "teldomicile", "gsm", "portable"],
}


def _colonnes(ligne):
    """Ligne au format du modèle : les noms de l'ancien logiciel sont repris."""
    resultat = {c: ligne.get(c, "").strip() for c in COLONNES_OPHTALMOLOGUES}
    for colonne, autres in SYNONYMES.items():
        valeurs = [ligne.get(a, "").strip() for a in autres]
        valeurs = [v for v in valeurs if v]
        if colonne == "telephone_2" and not resultat["telephone"] and valeurs:
            resultat["telephone"] = valeurs.pop(0)
        if not resultat[colonne] and valeurs:
            resultat[colonne] = valeurs[0]
    return resultat


def telephone_importe(texte):
    """« 71 294 677 », « 71.860.266 », « 74406004  fax », « 71902400 / 71906096 » → 1er numéro."""
    numero = re.search(r"\+?\d[\d .]*\d", texte or "")
    return re.sub(r"[ .]", "", numero.group()) if numero else ""


def nom_affiche(nom, prenom):
    """« ben salah », « chedly » → « BEN SALAH Chedly »."""
    nom, prenom = " ".join(nom.split()), " ".join(prenom.split())
    return " ".join(p for p in (nom.upper(), prenom.title()) if p)


def importer_ophtalmologues(lignes, *, apercu=False):
    """Crée les médecins, ou complète la fiche de ceux déjà dans la liste."""
    rapport = Rapport(apercu=apercu, lignes=len(lignes))
    if lignes and "nom" not in lignes[0][1]:
        rapport.erreur(1, "Colonne obligatoire absente : nom.")
        return rapport
    vus = {}
    try:
        with transaction.atomic():
            for numero, brute in lignes:
                ligne = _colonnes(brute)
                nom = nom_affiche(ligne["nom"], ligne["prenom"])
                cle = cle_ophtalmologue(nom)
                if not cle:
                    rapport.erreur(numero, "nom : obligatoire.")
                    continue
                for champ in ("telephone", "telephone_2"):
                    ligne[champ] = telephone_importe(ligne[champ])
                if ligne["ville"].isdigit():
                    # Code de ville de l'ancien logiciel, sans sa table : on ne le garde pas.
                    ligne["ville"] = ""
                if ligne["ville"]:
                    ligne["ville"], alerte = ville_importee(ligne["ville"])
                    if alerte:
                        rapport.alerte(numero, alerte)
                try:
                    with transaction.atomic():
                        medecin, cree = _importer(cle, nom, ligne)
                except ValidationError as erreur:
                    rapport.erreur(numero, _message(erreur))
                    continue
                if cle in vus:
                    rapport.alerte(
                        numero, f"{medecin.nom} déjà en ligne {vus[cle]} : fiches regroupées."
                    )
                elif cree:
                    rapport.crees += 1
                else:
                    rapport.modifies += 1
                    rapport.alerte(
                        numero, f"{medecin.nom} est déjà dans la liste : sa fiche est complétée."
                    )
                vus.setdefault(cle, numero)
            if rapport.erreurs or apercu:
                raise _Annuler
    except _Annuler:
        pass
    return rapport


def _importer(cle, nom, ligne):
    medecin = Ophtalmologue.objects.filter(cle=cle).first()
    cree = medecin is None
    if cree:
        medecin = Ophtalmologue(nom=nom)
    # Une case vide, ou déjà remplie, garde la valeur enregistrée : on complète la fiche.
    for champ in ("telephone", "telephone_2", "email", "adresse", "ville"):
        valeur = " ".join(ligne[champ].split())
        if valeur and not getattr(medecin, champ):
            setattr(medecin, champ, valeur)
    if medecin.telephone_2 == medecin.telephone:
        medecin.telephone_2 = ""
    if ligne["ancien_code"]:
        codes = [c for c in medecin.anciens_codes.split(", ") if c]
        if ligne["ancien_code"] not in codes:
            medecin.anciens_codes = ", ".join([*codes, ligne["ancien_code"]])
    medecin.adresse = medecin.adresse[:255]
    medecin.full_clean(exclude=["cle", "nom"] if not cree else ["cle"])
    medecin.save()
    return medecin, cree
