from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.stock.models import MouvementStock, PrixArticle

from .models import PREFIXES, CompteurFacture, LigneVente, Paiement, TypeDocument, Vente


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


def _stocks(magasin, articles):
    lignes = (
        MouvementStock.tous.filter(magasin=magasin, article__in=articles)
        .values("article_id")
        .annotate(total=Sum("quantite"))
    )
    return {ligne["article_id"]: ligne["total"] for ligne in lignes}


@transaction.atomic
def enregistrer_vente(*, magasin, vendeur, lignes, paiements, facture=False, client=None):
    """Encaisse une vente : lignes, sortie de stock, paiements et numéro de ticket ou de facture.

    ``lignes`` : [{"article", "quantite", "remise_pct"}] ; ``paiements`` : [{"mode", "montant"}].
    Une facture exige un client et porte le droit de timbre du pays ; un ticket n'en a pas.
    Tout est écrit dans une seule transaction, ou rien.
    """
    if not lignes:
        raise VenteInvalide("La vente ne contient aucun article.")
    if facture and client is None:
        raise VenteInvalide("Une facture doit être établie au nom d'un client.")
    type_document = TypeDocument.FACTURE if facture else TypeDocument.TICKET

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
    timbre = pays.timbre_fiscal if facture else Decimal("0")
    net_a_payer = total_ttc + timbre
    total_paye = sum((arrondir(p["montant"], pays.decimales) for p in paiements), Decimal("0"))
    if total_paye != net_a_payer:
        raise VenteInvalide(
            f"Les paiements ({total_paye} {pays.devise}) ne couvrent pas le net à payer "
            f"({net_a_payer} {pays.devise})."
        )

    # L'année de la facture est celle du magasin, pas celle du serveur.
    annee = timezone.localdate(timezone=ZoneInfo(pays.fuseau_horaire)).year
    sequence = _prochain_numero(magasin, annee, type_document)
    vente = Vente.tous.create(
        magasin=magasin,
        type_document=type_document,
        client=client,
        numero=f"{magasin.code}-{PREFIXES[type_document]}{annee}-{sequence:06d}",
        annee=annee,
        sequence=sequence,
        vendeur=vendeur,
        devise=pays.devise,
        total_ht=total_ht,
        total_tva=total_ttc - total_ht,
        total_ttc=total_ttc,
        timbre_fiscal=timbre,
        net_a_payer=net_a_payer,
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
