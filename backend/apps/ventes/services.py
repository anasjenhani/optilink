from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.stock.models import MouvementStock, PrixArticle

from .models import PREFIXES, CompteurFacture, Facture, LigneVente, Paiement, TypeDocument, Vente


class VenteInvalide(Exception):
    pass


def arrondir(montant, decimales):
    """Arrondi à la plus petite unité de la monnaie (centime, millime…)."""
    return montant.quantize(Decimal(1).scaleb(-decimales), rounding=ROUND_HALF_UP)


def _prochain_numero(magasin, annee, type_document):
    """Réserve le numéro suivant ; le verrou tient jusqu'à la fin de la transaction.

    Si la vente échoue, la transaction annule aussi l'incrément : aucun trou dans la suite.
    """
    cle = {"magasin": magasin, "annee": annee, "type_document": type_document}
    CompteurFacture.objects.get_or_create(**cle)
    compteur = CompteurFacture.objects.select_for_update().get(**cle)
    compteur.dernier += 1
    compteur.save(update_fields=["dernier"])
    return compteur.dernier


def _numero(magasin, type_document, annee, sequence):
    return f"{magasin.code}-{PREFIXES[type_document]}{annee}-{sequence:06d}"


def _stocks(magasin, articles):
    lignes = (
        MouvementStock.tous.filter(magasin=magasin, article__in=articles)
        .values("article_id")
        .annotate(total=Sum("quantite"))
    )
    return {ligne["article_id"]: ligne["total"] for ligne in lignes}


@transaction.atomic
def enregistrer_vente(*, magasin, vendeur, lignes, paiements, client=None):
    """Encaisse une vente : lignes, sortie de stock, paiements et numéro de ticket.

    ``lignes`` : [{"article", "quantite", "remise_pct"}] ; ``paiements`` : [{"mode", "montant"}].
    La facture, elle, se génère à part (``generer_facture``).
    Tout est écrit dans une seule transaction, ou rien.
    """
    if not lignes:
        raise VenteInvalide("La vente ne contient aucun article.")

    quantites = {}
    for ligne in lignes:
        quantites[ligne["article"].pk] = quantites.get(ligne["article"].pk, 0) + ligne["quantite"]
    stocks = _stocks(magasin, [ligne["article"] for ligne in lignes])
    for ligne in lignes:
        article = ligne["article"]
        if not article.est_actif:
            raise VenteInvalide(f"L'article {article.reference} n'est plus vendu.")
        if stocks.get(article.pk, 0) < quantites[article.pk]:
            raise VenteInvalide(f"Stock insuffisant pour {article.reference}.")

    pays = magasin.pays
    tarifs = {
        prix.article_id: prix
        for prix in PrixArticle.objects.select_related("tva").filter(
            pays=pays, article__in=quantites.keys()
        )
    }
    detail = []
    for ligne in lignes:
        article, quantite = ligne["article"], ligne["quantite"]
        tarif = tarifs.get(article.pk)
        if tarif is None:
            raise VenteInvalide(f"L'article {article.reference} n'a pas de prix en {pays}.")
        remise = ligne.get("remise_pct") or Decimal("0")
        total_ttc = arrondir(tarif.prix_vente_ttc * quantite * (1 - remise / 100), pays.decimales)
        total_ht = arrondir(total_ttc / (1 + tarif.tva.taux / 100), pays.decimales)
        detail.append((article, quantite, remise, total_ttc, total_ht, tarif))

    total_ttc = sum((d[3] for d in detail), Decimal("0"))
    total_ht = sum((d[4] for d in detail), Decimal("0"))
    total_paye = sum((arrondir(p["montant"], pays.decimales) for p in paiements), Decimal("0"))
    if total_paye != total_ttc:
        raise VenteInvalide(
            f"Les paiements ({total_paye} {pays.devise}) ne couvrent pas le total "
            f"({total_ttc} {pays.devise})."
        )

    # L'année de la facture est celle du magasin, pas celle du serveur.
    annee = timezone.localdate(timezone=ZoneInfo(pays.fuseau_horaire)).year
    sequence = _prochain_numero(magasin, annee, TypeDocument.TICKET)
    vente = Vente.tous.create(
        magasin=magasin,
        client=client,
        numero=_numero(magasin, TypeDocument.TICKET, annee, sequence),
        annee=annee,
        sequence=sequence,
        vendeur=vendeur,
        devise=pays.devise,
        total_ht=total_ht,
        total_tva=total_ttc - total_ht,
        total_ttc=total_ttc,
    )
    LigneVente.objects.bulk_create(
        LigneVente(
            vente=vente,
            article=article,
            libelle=article.libelle,
            quantite=quantite,
            prix_unitaire_ttc=tarif.prix_vente_ttc,
            remise_pct=remise,
            taux_tva=tarif.tva.taux,
            total_ttc=ttc,
        )
        for article, quantite, remise, ttc, _, tarif in detail
    )
    MouvementStock.tous.bulk_create(
        MouvementStock(
            magasin=magasin,
            article=article,
            quantite=-quantite,
            type=MouvementStock.Type.VENTE,
            utilisateur=vendeur,
            reference=vente.numero,
        )
        for article, quantite, *_ in detail
    )
    Paiement.objects.bulk_create(
        Paiement(vente=vente, mode=p["mode"], montant=arrondir(p["montant"], pays.decimales))
        for p in paiements
    )
    return vente


class FactureImpossible(Exception):
    pass


@transaction.atomic
def generer_facture(*, vente, client, emetteur, mode_paiement_timbre=""):
    """Émet la facture d'une vente entièrement payée, au nom d'un client.

    Le droit de timbre du pays s'ajoute au net à payer : c'est le client qui le règle, au moment
    de la facture (``mode_paiement_timbre``). Une vente n'a qu'une facture.
    """
    vente = Vente.tous.select_for_update().select_related("magasin__pays").get(pk=vente.pk)
    if Facture.tous.filter(vente=vente).exists():
        raise FactureImpossible(f"La vente {vente.numero} est déjà facturée.")
    if client is None:
        raise FactureImpossible("Une facture est établie au nom d'un client.")
    reste = vente.reste_a_payer
    if reste > 0:
        raise FactureImpossible(
            f"La commande n'est pas entièrement payée : reste {reste} {vente.devise}."
        )
    pays = vente.magasin.pays
    timbre = pays.timbre_fiscal
    if timbre > 0 and not mode_paiement_timbre:
        raise FactureImpossible(
            f"Encaisser le timbre fiscal ({timbre} {pays.devise}) : préciser le mode de paiement."
        )
    annee = timezone.localdate(timezone=ZoneInfo(pays.fuseau_horaire)).year
    sequence = _prochain_numero(vente.magasin, annee, TypeDocument.FACTURE)
    facture = Facture.tous.create(
        magasin=vente.magasin,
        vente=vente,
        client=client,
        numero=_numero(vente.magasin, TypeDocument.FACTURE, annee, sequence),
        annee=annee,
        sequence=sequence,
        devise=vente.devise,
        total_ht=vente.total_ht,
        total_tva=vente.total_tva,
        total_ttc=vente.total_ttc,
        timbre_fiscal=timbre,
        net_a_payer=vente.total_ttc + timbre,
        mode_paiement_timbre=mode_paiement_timbre if timbre > 0 else "",
        emise_par=emetteur,
    )
    return facture
