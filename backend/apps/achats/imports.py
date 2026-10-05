"""Import des fournisseurs et des bons de réception depuis un fichier Excel (.xlsx) ou CSV.

Mêmes règles que les autres imports : tout le fichier est contrôlé avant d'enregistrer quoi que
ce soit, une vérification sans erreur précède l'import, et ce qui existe déjà est signalé.
"""

from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.reseau.models import Pays
from apps.stock.imports import (
    Rapport,
    _Annuler,
    _booleen,
    _choix,
    _decimal,
    _entier,
    _message,
    normaliser,
)
from apps.stock.models import Article

from .models import Fournisseur
from .receptions import ReceptionImpossible, enregistrer_reception, taux_tva_par_defaut

COLONNES_FOURNISSEURS = [
    "code",
    "raison_sociale",
    "notre_code",
    "responsable",
    "fournisseur_verres",
    "matricule_fiscal",
    "registre_commerce",
    "code_douane",
    "forme_juridique",
    "capital_social",
    "timbre_fiscal",
    "assujetti",
    "fodec",
    "regime_tva",
    "numero_exoneration",
    "exoneration_du",
    "exoneration_au",
    "adresse",
    "code_postal",
    "ville",
    "pays",
    "telephone",
    "telephone_2",
    "fax",
    "email",
    "site_web",
    "banque",
    "rib",
    "observation",
]

COLONNES_RECEPTIONS = [
    "numero_bl",
    "date_bl",
    "fournisseur",
    "code_barres",
    "reference",
    "quantite",
    "prix_achat_ht",
    "taux_remise",
    "taux_tva",
    "numero_lot",
    "date_peremption",
    "numero_serie",
    "observation",
]

FORMATS_DATE = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y"]
_TEXTES = [
    "notre_code",
    "responsable",
    "matricule_fiscal",
    "registre_commerce",
    "code_douane",
    "numero_exoneration",
    "adresse",
    "code_postal",
    "ville",
    "telephone",
    "telephone_2",
    "fax",
    "email",
    "site_web",
    "banque",
    "rib",
    "observation",
]
_BOOLEENS = ["fournisseur_verres", "timbre_fiscal", "assujetti", "fodec"]
# « Payer TVA » (comme l'écran de l'ancien logiciel), « TVA », « Assujetti » : même régime.
_REGIMES_TVA = [
    *Fournisseur.RegimeTva.choices,
    (Fournisseur.RegimeTva.ASSUJETTI, "Payer TVA"),
    (Fournisseur.RegimeTva.ASSUJETTI, "TVA"),
    (Fournisseur.RegimeTva.EXONERATION, "Exonere"),
]


def _date(texte, nom):
    if texte == "":
        return None
    for format_ in FORMATS_DATE:
        try:
            return datetime.strptime(texte, format_).date()
        except ValueError:
            continue
    raise ValidationError(f"{nom} : « {texte} » n'est pas une date (jj/mm/aaaa).")


def trouver_fournisseur(texte):
    """Fournisseur par son code (« 5 ») ou sa raison sociale, actif ou non."""
    texte = texte.strip()
    if texte.isdigit():
        trouve = Fournisseur.objects.filter(code=int(texte)).first()
        if trouve:
            return trouve
    cle = normaliser(texte)
    return next((f for f in Fournisseur.objects.all() if normaliser(f.nom) == cle), None)


def _existant(ligne):
    """Fiche déjà créée : par code, sinon par matricule fiscal, sinon par raison sociale."""
    code = ligne.get("code", "")
    if code:
        if not code.isdigit():
            raise ValidationError(f"code : « {code} » doit être un nombre.")
        trouve = Fournisseur.objects.filter(code=int(code)).first()
        if trouve is None:
            raise ValidationError(
                f"code : aucun fournisseur n° {code}. Laisser la colonne vide pour en créer un "
                "(le code est attribué automatiquement)."
            )
        return trouve, "code"
    matricule = ligne.get("matricule_fiscal", "")
    if matricule:
        trouve = Fournisseur.objects.filter(matricule_fiscal__iexact=matricule).first()
        if trouve:
            return trouve, "matricule fiscal"
    cle = normaliser(ligne["raison_sociale"])
    trouve = next((f for f in Fournisseur.objects.all() if normaliser(f.nom) == cle), None)
    return trouve, "raison sociale"


def importer_fournisseurs(lignes, *, pays, apercu=False):
    """Crée les fournisseurs (code attribué) ou met à jour ceux déjà créés."""
    rapport = Rapport(apercu=apercu, lignes=len(lignes))
    if "raison_sociale" not in (lignes[0][1] if lignes else {}):
        rapport.erreur(1, "Colonne obligatoire absente : raison_sociale.")
        return rapport
    vues, matricules = {}, {}
    try:
        with transaction.atomic():
            for numero, ligne in lignes:
                cle = normaliser(ligne["raison_sociale"])
                if cle and cle in vues:
                    rapport.erreur(numero, f"{ligne['raison_sociale']} déjà en ligne {vues[cle]}.")
                    continue
                vues[cle] = numero
                matricule = ligne.get("matricule_fiscal", "").upper()
                if matricule and matricule in matricules:
                    rapport.erreur(
                        numero,
                        f"matricule_fiscal : {ligne['matricule_fiscal']} déjà en ligne "
                        f"{matricules[matricule]}.",
                    )
                    continue
                if matricule:
                    matricules[matricule] = numero
                try:
                    with transaction.atomic():
                        fournisseur, cree, par = _importer_fournisseur(ligne, pays)
                except ValidationError as erreur:
                    rapport.erreur(numero, _message(erreur))
                    continue
                if cree:
                    rapport.crees += 1
                else:
                    rapport.modifies += 1
                    rapport.alerte(
                        numero,
                        f"{fournisseur.nom} existe déjà (code {fournisseur.code}, même {par}) : "
                        "sa fiche sera mise à jour.",
                    )
            if rapport.erreurs or apercu:
                raise _Annuler
    except _Annuler:
        pass
    return rapport


def _importer_fournisseur(ligne, pays):
    if not ligne["raison_sociale"]:
        raise ValidationError("raison_sociale : obligatoire.")
    fournisseur, par = _existant(ligne)
    cree = fournisseur is None
    if cree:
        fournisseur = Fournisseur(pays=pays)
    if cree or par != "raison sociale":
        # Même raison sociale à la casse près : on garde l'écriture déjà enregistrée.
        fournisseur.nom = ligne["raison_sociale"]
    for champ in _TEXTES:
        if champ in ligne:
            setattr(fournisseur, champ, ligne[champ])
    for champ in _BOOLEENS:
        if ligne.get(champ, "") != "":
            setattr(fournisseur, champ, _booleen(ligne[champ]))
    if "forme_juridique" in ligne:
        fournisseur.forme_juridique = _choix(
            ligne["forme_juridique"], Fournisseur.FormeJuridique.choices, "forme_juridique"
        )
    if ligne.get("regime_tva", ""):
        fournisseur.regime_tva = _choix(ligne["regime_tva"], _REGIMES_TVA, "regime_tva")
    if "capital_social" in ligne:
        fournisseur.capital_social = _decimal(ligne["capital_social"], "capital_social")
    for champ in ("exoneration_du", "exoneration_au"):
        if champ in ligne:
            setattr(fournisseur, champ, _date(ligne[champ], champ))
    if ligne.get("pays", ""):
        autre = Pays.objects.filter(code__iexact=ligne["pays"]).first()
        if autre is None:
            raise ValidationError(f"pays : code « {ligne['pays']} » inconnu (ex. TN, FR).")
        fournisseur.pays = autre
    matricule = fournisseur.matricule_fiscal
    if matricule:
        double = Fournisseur.objects.filter(matricule_fiscal__iexact=matricule).exclude(
            pk=fournisseur.pk
        )
        if double.exists():
            raise ValidationError(
                f"matricule_fiscal : {matricule} est déjà celui de {double.first().nom}."
            )
    fournisseur.full_clean(exclude=["code"])
    fournisseur.save()
    return fournisseur, cree, par


def _article(ligne):
    code, reference = ligne.get("code_barres", ""), ligne.get("reference", "")
    article = None
    if code:
        article = Article.objects.filter(code_barres=code, est_actif=True).first()
    if article is None and reference:
        article = Article.objects.filter(reference=reference, est_actif=True).first()
    if article is None:
        raise ValidationError(f"Article inconnu : {code or reference or '(vide)'}.")
    if article.sur_commande:
        raise ValidationError(
            f"{article.reference} est commandé pour un client : le recevoir avec « Importer Bon "
            "Commande » dans l'écran Bon de Réception."
        )
    return article


def importer_receptions(lignes, *, magasin, utilisateur, apercu=False):
    """Un bon de réception par couple (fournisseur, n° de BL), une ligne par article reçu."""
    rapport = Rapport(apercu=apercu, lignes=len(lignes))
    colonnes = set(lignes[0][1]) if lignes else set()
    manquantes = {"numero_bl", "fournisseur", "quantite", "prix_achat_ht"} - colonnes
    if not colonnes & {"code_barres", "reference"}:
        manquantes.add("code_barres ou reference")
    if manquantes:
        rapport.erreur(1, f"Colonnes obligatoires absentes : {', '.join(sorted(manquantes))}.")
        return rapport

    bons = defaultdict(list)
    entetes = {}
    for numero, ligne in lignes:
        try:
            if not ligne["numero_bl"]:
                raise ValidationError("numero_bl : obligatoire.")
            fournisseur = trouver_fournisseur(ligne["fournisseur"])
            if fournisseur is None:
                raise ValidationError(
                    f"fournisseur : « {ligne['fournisseur']} » inconnu ; le créer d'abord "
                    "(écran Fournisseurs ou import des fournisseurs)."
                )
            article = _article(ligne)
            quantite = _entier(ligne["quantite"], "quantite")
            if not quantite or quantite < 1:
                raise ValidationError("quantite : un nombre entier positif.")
            prix = _decimal(ligne["prix_achat_ht"], "prix_achat_ht")
            if prix is None or prix < 0:
                raise ValidationError("prix_achat_ht : obligatoire.")
            detail = {
                "article": article,
                "quantite": quantite,
                "prix_achat_ht": prix,
                "taux_remise": _decimal(ligne.get("taux_remise", ""), "taux_remise")
                or Decimal("0"),
                "taux_tva": _decimal(ligne.get("taux_tva", ""), "taux_tva"),
                "non_conforme": False,
                "motif": "",
                "numero_lot": ligne.get("numero_lot", ""),
                "numero_serie": ligne.get("numero_serie", ""),
                "date_peremption": _date(ligne.get("date_peremption", ""), "date_peremption"),
            }
            date_bl = _date(ligne.get("date_bl", ""), "date_bl")
        except ValidationError as erreur:
            rapport.erreur(numero, _message(erreur))
            continue
        cle = (fournisseur.pk, ligne["numero_bl"])
        entetes.setdefault(
            cle,
            {
                "fournisseur": fournisseur,
                "numero_bl": ligne["numero_bl"],
                "date_bl": date_bl,
                "observation": ligne.get("observation", ""),
                "premiere": numero,
            },
        )
        bons[cle].append(detail)
    if rapport.erreurs:
        return rapport

    try:
        with transaction.atomic():
            for cle, details in bons.items():
                entete = entetes[cle]
                sans_taux = [d["article"] for d in details if d["taux_tva"] is None]
                defauts = taux_tva_par_defaut(sans_taux, magasin.pays) if sans_taux else {}
                for d in details:
                    if d["taux_tva"] is None:
                        d["taux_tva"] = defauts[d["article"].pk]
                try:
                    with transaction.atomic():
                        bon = enregistrer_reception(
                            magasin=magasin,
                            fournisseur=entete["fournisseur"],
                            numero_bl=entete["numero_bl"],
                            date_bl=entete["date_bl"] or datetime.now().date(),
                            lignes=details,
                            auteur=utilisateur,
                            observation=entete["observation"],
                        )
                except (ReceptionImpossible, ValidationError) as erreur:
                    message = (
                        _message(erreur) if isinstance(erreur, ValidationError) else str(erreur)
                    )
                    rapport.erreur(entete["premiere"], f"BL {entete['numero_bl']} : {message}")
                    continue
                rapport.crees += 1
                rapport.alerte(
                    entete["premiere"],
                    f"BL {bon.numero_bl} de {bon.fournisseur.nom} : {len(details)} article(s), "
                    f"{bon.total_ttc} TTC.",
                )
            if rapport.erreurs or apercu:
                raise _Annuler
    except _Annuler:
        pass
    return rapport
