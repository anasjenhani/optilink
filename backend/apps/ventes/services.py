from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.stock.models import MouvementStock

from .models import CompteurFacture, LigneVente, Paiement, Vente

CENTIME = Decimal("0.01")


class VenteInvalide(Exception):
    pass


def arrondir(montant):
    return montant.quantize(CENTIME, rounding=ROUND_HALF_UP)


def _prochain_numero(magasin, annee):
    """Réserve le numéro suivant ; le verrou tient jusqu'à la fin de la transaction.

    Si la vente échoue, la transaction annule aussi l'incrément : aucun trou dans la suite.
    """
    CompteurFacture.objects.get_or_create(magasin=magasin, annee=annee)
    compteur = CompteurFacture.objects.select_for_update().get(magasin=magasin, annee=annee)
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
def enregistrer_vente(*, magasin, vendeur, lignes, paiements):
    """Encaisse une vente : lignes, sortie de stock, paiements et numéro de facture.

    ``lignes`` : [{"article", "quantite", "remise_pct"}] ; ``paiements`` : [{"mode", "montant"}].
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

    detail = []
    for ligne in lignes:
        article, quantite = ligne["article"], ligne["quantite"]
        remise = ligne.get("remise_pct") or Decimal("0")
        total_ttc = arrondir(article.prix_vente_ttc * quantite * (1 - remise / 100))
        total_ht = arrondir(total_ttc / (1 + article.taux_tva / 100))
        detail.append((article, quantite, remise, total_ttc, total_ht))

    total_ttc = sum((d[3] for d in detail), Decimal("0"))
    total_ht = sum((d[4] for d in detail), Decimal("0"))
    total_paye = sum((arrondir(p["montant"]) for p in paiements), Decimal("0"))
    if total_paye != total_ttc:
        raise VenteInvalide(
            f"Les paiements ({total_paye} €) ne couvrent pas le total ({total_ttc} €)."
        )

    annee = timezone.localdate().year
    sequence = _prochain_numero(magasin, annee)
    vente = Vente.tous.create(
        magasin=magasin,
        numero=f"{magasin.code}-{annee}-{sequence:06d}",
        annee=annee,
        sequence=sequence,
        vendeur=vendeur,
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
            prix_unitaire_ttc=article.prix_vente_ttc,
            remise_pct=remise,
            taux_tva=article.taux_tva,
            total_ttc=ttc,
        )
        for article, quantite, remise, ttc, _ in detail
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
        Paiement(vente=vente, mode=p["mode"], montant=arrondir(p["montant"])) for p in paiements
    )
    return vente
