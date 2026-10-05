"""Factures achat : une facture fournisseur regroupe des bons de réception (BL) du magasin."""

from collections import defaultdict
from decimal import Decimal

from django.db import transaction

from apps.ventes.models import TypeDocument
from apps.ventes.services import _aujourd_hui, _numero, _prochain_numero, arrondir

from .models import BonReception, FactureAchat
from .receptions import CENT, detail_tva


class FactureImpossible(Exception):
    pass


def calculer_facture(
    bons,
    *,
    pays,
    taux_remise_ex=Decimal("0"),
    frais=Decimal("0"),
    timbre=Decimal("0"),
    ajustement=Decimal("0"),
):
    """Totaux d'une facture à partir des totaux figés de ses bons.

    La remise exceptionnelle de la facture s'applique au net HT des bons, et dans la même
    proportion au FODEC et à la TVA. Timbre, frais et ajustement s'ajoutent au TTC.
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
    return BonReception.objects.filter(
        magasin=magasin, fournisseur=fournisseur, facture__isnull=True
    ).order_by("date_bl", "sequence")


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
    for bon in bons:
        if bon.magasin_id != magasin.pk or bon.fournisseur_id != fournisseur.pk:
            raise FactureImpossible(
                f"Le bon {bon.numero} n'est pas un BL de {fournisseur} dans ce magasin."
            )
        if bon.facture_id is not None:
            raise FactureImpossible(f"Le bon {bon.numero} (BL {bon.numero_bl}) est déjà facturé.")
    return sorted(bons, key=lambda b: (b.date_bl, b.sequence))


@transaction.atomic
def enregistrer_facture(
    *,
    magasin,
    fournisseur,
    reference_fournisseur,
    date_reference,
    bons,
    auteur,
    date_entree=None,
    taux_remise_ex=Decimal("0"),
    frais=Decimal("0"),
    timbre=None,
    ajustement=Decimal("0"),
    observation="",
):
    """Enregistre la facture et marque ses bons « Facturé »."""
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
    pays = magasin.pays
    timbre = timbre_par_defaut(fournisseur, pays) if timbre is None else timbre
    if timbre < 0:
        raise FactureImpossible("Le timbre fiscal ne peut pas être négatif.")
    totaux, _ = calculer_facture(
        bons,
        pays=pays,
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
    return facture
