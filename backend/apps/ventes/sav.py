"""Service après-vente : ouverture d'un dossier et passage d'une étape à l'autre."""

from django.db import transaction

from .models import DossierSav, EvenementSav, TypeDocument
from .services import _aujourd_hui, _numero, _prochain_numero

Etape = DossierSav.Etape


class SavImpossible(Exception):
    pass


@transaction.atomic
def ouvrir_dossier(
    *,
    magasin,
    client,
    designation,
    motif,
    utilisateur,
    vente=None,
    article=None,
    description="",
    sous_garantie=False,
    retour_prevu_le=None,
):
    """Enregistre ce que le client rapporte ; le dossier commence « reçu au magasin »."""
    if not designation.strip():
        raise SavImpossible("Indiquer ce que le client rapporte.")
    if vente is not None:
        if vente.magasin_id != magasin.pk:
            raise SavImpossible("La visite d'origine est d'un autre magasin.")
        if vente.client_id not in (None, client.pk):
            raise SavImpossible("La visite d'origine est celle d'un autre client.")
    annee = _aujourd_hui(magasin.pays).year
    sequence = _prochain_numero(magasin, annee, TypeDocument.SAV)
    dossier = DossierSav.tous.create(
        magasin=magasin,
        numero=_numero(magasin, TypeDocument.SAV, annee, sequence),
        annee=annee,
        sequence=sequence,
        client=client,
        vente=vente,
        article=article,
        designation=designation.strip(),
        motif=motif,
        description=description,
        sous_garantie=sous_garantie,
        retour_prevu_le=retour_prevu_le,
        cree_par=utilisateur,
    )
    EvenementSav.objects.create(dossier=dossier, etape=Etape.RECU, par=utilisateur)
    return dossier


@transaction.atomic
def changer_etape(
    dossier,
    etape,
    *,
    utilisateur,
    commentaire="",
    fournisseur=None,
    retour_prevu_le=None,
    solution="",
):
    """Fait avancer le dossier ; « rendu » et « annulé » le clôturent pour de bon."""
    dossier = DossierSav.tous.select_for_update().get(pk=dossier.pk)
    if not dossier.est_ouvert:
        raise SavImpossible(f"Le dossier {dossier.numero} est clôturé.")
    if etape == dossier.etape:
        raise SavImpossible(f"Le dossier est déjà à l'étape « {dossier.get_etape_display()} ».")
    if etape == Etape.FOURNISSEUR:
        dossier.fournisseur = fournisseur or dossier.fournisseur
        if dossier.fournisseur is None:
            raise SavImpossible("Choisir le fournisseur à qui l'article est envoyé.")
    if etape == Etape.ANNULE and not commentaire.strip():
        raise SavImpossible("Indiquer pourquoi le dossier est annulé.")
    if retour_prevu_le is not None:
        dossier.retour_prevu_le = retour_prevu_le
    if solution.strip():
        dossier.solution = solution.strip()
    dossier.etape = etape
    dossier.save()
    EvenementSav.objects.create(
        dossier=dossier, etape=etape, commentaire=commentaire.strip(), par=utilisateur
    )
    return dossier
