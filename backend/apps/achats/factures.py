"""Factures achat : une facture fournisseur regroupe des bons de réception (BL) du magasin."""

from collections import defaultdict
from decimal import Decimal

from django.db import transaction

from apps.ventes.models import TypeDocument
from apps.ventes.services import _aujourd_hui, _numero, _prochain_numero, arrondir

from .depot import autre_depot, magasins_geres
from .models import BonReception, BonRetour, FactureAchat
from .receptions import CENT, detail_tva
from .retours import detail_tva_retour


class FactureImpossible(Exception):
    pass


def calculer_facture(
    bons,
    *,
    pays,
    retours=(),
    taux_remise_ex=Decimal("0"),
    frais=Decimal("0"),
    timbre=Decimal("0"),
    ajustement=Decimal("0"),
):
    """Totaux d'une facture à partir des totaux figés de ses bons, moins ses bons retour.

    La remise exceptionnelle de la facture s'applique au net HT (BL moins retours), et dans la
    même proportion au FODEC et à la TVA. Timbre, frais et ajustement s'ajoutent au TTC.
    """
    decimales = pays.decimales
    total_ht = total_remise = net = fodec = Decimal("0")
    bases, montants = defaultdict(Decimal), defaultdict(Decimal)
    for bon in bons:
        total_ht += bon.total_ht
        total_remise += bon.total_remise + bon.remise_ex
        net += bon.total_net_ht
        fodec += bon.total_fodec
        for ligne in detail_tva(bon):
            bases[ligne["taux"]] += ligne["base_ht"]
            montants[ligne["taux"]] += ligne["montant_tva"]
    for retour in retours:
        total_ht -= retour.total_ht
        total_remise -= retour.total_remise
        net -= retour.total_net_ht
        fodec -= retour.total_fodec
        for ligne in detail_tva_retour(retour):
            bases[ligne["taux"]] -= ligne["base_ht"]
            montants[ligne["taux"]] -= ligne["montant_tva"]
    reste = 1 - taux_remise_ex / CENT
    remise_ex = arrondir(net * taux_remise_ex / CENT, decimales)
    tva = []
    for taux in sorted({*pays.taux_tva.values_list("taux", flat=True), *bases}):
        tva.append(
            {
                "taux": taux,
                "base_ht": arrondir(bases[taux] * reste, decimales),
                "montant_tva": arrondir(montants[taux] * reste, decimales),
            }
        )
    total_net_ht = net - remise_ex
    total_fodec = arrondir(fodec * reste, decimales)
    total_tva = sum((t["montant_tva"] for t in tva), Decimal("0"))
    return {
        "total_ht": total_ht,
        "total_remise": total_remise,
        "remise_ex": remise_ex,
        "total_net_ht": total_net_ht,
        "total_fodec": total_fodec,
        "total_tva": total_tva,
        "total_ttc": total_net_ht + total_fodec + total_tva + timbre + frais + ajustement,
    }, tva


def timbre_par_defaut(fournisseur, pays):
    """Timbre fiscal du pays si le fournisseur le facture (case de sa fiche), sinon 0."""
    return pays.timbre_fiscal if fournisseur.timbre_fiscal else Decimal("0")


def bons_a_facturer(magasin, fournisseur):
    """BL non facturés de ce fournisseur : ceux du magasin, et pour un dépôt de sa société."""
    return BonReception.objects.filter(
        magasin_id__in=magasins_geres(magasin), fournisseur=fournisseur, facture__isnull=True
    ).order_by("date_bl", "sequence")


def retours_a_deduire(magasin, fournisseur):
    """Bons retour de ce fournisseur saisis ici et pas encore déduits d'une facture."""
    return BonRetour.objects.filter(
        magasin=magasin, fournisseur=fournisseur, facture__isnull=True
    ).order_by("date_retour", "sequence")


def controler(magasin, fournisseur, bons_ids, *, verrouiller=False):
    """Bons choisis, tous de ce fournisseur, de ce magasin et pas encore facturés."""
    if not bons_ids:
        raise FactureImpossible("Importez au moins un bon de livraison (BL).")
    bons = BonReception.objects.filter(public_id__in=bons_ids)
    if verrouiller:
        bons = bons.select_for_update(of=("self",))
    bons = list(bons.select_related("magasin__pays", "fournisseur").prefetch_related("lignes"))
    if len(bons) != len(set(bons_ids)):
        raise FactureImpossible("Bon de réception introuvable ou hors de votre périmètre.")
    geres = set(magasins_geres(magasin))
    for bon in bons:
        if bon.magasin_id not in geres or bon.fournisseur_id != fournisseur.pk:
            raise FactureImpossible(
                f"Le bon {bon.numero} n'est pas un BL de {fournisseur} dans ce magasin."
            )
        if bon.facture_id is not None:
            raise FactureImpossible(f"Le bon {bon.numero} (BL {bon.numero_bl}) est déjà facturé.")
    return sorted(bons, key=lambda b: (b.date_bl, b.sequence))


def controler_retours(magasin, fournisseur, retours_ids, *, verrouiller=False):
    """Bons retour choisis, tous de ce fournisseur, saisis ici et pas encore déduits."""
    if not retours_ids:
        return []
    retours = BonRetour.objects.filter(public_id__in=retours_ids)
    if verrouiller:
        retours = retours.select_for_update(of=("self",))
    retours = list(
        retours.select_related("magasin__pays", "fournisseur").prefetch_related("lignes")
    )
    if len(retours) != len(set(retours_ids)):
        raise FactureImpossible("Bon retour introuvable ou hors de votre périmètre.")
    for retour in retours:
        if retour.magasin_id != magasin.pk or retour.fournisseur_id != fournisseur.pk:
            raise FactureImpossible(
                f"Le bon retour {retour.numero} n'est pas un retour à {fournisseur} d'ici."
            )
        if retour.facture_id is not None:
            raise FactureImpossible(f"Le bon retour {retour.numero} est déjà déduit.")
    return sorted(retours, key=lambda r: (r.date_retour, r.sequence))


def exiger_depot(magasin):
    depot = autre_depot(magasin)
    if depot is not None:
        raise FactureImpossible(f"Les factures achat se saisissent au dépôt central ({depot.nom}).")


@transaction.atomic
def enregistrer_facture(
    *,
    magasin,
    fournisseur,
    reference_fournisseur,
    date_reference,
    bons,
    auteur,
    retours=(),
    date_entree=None,
    taux_remise_ex=Decimal("0"),
    frais=Decimal("0"),
    timbre=None,
    ajustement=Decimal("0"),
    observation="",
):
    """Enregistre la facture, marque ses bons « Facturé » et ses bons retour « Déduit »."""
    exiger_depot(magasin)
    reference_fournisseur = reference_fournisseur.strip()
    if not reference_fournisseur:
        raise FactureImpossible("Référence fournisseur (n° de sa facture) obligatoire.")
    deja = FactureAchat.tous.filter(
        fournisseur=fournisseur, reference_fournisseur__iexact=reference_fournisseur
    ).first()
    if deja:
        raise FactureImpossible(
            f"La facture {reference_fournisseur} de {fournisseur} est déjà saisie ({deja.numero})."
        )
    if not 0 <= taux_remise_ex <= 100:
        raise FactureImpossible("Remise exceptionnelle entre 0 et 100 %.")
    if frais < 0:
        raise FactureImpossible("Les frais supplémentaires ne peuvent pas être négatifs.")
    bons = controler(magasin, fournisseur, bons, verrouiller=True)
    retours = controler_retours(magasin, fournisseur, retours, verrouiller=True)
    pays = magasin.pays
    timbre = timbre_par_defaut(fournisseur, pays) if timbre is None else timbre
    if timbre < 0:
        raise FactureImpossible("Le timbre fiscal ne peut pas être négatif.")
    totaux, _ = calculer_facture(
        bons,
        pays=pays,
        retours=retours,
        taux_remise_ex=taux_remise_ex,
        frais=frais,
        timbre=timbre,
        ajustement=ajustement,
    )
    annee = _aujourd_hui(pays).year
    sequence = _prochain_numero(magasin, annee, TypeDocument.FACTURE_ACHAT)
    facture = FactureAchat.tous.create(
        magasin=magasin,
        numero=_numero(magasin, TypeDocument.FACTURE_ACHAT, annee, sequence),
        annee=annee,
        sequence=sequence,
        fournisseur=fournisseur,
        date_entree=date_entree or _aujourd_hui(pays),
        reference_fournisseur=reference_fournisseur,
        date_reference=date_reference,
        taux_remise_ex=taux_remise_ex,
        frais_supplementaires=frais,
        timbre_fiscal=timbre,
        ajustement=ajustement,
        observation=observation,
        cree_par=auteur,
        **totaux,
    )
    BonReception.tous.filter(pk__in=[b.pk for b in bons]).update(
        facture=facture, etat=BonReception.Etat.FACTURE, numero_facture=reference_fournisseur
    )
    BonRetour.tous.filter(pk__in=[r.pk for r in retours]).update(
        facture=facture, etat=BonRetour.Etat.FACTURE
    )
    return facture
