"""Transferts de stock : un dépôt (le dépôt central en général) envoie des articles à un autre.

À l'envoi, les articles sortent du dépôt de départ. Le magasin destinataire les réceptionne à
l'arrivée : ils entrent alors dans le dépôt destinataire. Un transfert se fait entre dépôts
d'une même société, éventuellement d'un même magasin (vers le dépôt casse…). Sans dépôt
précisé, le départ est le dépôt central du magasin s'il l'abrite, sinon son dépôt de vente ;
l'arrivée est le dépôt de vente du magasin destinataire.
"""

from collections import defaultdict

from django.db import transaction
from django.utils import timezone

from apps.ventes.models import TypeDocument
from apps.ventes.services import _aujourd_hui, _numero, _prochain_numero

from .models import Article, LigneTransfert, MouvementStock, TransfertStock, stock_disponible
from .peremptions import a_envoyer


class TransfertImpossible(Exception):
    pass


@transaction.atomic
def envoyer_transfert(
    *,
    magasin,
    destination,
    lignes,
    auteur,
    observation="",
    depot_origine=None,
    depot_destination=None,
):
    """Envoie les articles : ``lignes`` = [{"article", "quantite"}]."""
    depot_origine = depot_origine or magasin.depot_de_reception
    depot_destination = depot_destination or destination.depot_de_vente
    if depot_origine.magasin_id != magasin.pk or depot_destination.magasin_id != destination.pk:
        raise TransfertImpossible("Chaque dépôt doit appartenir à son magasin.")
    if depot_destination.pk == depot_origine.pk:
        raise TransfertImpossible("Choisissez un autre dépôt que celui de départ.")
    if destination.societe_id != magasin.societe_id:
        raise TransfertImpossible("Un transfert se fait entre magasins d'une même société.")
    if not destination.est_actif:
        raise TransfertImpossible(f"Le magasin {destination.nom} n'est plus actif.")
    if not depot_origine.est_actif or not depot_destination.est_actif:
        raise TransfertImpossible("Un des deux dépôts n'est plus actif.")
    if not lignes:
        raise TransfertImpossible("Le transfert ne contient aucun article.")
    quantites = defaultdict(int)
    for numero, ligne in enumerate(lignes, start=1):
        article = ligne["article"]
        if ligne["quantite"] < 1:
            raise TransfertImpossible(f"Ligne {numero} : quantité d'au moins 1.")
        if article.sur_commande:
            raise TransfertImpossible(
                f"Ligne {numero} : {article.libelle} est commandé pour un client, pas en stock."
            )
        quantites[article] += ligne["quantite"]
    for article, quantite in quantites.items():
        disponible = stock_disponible(magasin, article, depot_origine)
        if quantite > disponible:
            raise TransfertImpossible(
                f"{article.libelle} : {quantite} à envoyer, {disponible} en stock au dépôt "
                f"{depot_origine.nom}."
            )
    annee = _aujourd_hui(magasin.pays).year
    sequence = _prochain_numero(magasin, annee, TypeDocument.TRANSFERT)
    transfert = TransfertStock.tous.create(
        magasin=magasin,
        destination=destination,
        depot_origine=depot_origine,
        depot_destination=depot_destination,
        numero=_numero(magasin, TypeDocument.TRANSFERT, annee, sequence),
        annee=annee,
        sequence=sequence,
        observation=observation,
        envoye_par=auteur,
    )
    for article, quantite in quantites.items():
        LigneTransfert.objects.create(
            transfert=transfert,
            article=article,
            quantite=quantite,
            peremptions=(
                a_envoyer(depot_origine, article, quantite)
                if article.famille == Article.Famille.LENTILLE
                else []
            ),
        )
        MouvementStock.tous.create(
            magasin=magasin,
            depot=depot_origine,
            article=article,
            quantite=-quantite,
            type=MouvementStock.Type.TRANSFERT_SORTIE,
            utilisateur=auteur,
            reference=transfert.numero,
        )
    return transfert


@transaction.atomic
def recevoir_transfert(transfert, *, auteur):
    """Le magasin destinataire réceptionne le transfert : les articles entrent en stock."""
    transfert = (
        TransfertStock.tous.select_for_update(of=("self",))
        .prefetch_related("lignes__article")
        .get(pk=transfert.pk)
    )
    if transfert.statut != TransfertStock.Statut.ENVOYE:
        raise TransfertImpossible(f"Le transfert {transfert.numero} est déjà réceptionné.")
    for ligne in transfert.lignes.all():
        MouvementStock.tous.create(
            magasin_id=transfert.destination_id,
            depot_id=transfert.depot_destination_id,
            article=ligne.article,
            quantite=ligne.quantite,
            type=MouvementStock.Type.TRANSFERT_ENTREE,
            utilisateur=auteur,
            reference=transfert.numero,
        )
    transfert.statut = TransfertStock.Statut.RECU
    transfert.recu_par = auteur
    transfert.recu_le = timezone.now()
    transfert.save(update_fields=["statut", "recu_par", "recu_le", "modifie_le"])
    return transfert


@transaction.atomic
def annuler_transfert(transfert, *, auteur):
    """Transfert envoyé par erreur et pas encore réceptionné : les articles reviennent au dépôt
    de départ (mouvement inverse, l'historique de l'envoi reste)."""
    transfert = (
        TransfertStock.tous.select_for_update(of=("self",))
        .prefetch_related("lignes__article")
        .get(pk=transfert.pk)
    )
    if transfert.statut != TransfertStock.Statut.ENVOYE:
        raise TransfertImpossible(
            f"Le transfert {transfert.numero} est {transfert.get_statut_display().lower()} : "
            "il ne s'annule plus."
        )
    for ligne in transfert.lignes.all():
        MouvementStock.tous.create(
            magasin_id=transfert.magasin_id,
            depot_id=transfert.depot_origine_id,
            article=ligne.article,
            quantite=ligne.quantite,
            type=MouvementStock.Type.TRANSFERT_ENTREE,
            utilisateur=auteur,
            reference=f"{transfert.numero} annulé",
        )
    transfert.statut = TransfertStock.Statut.ANNULE
    transfert.annule_par = auteur
    transfert.annule_le = timezone.now()
    transfert.save(update_fields=["statut", "annule_par", "annule_le", "modifie_le"])
    return transfert
