"""Crédit client et impayés : chèque revenu impayé, changement de chèque, liste noire."""

from django.db import transaction
from django.utils import timezone

from .models import Paiement
from .services import VenteInvalide, _encaisser, _verrouiller_vente

Statut = Paiement.Statut


def _verrouiller_paiement(paiement):
    return (
        Paiement.objects.select_for_update(of=("self",))
        .select_related("vente__client")
        .get(pk=paiement.pk)
    )


def mettre_en_liste_noire(client, motif):
    client.liste_noire = True
    client.motif_liste_noire = motif.strip()[:200]
    client.liste_noire_le = timezone.localdate()
    client.save(update_fields=["liste_noire", "motif_liste_noire", "liste_noire_le", "modifie_le"])


def retirer_de_la_liste_noire(client):
    client.liste_noire = False
    client.motif_liste_noire = ""
    client.liste_noire_le = None
    client.save(update_fields=["liste_noire", "motif_liste_noire", "liste_noire_le", "modifie_le"])


@transaction.atomic
def declarer_impaye(paiement, *, le, motif, liste_noire=True):
    """La banque a rejeté le chèque ou la traite : son montant redevient dû par le client.

    Par défaut, le client passe en liste noire (plus de chèque ni de crédit).
    """
    paiement = _verrouiller_paiement(paiement)
    if paiement.mode not in Paiement.A_ECHEANCE:
        raise VenteInvalide("Seul un chèque ou une traite peut revenir impayé.")
    if paiement.statut != Statut.ENCAISSE:
        raise VenteInvalide(f"Ce règlement est déjà {paiement.get_statut_display().lower()}.")
    if not motif.strip():
        raise VenteInvalide("Indiquer le motif du rejet (sans provision, signature…).")
    paiement.statut, paiement.impaye_le, paiement.motif_impaye = Statut.IMPAYE, le, motif.strip()
    paiement.save(update_fields=["statut", "impaye_le", "motif_impaye"])
    client = paiement.vente.client
    if liste_noire and client is not None and not client.liste_noire:
        libelle = paiement.get_mode_display().lower()
        mettre_en_liste_noire(
            client,
            f"{libelle.capitalize()} n° {paiement.reference} impayé ({paiement.vente.numero})",
        )
    return paiement


@transaction.atomic
def changer_cheque(paiement, *, nouveau, utilisateur):
    """Le client reprend son chèque (ou sa traite) et paie autrement le même montant.

    ``nouveau`` : {"mode", "reference", "banque", "echeance"}. Un impayé se change aussi : c'est
    sa régularisation.
    """
    paiement = _verrouiller_paiement(paiement)
    if paiement.mode not in Paiement.A_ECHEANCE:
        raise VenteInvalide("Seul un chèque ou une traite se change.")
    if paiement.statut == Statut.REMPLACE:
        raise VenteInvalide("Ce chèque a déjà été changé.")
    vente = _verrouiller_vente(paiement.vente)
    avant = set(vente.paiements.values_list("pk", flat=True))
    _encaisser(vente, [{**nouveau, "montant": paiement.montant}], utilisateur)
    remplacant = vente.paiements.exclude(pk__in=avant).get()
    paiement.statut, paiement.remplace_par = Statut.REMPLACE, remplacant
    paiement.save(update_fields=["statut", "remplace_par"])
    return remplacant
