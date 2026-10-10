"""Péremption des lentilles en stock, dépôt par dépôt.

Le stock d'une lentille est fait des dernières pièces entrées (on vend et on envoie d'abord les
plus anciennes) : on remonte les entrées, de la plus récente à la plus ancienne, jusqu'à couvrir
le stock. Une entrée est une réception (date saisie sur le bon) ou un transfert reçu (dates des
pièces envoyées, retenues à l'envoi). Le dernier inventaire validé compte comme l'entrée de tout
ce qui a été compté, avec la date saisie au comptage ; les entrées plus anciennes ne comptent
plus. Ce qui reste (stock repris de l'ancien logiciel…) a une date inconnue, jusqu'au prochain
inventaire.
"""

from collections import defaultdict
from datetime import date, timedelta

from django.db.models import Sum

from .models import (
    Article,
    Inventaire,
    LigneInventaire,
    LigneTransfert,
    MouvementStock,
    TransfertStock,
)


def _stocks(depot, articles=None):
    mouvements = MouvementStock.tous.filter(
        depot=depot, article__famille=Article.Famille.LENTILLE, article__sur_commande=False
    )
    if articles is not None:
        mouvements = mouvements.filter(article__in=articles)
    return {
        s["article"]: s["q"]
        for s in mouvements.values("article").annotate(q=Sum("quantite"))
        if s["q"] and s["q"] > 0
    }


def _date(texte):
    return date.fromisoformat(texte) if texte else None


def lots(depot, stocks):
    """{article_id: {date ou None: quantité}} des pièces en stock (``stocks`` : {id: stock})."""
    from apps.achats.models import LigneReception

    entrees = defaultdict(list)  # article_id → [(instant, {date: quantité})]
    for ligne in LigneReception.objects.filter(
        bon__depot=depot, article_id__in=stocks, non_conforme=False
    ).select_related("bon"):
        entrees[ligne.article_id].append(
            (ligne.bon.cree_le, {ligne.date_peremption: ligne.quantite})
        )
    for ligne in LigneTransfert.objects.filter(
        transfert__depot_destination=depot,
        transfert__statut=TransfertStock.Statut.RECU,
        article_id__in=stocks,
    ).select_related("transfert"):
        repartition = defaultdict(int)
        for lot in ligne.peremptions or [{"date": None, "quantite": ligne.quantite}]:
            repartition[_date(lot["date"])] += lot["quantite"]
        entrees[ligne.article_id].append((ligne.transfert.recu_le, dict(repartition)))
    inventaires = {}
    for ligne in (
        LigneInventaire.objects.filter(
            inventaire__depot=depot,
            inventaire__statut=Inventaire.Statut.VALIDE,
            article_id__in=stocks,
        )
        .select_related("inventaire")
        .order_by("inventaire__valide_le")
    ):
        inventaires[ligne.article_id] = ligne  # le plus récent l'emporte

    resultat = {}
    for article_id, stock in stocks.items():
        reste, trouves = stock, defaultdict(int)
        base = inventaires.get(article_id)
        for instant, repartition in sorted(entrees[article_id], key=lambda e: e[0], reverse=True):
            if reste == 0 or (base and instant <= base.inventaire.valide_le):
                break
            # Dans une entrée, les pièces restantes sont celles qui périment le plus tard.
            for jour in sorted(repartition, key=lambda d: d or date.min, reverse=True):
                pris = min(reste, repartition[jour])
                trouves[jour] += pris
                reste -= pris
        if reste and base:
            pris = min(reste, base.quantite_comptee)
            trouves[base.date_peremption] += pris
            reste -= pris
        if reste:
            trouves[None] += reste
        resultat[article_id] = {d: q for d, q in trouves.items() if q}
    return resultat


def a_envoyer(depot, article, quantite):
    """Dates des pièces qu'un dépôt envoie : les plus proches d'abord, puis les inconnues."""
    stock = _stocks(depot, [article])
    if not stock:
        return []
    disponibles = lots(depot, stock).get(article.pk, {})
    envoi, reste = [], quantite
    for jour in sorted(disponibles, key=lambda d: (d is None, d or date.min)):
        pris = min(reste, disponibles[jour])
        if pris:
            envoi.append({"date": jour.isoformat() if jour else None, "quantite": pris})
            reste -= pris
    if reste:
        envoi.append({"date": None, "quantite": reste})
    return envoi


def peremptions(depot, aujourd_hui, *, proche_jours=90):
    stocks = _stocks(depot)
    if not stocks:
        return []
    tous_lots = lots(depot, stocks)
    limite = aujourd_hui + timedelta(days=proche_jours)
    resultat = []
    for article in Article.objects.filter(pk__in=stocks):
        trouves = tous_lots[article.pk]
        connues = sorted(d for d in trouves if d is not None)
        prochaine = connues[0] if connues else None
        if prochaine is None:
            etat = "inconnue"
        elif prochaine < aujourd_hui:
            etat = "perimee"
        elif prochaine <= limite:
            etat = "proche"
        else:
            etat = "ok"
        resultat.append(
            {
                "article": article,
                "stock": stocks[article.pk],
                "prochaine": prochaine,
                "etat": etat,
                "lots": [
                    {"date": d, "quantite": trouves[d]} for d in [*connues, None] if d in trouves
                ],
            }
        )
    ordre = {"perimee": 0, "proche": 1, "inconnue": 2, "ok": 3}
    resultat.sort(
        key=lambda r: (ordre[r["etat"]], r["prochaine"] or aujourd_hui, r["article"].libelle)
    )
    return resultat
