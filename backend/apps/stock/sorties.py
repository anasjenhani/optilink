"""Sorties de stock sans vente (bon de sortie, casse), demandes de transfert, réassort et stock
à une date."""

from collections import defaultdict
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.ventes.models import TypeDocument
from apps.ventes.services import _aujourd_hui, _numero, _prochain_numero
from core import rls

from .models import (
    Article,
    BonSortie,
    DemandeTransfert,
    LigneDemandeTransfert,
    LigneSortie,
    MouvementStock,
    PrixArticle,
    stock_disponible,
)
from .transferts import TransfertImpossible, envoyer_transfert


class SortieImpossible(Exception):
    pass


def _regrouper(lignes, erreur):
    """[{"article", "quantite"}] → {article: quantité}, en refusant les articles sur commande."""
    if not lignes:
        raise erreur("Ajouter au moins un article.")
    quantites = defaultdict(int)
    for numero, ligne in enumerate(lignes, start=1):
        article = ligne["article"]
        if ligne["quantite"] < 1:
            raise erreur(f"Ligne {numero} : quantité d'au moins 1.")
        if article.sur_commande:
            raise erreur(
                f"Ligne {numero} : {article.libelle} est commandé pour un client, pas en stock."
            )
        quantites[article] += ligne["quantite"]
    return quantites


@transaction.atomic
def sortir(*, magasin, type, motif, lignes, auteur, observation="", depot=None):
    """Sort des articles d'un dépôt (usage interne, cadeau, casse…) : effet immédiat.

    Sans dépôt précisé : le dépôt de vente du magasin.
    """
    depot = depot or magasin.depot_de_vente
    if depot.magasin_id != magasin.pk:
        raise SortieImpossible(f"Le dépôt {depot.nom} n'est pas un dépôt de {magasin.nom}.")
    if not motif.strip():
        raise SortieImpossible("Indiquer le motif de la sortie.")
    quantites = _regrouper(lignes, SortieImpossible)
    for article, quantite in quantites.items():
        disponible = stock_disponible(magasin, article, depot)
        if quantite > disponible:
            raise SortieImpossible(
                f"{article.libelle} : {quantite} à sortir, {disponible} en stock au dépôt "
                f"{depot.nom}."
            )
    annee = _aujourd_hui(magasin.pays).year
    sequence = _prochain_numero(magasin, annee, TypeDocument.BON_SORTIE)
    bon = BonSortie.tous.create(
        magasin=magasin,
        depot=depot,
        numero=_numero(magasin, TypeDocument.BON_SORTIE, annee, sequence),
        annee=annee,
        sequence=sequence,
        type=type,
        motif=motif.strip(),
        observation=observation,
        cree_par=auteur,
    )
    mouvement = (
        MouvementStock.Type.CASSE if type == BonSortie.Type.CASSE else MouvementStock.Type.SORTIE
    )
    for article, quantite in quantites.items():
        LigneSortie.objects.create(bon=bon, article=article, quantite=quantite)
        MouvementStock.tous.create(
            magasin=magasin,
            depot=depot,
            article=article,
            quantite=-quantite,
            type=mouvement,
            utilisateur=auteur,
            reference=bon.numero,
        )
    return bon


@transaction.atomic
def demander(*, magasin, aupres_de, lignes, auteur, observation=""):
    """Demande des articles à un autre magasin (au dépôt : demande d'alimentation)."""
    if aupres_de.pk == magasin.pk:
        raise TransfertImpossible("Choisir un autre magasin que le vôtre.")
    if aupres_de.societe_id != magasin.societe_id:
        raise TransfertImpossible("Une demande se fait entre magasins d'une même société.")
    quantites = _regrouper(lignes, TransfertImpossible)
    annee = _aujourd_hui(magasin.pays).year
    sequence = _prochain_numero(magasin, annee, TypeDocument.DEMANDE_TRANSFERT)
    demande = DemandeTransfert.tous.create(
        magasin=magasin,
        aupres_de=aupres_de,
        numero=_numero(magasin, TypeDocument.DEMANDE_TRANSFERT, annee, sequence),
        annee=annee,
        sequence=sequence,
        observation=observation,
        demandee_par=auteur,
    )
    LigneDemandeTransfert.objects.bulk_create(
        LigneDemandeTransfert(demande=demande, article=article, quantite=quantite)
        for article, quantite in quantites.items()
    )
    return demande


def _verrouiller(demande):
    demande = (
        DemandeTransfert.tous.select_for_update(of=("self",))
        .select_related("magasin__pays", "aupres_de__pays")
        .get(pk=demande.pk)
    )
    if demande.statut != DemandeTransfert.Statut.EN_ATTENTE:
        raise TransfertImpossible(
            f"La demande {demande.numero} est déjà {demande.get_statut_display().lower()}."
        )
    return demande


def _cloturer(demande, statut, auteur, **champs):
    demande.statut, demande.traitee_par, demande.traitee_le = statut, auteur, timezone.now()
    for champ, valeur in champs.items():
        setattr(demande, champ, valeur)
    demande.save(
        update_fields=["statut", "traitee_par", "traitee_le", *champs, "modifie_le"],
    )
    return demande


@transaction.atomic
def servir(demande, *, auteur, quantites=None):
    """Le magasin sollicité envoie les articles par un transfert.

    ``quantites`` : {article_id: quantité envoyée} pour servir moins (ou rien sur une ligne) ;
    par défaut, ce qui est demandé.
    """
    demande = _verrouiller(demande)
    lignes = list(demande.lignes.select_related("article"))
    envoi = []
    for ligne in lignes:
        quantite = ligne.quantite if quantites is None else quantites.get(ligne.article_id, 0)
        if quantite < 0 or quantite > ligne.quantite:
            raise TransfertImpossible(
                f"{ligne.article.libelle} : entre 0 et {ligne.quantite} à envoyer."
            )
        ligne.quantite_servie = quantite
        if quantite:
            envoi.append({"article": ligne.article, "quantite": quantite})
    if not envoi:
        raise TransfertImpossible("Rien à envoyer : refuser la demande plutôt.")
    transfert = envoyer_transfert(
        magasin=demande.aupres_de,
        destination=demande.magasin,
        lignes=envoi,
        auteur=auteur,
        observation=f"Demande {demande.numero}",
    )
    LigneDemandeTransfert.objects.bulk_update(lignes, ["quantite_servie"])
    return _cloturer(demande, DemandeTransfert.Statut.SERVIE, auteur, transfert=transfert)


@transaction.atomic
def refuser(demande, *, auteur, motif):
    if not motif.strip():
        raise TransfertImpossible("Indiquer pourquoi la demande est refusée.")
    demande = _verrouiller(demande)
    return _cloturer(
        demande, DemandeTransfert.Statut.REFUSEE, auteur, motif_refus=motif.strip()[:200]
    )


@transaction.atomic
def annuler(demande, *, auteur):
    """Le demandeur retire sa demande tant qu'elle n'est pas traitée."""
    return _cloturer(_verrouiller(demande), DemandeTransfert.Statut.ANNULEE, auteur)


def _fin_de_journee(jour, pays):
    """Premier instant du lendemain, à l'heure du pays."""
    return datetime.combine(
        jour + timedelta(days=1), time.min, tzinfo=ZoneInfo(pays.fuseau_horaire)
    )


def reassort(magasin, *, du, au, famille="", depot=None):
    """Ce qui s'est vendu au magasin sur la période, son stock actuel et celui du dépôt.

    ``depot`` est le magasin qui abrite le dépôt central. La quantité proposée remplace ce qui
    est parti, dans la limite du stock du dépôt central.
    """
    pays = magasin.pays
    debut = datetime.combine(du, time.min, tzinfo=ZoneInfo(pays.fuseau_horaire))
    ventes = MouvementStock.tous.filter(
        magasin=magasin,
        type=MouvementStock.Type.VENTE,
        horodatage__gte=debut,
        horodatage__lt=_fin_de_journee(au, pays),
        article__sur_commande=False,
    )
    if famille:
        ventes = ventes.filter(article__famille=famille)
    vendus = {
        v["article"]: -v["q"]
        for v in ventes.values("article").annotate(q=Sum("quantite"))
        if v["q"] and v["q"] < 0
    }
    if not vendus:
        return []

    def stocks(ou):
        if ou is None:
            return {}
        return {
            s["article"]: s["q"]
            for s in MouvementStock.tous.filter(depot=ou, article__in=vendus)
            .values("article")
            .annotate(q=Sum("quantite"))
        }

    au_magasin = stocks(magasin.depot_de_vente)
    # Le stock du dépôt, hors du périmètre du magasin : lu exprès, pour cette proposition.
    with rls.voir_aussi([depot.pk] if depot else []):
        au_depot = stocks(depot.depot_de_reception if depot else None)
    resultat = []
    for article in Article.objects.filter(pk__in=vendus).order_by("famille", "libelle"):
        vendu = vendus[article.pk]
        propose = vendu if depot is None else max(0, min(vendu, au_depot.get(article.pk, 0)))
        resultat.append(
            {
                "article": article,
                "vendu": vendu,
                "stock": au_magasin.get(article.pk, 0),
                "stock_depot": au_depot.get(article.pk, 0) if depot else None,
                "propose": propose,
            }
        )
    return resultat


def stock_a_la_date(magasin, jour, *, famille="", recherche="", depot=None):
    """Stock de chaque article à la fin du jour donné : la somme des mouvements jusque-là.

    Sans dépôt précisé : tous les dépôts du magasin. La valeur est au prix d'achat net du tarif
    actuel (vide si l'article n'en a pas).
    """
    mouvements = MouvementStock.tous.filter(
        magasin=magasin, horodatage__lt=_fin_de_journee(jour, magasin.pays)
    )
    if depot is not None:
        mouvements = mouvements.filter(depot=depot)
    if famille:
        mouvements = mouvements.filter(article__famille=famille)
    if recherche.strip():
        mouvements = mouvements.filter(article__libelle__icontains=recherche.strip()) | (
            mouvements.filter(article__reference__icontains=recherche.strip())
        )
    quantites = {
        m["article"]: m["q"]
        for m in mouvements.values("article").annotate(q=Sum("quantite"))
        if m["q"]
    }
    tarifs = {
        t.article_id: t
        for t in PrixArticle.objects.filter(pays=magasin.pays, article_id__in=quantites)
    }
    lignes = []
    for article in Article.objects.filter(pk__in=quantites).order_by("famille", "libelle"):
        quantite = quantites[article.pk]
        tarif = tarifs.get(article.pk)
        valeur = None
        if tarif is not None and tarif.prix_achat_ht is not None:
            unitaire = tarif.prix_achat_ht * (1 - tarif.taux_remise_achat / 100)
            valeur = round(unitaire * quantite, magasin.pays.decimales)
        lignes.append({"article": article, "quantite": quantite, "valeur_achat": valeur})
    return lignes
