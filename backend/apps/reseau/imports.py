"""Import des dépôts (fichier Excel .xlsx ou CSV).

Le fichier « Depot » de l'ancien logiciel s'importe tel quel : CodeDepot, Libelle, Adresse,
Ville, Tel, EtatInventaire, NomBaseCentrale, CodeMagasin. EtatInventaire et NomBaseCentrale
sont ignorés (l'état d'inventaire est calculé dans OptiLink). Une colonne Type (vente, central,
casse) est facultative : sans elle, le type se déduit du code et du libellé (« CASSE » → casse,
« Central » ou DEPCEN → central, sinon vente).

Le dépôt de vente créé avec chaque magasin (et le dépôt central repris de l'ancien « magasin
dépôt ») reçoit le code et le libellé du fichier au lieu d'être doublé. Un dépôt sans magasin
dans le fichier est rattaché au magasin du dépôt central.
"""

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.optique.imports import telephone_importe
from apps.stock.imports import Rapport, _Annuler, _message, normaliser

from .models import Depot, Magasin
from .villes import ville_importee

COLONNES_DEPOTS = [
    "CodeDepot",
    "Libelle",
    "Adresse",
    "Ville",
    "Tel",
    "EtatInventaire",
    "NomBaseCentrale",
    "CodeMagasin",
    "Type",
]

TYPES = {
    "vente": Depot.Type.VENTE,
    "depot_de_vente": Depot.Type.VENTE,
    "magasin": Depot.Type.VENTE,
    "central": Depot.Type.CENTRAL,
    "centrale": Depot.Type.CENTRAL,
    "depot_central": Depot.Type.CENTRAL,
    "casse": Depot.Type.CASSE,
    "depot_casse": Depot.Type.CASSE,
}


def _type_deduit(code, libelle):
    texte = f"{normaliser(code)} {normaliser(libelle)}"
    if "casse" in texte:
        return Depot.Type.CASSE
    if "central" in texte or normaliser(code).endswith("cen"):
        return Depot.Type.CENTRAL
    return Depot.Type.VENTE


def _magasin(code, magasins):
    """« 01 » trouve le magasin « 1 » : les zéros de tête ne comptent pas."""
    cle = code.strip().upper().lstrip("0") or "0"
    return magasins.get(cle)


def importer_depots(lignes, *, apercu=False):
    """Crée les dépôts, ou met à jour ceux qui ont déjà ce code."""
    rapport = Rapport(apercu=apercu, lignes=len(lignes))
    entetes = lignes[0][1] if lignes else {}
    absentes = [c for c in ("codedepot", "libelle") if c not in entetes]
    if absentes:
        rapport.erreur(1, "Colonne obligatoire absente : " + ", ".join(absentes) + ".")
        return rapport
    magasins = {(m.code.upper().lstrip("0") or "0"): m for m in Magasin.tous.select_related("pays")}
    # Les dépôts sans magasin passent en dernier : ils rejoignent le magasin du dépôt central.
    ordre = sorted(lignes, key=lambda nl: not nl[1].get("codemagasin", "").strip())
    vus = {}
    try:
        with transaction.atomic():
            for numero, ligne in ordre:
                code = ligne.get("codedepot", "").strip().upper()
                libelle = " ".join(ligne.get("libelle", "").split())
                if not code or not libelle:
                    rapport.erreur(numero, "CodeDepot et Libelle sont obligatoires.")
                    continue
                if code in vus:
                    rapport.erreur(numero, f"CodeDepot : {code} déjà en ligne {vus[code]}.")
                    continue
                vus[code] = numero

                saisi = normaliser(ligne.get("type", ""))
                if saisi and saisi not in TYPES:
                    rapport.erreur(numero, f"Type : « {ligne['type']} » (vente, central ou casse).")
                    continue
                type_ = TYPES[saisi] if saisi else _type_deduit(code, libelle)

                code_magasin = ligne.get("codemagasin", "").strip()
                if code_magasin:
                    magasin = _magasin(code_magasin, magasins)
                    if magasin is None:
                        rapport.erreur(
                            numero, f"CodeMagasin : « {code_magasin} » n'est pas un magasin."
                        )
                        continue
                else:
                    central = Depot.objects.filter(type=Depot.Type.CENTRAL, est_actif=True).first()
                    if central is None:
                        rapport.erreur(numero, "CodeMagasin : obligatoire (aucun dépôt central).")
                        continue
                    magasin = central.magasin
                    rapport.alerte(
                        numero, f"{code} sans magasin : rattaché à {magasin.code} {magasin.nom}."
                    )

                ville, alerte = ville_importee(ligne.get("ville", ""), magasin.pays)
                if alerte:
                    rapport.alerte(numero, alerte)
                valeurs = {
                    "nom": libelle[:100],
                    "adresse": " ".join(ligne.get("adresse", "").split()),
                    "ville": ville,
                    "telephone": telephone_importe(ligne.get("tel", "")),
                    "type": type_,
                }
                try:
                    with transaction.atomic():
                        cree, renomme = _importer(code, magasin, valeurs)
                except ValidationError as erreur:
                    rapport.erreur(numero, _message(erreur))
                    continue
                if renomme:
                    rapport.alerte(
                        numero,
                        f"Le dépôt « {renomme} » de {magasin.nom} devient {code}.",
                    )
                if cree:
                    rapport.crees += 1
                else:
                    rapport.modifies += 1
            if rapport.erreurs or apercu:
                raise _Annuler
    except _Annuler:
        pass
    return rapport


def _importer(code, magasin, valeurs):
    """(créé, ancien code renommé) ; le dépôt déjà créé pour ce magasin est repris."""
    depot = Depot.objects.filter(code__iexact=code).first()
    renomme = ""
    if depot is not None and depot.magasin_id != magasin.pk:
        raise ValidationError(
            f"CodeMagasin : {code} est déjà le dépôt du magasin {depot.magasin.nom}."
        )
    if depot is None and valeurs["type"] in (Depot.Type.VENTE, Depot.Type.CENTRAL):
        depot = Depot.objects.filter(magasin=magasin, type=valeurs["type"]).first()
        renomme = depot.code if depot else ""
    cree = depot is None
    if cree:
        depot = Depot(magasin=magasin)
    depot.code = code
    for champ, valeur in valeurs.items():
        # Une case vide garde la valeur enregistrée.
        if valeur or champ in ("nom", "type"):
            setattr(depot, champ, valeur)
    depot.full_clean()
    depot.save()
    return cree, renomme
