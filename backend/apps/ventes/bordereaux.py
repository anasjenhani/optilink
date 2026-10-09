"""Bordereaux de prise en charge : préparation, envoi à l'organisme, saisie du règlement."""

from django.db import transaction

from .models import BordereauPec, PriseEnCharge, TypeDocument
from .services import _aujourd_hui, _numero, _prochain_numero

Statut = BordereauPec.Statut
StatutPec = PriseEnCharge.Statut
# Prises en charge qu'on peut envoyer : pas encore réglées ni refusées.
A_ENVOYER = (StatutPec.DEMANDEE, StatutPec.ACCORDEE)


class BordereauImpossible(Exception):
    pass


def prises_en_charge_a_envoyer(magasin, organisme):
    """Prises en charge du magasin pour cet organisme, dans aucun bordereau."""
    return PriseEnCharge.objects.filter(
        vente__magasin=magasin, organisme=organisme, bordereau=None, statut__in=A_ENVOYER
    ).select_related("vente__client")


def _verifier(magasin, organisme, prises_en_charge, bordereau=None):
    if not prises_en_charge:
        raise BordereauImpossible("Le bordereau ne contient aucune prise en charge.")
    for pec in prises_en_charge:
        if pec.vente.magasin_id != magasin.pk or pec.organisme_id != organisme.pk:
            raise BordereauImpossible(
                f"{pec.vente.numero} : prise en charge d'un autre magasin ou d'un autre organisme."
            )
        if pec.statut not in A_ENVOYER:
            raise BordereauImpossible(
                f"{pec.vente.numero} : prise en charge déjà {pec.get_statut_display().lower()}."
            )
        if pec.bordereau_id not in (None, getattr(bordereau, "pk", None)):
            raise BordereauImpossible(
                f"{pec.vente.numero} : déjà dans le bordereau {pec.bordereau}."
            )


@transaction.atomic
def preparer(*, magasin, organisme, prises_en_charge, utilisateur, observation=""):
    prises_en_charge = list(
        PriseEnCharge.objects.select_for_update()
        .filter(pk__in=[p.pk for p in prises_en_charge])
        .select_related("vente")
    )
    _verifier(magasin, organisme, prises_en_charge)
    annee = _aujourd_hui(magasin.pays).year
    sequence = _prochain_numero(magasin, annee, TypeDocument.BORDEREAU_PEC)
    bordereau = BordereauPec.tous.create(
        magasin=magasin,
        numero=_numero(magasin, TypeDocument.BORDEREAU_PEC, annee, sequence),
        annee=annee,
        sequence=sequence,
        organisme=organisme,
        observation=observation,
        cree_par=utilisateur,
    )
    PriseEnCharge.objects.filter(pk__in=[p.pk for p in prises_en_charge]).update(
        bordereau=bordereau
    )
    return bordereau


def _verrouiller(bordereau, *statuts):
    bordereau = BordereauPec.tous.select_for_update().get(pk=bordereau.pk)
    if bordereau.statut not in statuts:
        raise BordereauImpossible(
            f"Le bordereau {bordereau.numero} est {bordereau.get_statut_display().lower()}."
        )
    return bordereau


@transaction.atomic
def modifier(bordereau, *, prises_en_charge, observation=None):
    """Remplace la liste des prises en charge d'un bordereau encore en préparation."""
    bordereau = _verrouiller(bordereau, Statut.PREPARATION)
    prises_en_charge = list(
        PriseEnCharge.objects.select_for_update()
        .filter(pk__in=[p.pk for p in prises_en_charge])
        .select_related("vente")
    )
    _verifier(bordereau.magasin, bordereau.organisme, prises_en_charge, bordereau)
    bordereau.prises_en_charge.exclude(pk__in=[p.pk for p in prises_en_charge]).update(
        bordereau=None
    )
    PriseEnCharge.objects.filter(pk__in=[p.pk for p in prises_en_charge]).update(
        bordereau=bordereau
    )
    if observation is not None:
        bordereau.observation = observation
        bordereau.save(update_fields=["observation", "modifie_le"])
    return bordereau


@transaction.atomic
def supprimer(bordereau):
    """Abandonne un bordereau en préparation : ses prises en charge redeviennent à envoyer."""
    bordereau = _verrouiller(bordereau, Statut.PREPARATION)
    bordereau.prises_en_charge.update(bordereau=None)
    bordereau.delete()


@transaction.atomic
def envoyer(bordereau, *, le):
    bordereau = _verrouiller(bordereau, Statut.PREPARATION)
    bordereau.statut, bordereau.envoye_le = Statut.ENVOYE, le
    bordereau.save(update_fields=["statut", "envoye_le", "modifie_le"])
    return bordereau


@transaction.atomic
def regler(bordereau, *, le, mode, reference, lignes):
    """Saisit le paiement de l'organisme, prise en charge par prise en charge.

    ``lignes`` : {pk de la prise en charge: (montant réglé, motif du rejet)}. Une prise en
    charge sans ligne est réglée en entier ; à 0, elle est rejetée (motif obligatoire) et
    revient au client, comme l'écart d'un règlement partiel.
    """
    bordereau = _verrouiller(bordereau, Statut.ENVOYE)
    if le < bordereau.envoye_le:
        raise BordereauImpossible("Le règlement ne peut pas précéder l'envoi du bordereau.")
    prises_en_charge = list(bordereau.prises_en_charge.select_for_update().select_related("vente"))
    inconnues = set(lignes) - {p.pk for p in prises_en_charge}
    if inconnues:
        raise BordereauImpossible("Une ligne du règlement n'est pas dans ce bordereau.")
    for pec in prises_en_charge:
        montant, motif = lignes.get(pec.pk, (pec.montant, ""))
        if montant < 0 or montant > pec.montant:
            raise BordereauImpossible(
                f"{pec.vente.numero} : le montant réglé doit être entre 0 et {pec.montant}."
            )
        if montant < pec.montant and not motif.strip():
            raise BordereauImpossible(
                f"{pec.vente.numero} : indiquer le motif du rejet ou de la réduction."
            )
        pec.montant_regle = montant
        pec.motif_rejet = motif.strip() if montant < pec.montant else ""
        pec.statut = StatutPec.REGLEE if montant > 0 else StatutPec.REFUSEE
        pec.save(update_fields=["montant_regle", "motif_rejet", "statut", "modifie_le"])
    bordereau.statut, bordereau.regle_le = Statut.REGLE, le
    bordereau.mode_reglement, bordereau.reference_reglement = mode, reference
    bordereau.save(
        update_fields=["statut", "regle_le", "mode_reglement", "reference_reglement", "modifie_le"]
    )
    return bordereau
