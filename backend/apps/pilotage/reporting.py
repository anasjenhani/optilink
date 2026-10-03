"""Reporting des ventes sur une période : chiffre d'affaires, tickets, vendeurs, familles.

Une vente compte le jour où elle est enregistrée (une commande, le jour de l'acompte) ; les
ventes annulées sont exclues et les avoirs sont déduits pour le chiffre d'affaires net. Les
montants ne s'additionnent qu'entre magasins de même monnaie : il y a une section par devise.
"""

from decimal import Decimal

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate

from apps.stock.models import Article
from apps.ventes.models import Avoir, LigneVente, Paiement, Vente

ZERO = Decimal("0")
FAMILLES = dict(Article.Famille.choices)
MODES = dict(Paiement.Mode.choices)


def _somme(qs, champ="total_ttc"):
    return qs.aggregate(s=Sum(champ))["s"] or ZERO


def _section(devise, magasins, du, au):
    periode = {"cree_le__date__gte": du, "cree_le__date__lte": au}
    ventes = Vente.tous.filter(magasin__in=magasins, devise=devise, **periode).exclude(
        statut=Vente.Statut.ANNULEE
    )
    avoirs = Avoir.tous.filter(magasin__in=magasins, devise=devise, **periode)
    ca_ttc = _somme(ventes)
    nombre = ventes.count()
    montant_avoirs = _somme(avoirs)

    par_magasin = [
        {"magasin": m["magasin__nom"], "ca_ttc": m["ca"], "nombre": m["n"]}
        for m in ventes.values("magasin__nom")
        .annotate(ca=Sum("total_ttc"), n=Count("pk"))
        .order_by("-ca")
    ]
    par_jour = [
        {"jour": j["jour"], "ca_ttc": j["ca"], "nombre": j["n"]}
        for j in ventes.annotate(jour=TruncDate("cree_le"))
        .values("jour")
        .annotate(ca=Sum("total_ttc"), n=Count("pk"))
        .order_by("jour")
    ]
    par_vendeur = [
        {
            "vendeur": f"{v['vendeur__first_name']} {v['vendeur__last_name']}".strip()
            or v["vendeur__username"],
            "ca_ttc": v["ca"],
            "nombre": v["n"],
        }
        for v in ventes.values("vendeur__first_name", "vendeur__last_name", "vendeur__username")
        .annotate(ca=Sum("total_ttc"), n=Count("pk"))
        .order_by("-ca")
    ]
    par_famille = [
        {"famille": FAMILLES.get(f["article__famille"], f["article__famille"]), **f}
        for f in LigneVente.objects.filter(vente__in=ventes)
        .values("article__famille")
        .annotate(ca_ttc=Sum("total_ttc"), quantite=Sum("quantite"))
        .order_by("-ca_ttc")
    ]
    encaissements = [
        {"mode": MODES.get(p["mode"], p["mode"]), "montant": p["montant"]}
        for p in Paiement.objects.filter(
            vente__magasin__in=magasins,
            vente__devise=devise,
            recu_le__date__gte=du,
            recu_le__date__lte=au,
        )
        .values("mode")
        .annotate(montant=Sum("montant"))
        .order_by("-montant")
    ]
    for famille in par_famille:
        famille.pop("article__famille")
    return {
        "devise": devise,
        "ca_ttc": ca_ttc,
        "ca_ht": _somme(ventes, "total_ht"),
        "avoirs_ttc": montant_avoirs,
        "ca_net_ttc": ca_ttc - montant_avoirs,
        "nombre_ventes": nombre,
        "panier_moyen": (ca_ttc / nombre).quantize(Decimal("0.001")) if nombre else ZERO,
        "par_magasin": par_magasin,
        "par_jour": par_jour,
        "par_vendeur": par_vendeur,
        "par_famille": par_famille,
        "encaissements": encaissements,
    }


def rapport(magasins, du, au):
    devises = sorted({m.pays.devise for m in magasins})
    return [_section(devise, magasins, du, au) for devise in devises]
