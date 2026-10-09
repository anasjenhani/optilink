"""Règlements fournisseurs : paiement des factures achat, avances, retenue à la source."""

from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from apps.ventes.models import TypeDocument
from apps.ventes.services import _numero, _prochain_numero

from .models import FactureAchat, ImputationReglement, ReglementFournisseur

Mode = ReglementFournisseur.Mode
Statut = ReglementFournisseur.Statut
# Modes payés plus tard par la banque : ils passent par l'échéancier.
A_ECHEANCE = (Mode.CHEQUE, Mode.TRAITE)
ZERO = Decimal("0")


class ReglementImpossible(Exception):
    pass


def deja_regle(facture):
    return facture.imputations.aggregate(s=Sum("montant"))["s"] or ZERO


def reste_a_regler(facture):
    return facture.total_ttc - deja_regle(facture)


def disponible(reglement):
    """Avance encore à imputer : réglé (versé + retenue) moins ce qui est déjà imputé."""
    impute = reglement.imputations.aggregate(s=Sum("montant"))["s"] or ZERO
    return reglement.total_regle - impute


def factures_a_regler(magasin, fournisseur):
    """Factures non soldées du fournisseur pour ce magasin, les plus anciennes d'abord."""
    return (
        FactureAchat.objects.filter(magasin=magasin, fournisseur=fournisseur)
        .exclude(paiement=FactureAchat.Paiement.PAYE)
        .order_by("date_reference", "sequence")
    )


def _maj_paiement(factures):
    for facture in factures:
        regle = deja_regle(facture)
        if regle <= 0:
            etat = FactureAchat.Paiement.NON_PAYE
        elif regle < facture.total_ttc:
            etat = FactureAchat.Paiement.PARTIEL
        else:
            etat = FactureAchat.Paiement.PAYE
        if facture.paiement != etat:
            facture.paiement = etat
            facture.save(update_fields=["paiement", "modifie_le"])


def _imputer(reglement, lignes, le):
    """``lignes`` : [(facture, montant)]. Vérifie chaque facture et ce qui reste à imputer."""
    factures = []
    for facture, montant in lignes:
        facture = FactureAchat.tous.select_for_update().get(pk=facture.pk)
        if montant <= 0:
            raise ReglementImpossible(f"{facture.numero} : le montant imputé doit être positif.")
        if facture.magasin_id != reglement.magasin_id or (
            facture.fournisseur_id != reglement.fournisseur_id
        ):
            raise ReglementImpossible(
                f"{facture.numero} : facture d'un autre magasin ou d'un autre fournisseur."
            )
        reste = reste_a_regler(facture)
        if montant > reste:
            raise ReglementImpossible(f"{facture.numero} : il reste {reste} à régler, pas plus.")
        ImputationReglement.objects.create(
            reglement=reglement, facture=facture, montant=montant, le=le
        )
        factures.append(facture)
    if disponible(reglement) < 0:
        raise ReglementImpossible(
            "Les factures imputées dépassent le montant réglé (versé + retenue)."
        )
    _maj_paiement(factures)


@transaction.atomic
def regler(
    *,
    magasin,
    fournisseur,
    date_reglement,
    mode,
    montant,
    utilisateur,
    lignes=(),
    taux_retenue=ZERO,
    retenue=ZERO,
    reference="",
    banque="",
    echeance=None,
    observation="",
):
    """Enregistre un paiement au fournisseur et l'impute sur ses factures.

    ``montant`` est ce qui est versé ; la retenue à la source s'y ajoute pour solder les
    factures. Ce qui dépasse les factures imputées reste en avance.
    """
    if montant < 0 or retenue < 0 or montant + retenue <= 0:
        raise ReglementImpossible("Indiquer le montant versé.")
    if retenue and not lignes:
        raise ReglementImpossible("La retenue à la source porte sur des factures : en choisir.")
    if mode in A_ECHEANCE and not reference.strip():
        raise ReglementImpossible("Indiquer le n° du chèque ou de la traite.")
    if echeance and echeance < date_reglement:
        raise ReglementImpossible("L'échéance ne peut pas précéder la date du règlement.")
    a_echoir = mode in A_ECHEANCE
    annee = date_reglement.year
    sequence = _prochain_numero(magasin, annee, TypeDocument.REGLEMENT_FOURNISSEUR)
    reglement = ReglementFournisseur.tous.create(
        magasin=magasin,
        numero=_numero(magasin, TypeDocument.REGLEMENT_FOURNISSEUR, annee, sequence),
        annee=annee,
        sequence=sequence,
        fournisseur=fournisseur,
        date_reglement=date_reglement,
        mode=mode,
        reference=reference.strip(),
        banque=banque.strip(),
        echeance=(echeance or date_reglement) if a_echoir else None,
        statut=Statut.A_ECHOIR if a_echoir else Statut.DEBITE,
        debite_le=None if a_echoir else date_reglement,
        montant=montant,
        taux_retenue=taux_retenue,
        retenue=retenue,
        observation=observation,
        cree_par=utilisateur,
    )
    _imputer(reglement, lignes, date_reglement)
    return reglement


@transaction.atomic
def imputer_avance(reglement, *, lignes, le):
    """Affecte l'avance restante d'un règlement à des factures arrivées depuis."""
    reglement = ReglementFournisseur.tous.select_for_update().get(pk=reglement.pk)
    if not lignes:
        raise ReglementImpossible("Choisir les factures à solder avec l'avance.")
    _imputer(reglement, lignes, le)
    return reglement


@transaction.atomic
def debiter(reglement, *, le):
    """Le chèque ou la traite est passé à la banque : il sort de l'échéancier."""
    reglement = ReglementFournisseur.tous.select_for_update().get(pk=reglement.pk)
    if reglement.statut != Statut.A_ECHOIR:
        raise ReglementImpossible(f"Le règlement {reglement.numero} est déjà débité.")
    if le < reglement.date_reglement:
        raise ReglementImpossible("Le débit ne peut pas précéder la date du règlement.")
    reglement.statut, reglement.debite_le = Statut.DEBITE, le
    reglement.save(update_fields=["statut", "debite_le", "modifie_le"])
    return reglement


@transaction.atomic
def annuler(reglement):
    """Supprime un règlement saisi par erreur : ses factures redeviennent à régler."""
    reglement = ReglementFournisseur.tous.select_for_update().get(pk=reglement.pk)
    factures = [i.facture for i in reglement.imputations.select_related("facture")]
    reglement.delete()
    _maj_paiement(factures)
