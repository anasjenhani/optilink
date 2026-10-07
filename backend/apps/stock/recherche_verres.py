"""Recherche d'un verre pour une lunette, comme dans l'ancien logiciel : trois listes.

- Verres de stock fournisseur : sur commande, pris dans le stock du fournisseur ;
- Verres de prescription (RX, importation) : sur commande, fabriqués pour le client ;
- Verres en stock dans le magasin, avec leur quantité.

Chaque ligne est une plage de puissances du verre (sphère et cylindre de début et de fin) avec
son prix ; un verre sans plage donne une seule ligne au prix de l'article. Avec une correction,
seules les plages qui la couvrent restent (un verre sans plage reste : rien ne l'exclut).
"""

from django.db.models import Q, Sum

from .models import Article, MouvementStock, PlageVerre, PrixArticle, Verre

LIMITE = 200
SECTIONS = ("stock_fournisseur", "prescription", "magasin")


def _section(article):
    if not article.sur_commande:
        return "magasin"
    fiche = getattr(article, "verre", None)
    if fiche is not None and fiche.fabrication == Verre.Fabrication.STOCK:
        return "stock_fournisseur"
    return "prescription"


def rechercher_verres(magasin, *, texte="", sphere=None, cylindre=None):
    """Lignes de chaque section, au plus ``LIMITE`` par section, prix dans le pays du magasin."""
    pays = magasin.pays
    articles = Article.objects.filter(
        famille=Article.Famille.VERRE, est_actif=True, prix__pays=pays
    ).select_related("verre", "fournisseur")
    for mot in texte.split():
        articles = articles.filter(
            Q(libelle__icontains=mot)
            | Q(reference__iexact=mot)
            | Q(code_barres=mot)
            | Q(verre__marque__icontains=mot)
            | Q(verre__gamme__icontains=mot)
            | Q(fournisseur__nom__icontains=mot)
        )
    articles = list(articles.order_by("libelle")[: LIMITE * 6])
    prix = {
        p.article_id: p.prix_vente_ttc
        for p in PrixArticle.objects.filter(pays=pays, article__in=articles)
    }
    plages = {}
    for plage in PlageVerre.objects.filter(pays=pays, article__in=articles):
        plages.setdefault(plage.article_id, []).append(plage)
    en_magasin = [a.pk for a in articles if not a.sur_commande]
    stocks = dict(
        MouvementStock.tous.filter(magasin=magasin, article__in=en_magasin)
        .values_list("article")
        .annotate(total=Sum("quantite"))
    )

    resultat = {section: [] for section in SECTIONS}
    for article in articles:
        lignes = resultat[_section(article)]
        if len(lignes) >= LIMITE:
            continue
        fiche = getattr(article, "verre", None)
        commun = {
            "article": article.public_id,
            "reference": article.reference,
            "designation": article.libelle,
            "fournisseur": article.fournisseur.nom if article.fournisseur else "",
            "indice": fiche.indice if fiche else None,
            "diametre": (fiche.diametre_commercial or (fiche.diametre and str(fiche.diametre)))
            if fiche
            else "",
            "quantite": stocks.get(article.pk, 0) if not article.sur_commande else None,
        }
        propres = plages.get(article.pk)
        if not propres:
            lignes.append(
                commun
                | {
                    "plage": None,
                    "sphere_debut": None,
                    "sphere_fin": None,
                    "cylindre_debut": None,
                    "cylindre_fin": None,
                    "prix_vente_ttc": prix.get(article.pk),
                }
            )
            continue
        for plage in propres:
            if not plage.couvre(sphere, cylindre):
                continue
            lignes.append(
                commun
                | {
                    "plage": plage.pk,
                    "sphere_debut": plage.sphere_debut,
                    "sphere_fin": plage.sphere_fin,
                    "cylindre_debut": plage.cylindre_debut,
                    "cylindre_fin": plage.cylindre_fin,
                    "prix_vente_ttc": plage.prix_vente_ttc,
                }
            )
    for lignes in resultat.values():
        del lignes[LIMITE:]
    return resultat
