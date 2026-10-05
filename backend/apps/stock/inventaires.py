"""Inventaire : comptage physique du stock d'un magasin et correction du stock à la validation.

Le stock de l'application est relu au moment de la validation : les ventes ou réceptions faites
pendant le comptage sont donc prises en compte. Un article en stock mais non compté est
considéré comme absent : l'inventaire couvre tout son périmètre (tout le stock du magasin, ou
une famille, une marque, une nature de monture, un fournisseur).
"""

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.ventes.models import TypeDocument
from apps.ventes.services import _aujourd_hui, _numero, _prochain_numero

from .models import Article, Inventaire, LigneInventaire, MouvementStock


class InventaireImpossible(Exception):
    pass


# Statuts où le stock n'est pas encore corrigé et les quantités se modifient encore.
OUVERTS = (Inventaire.Statut.EN_COURS, Inventaire.Statut.A_VERIFIER)


def _filtre(inventaire, prefixe=""):
    """Q des articles que couvre l'inventaire (``prefixe`` : « article__ » depuis un mouvement)."""
    criteres = {f"{prefixe}sur_commande": False}
    if inventaire.famille:
        criteres[f"{prefixe}famille"] = inventaire.famille
    if inventaire.marque:
        criteres[f"{prefixe}monture__marque__iexact"] = inventaire.marque
    if inventaire.nature:
        criteres[f"{prefixe}monture__categorie"] = inventaire.nature
    if inventaire.fournisseur_id:
        criteres[f"{prefixe}fournisseur_id"] = inventaire.fournisseur_id
    return Q(**criteres)


def perimetre(inventaire):
    """Ce que couvre l'inventaire, en clair : « Montures · Ray-Ban · Lunette Solaire »."""
    parties = [
        inventaire.get_famille_display() if inventaire.famille else "Tout le stock",
        inventaire.marque,
        inventaire.get_nature_display() if inventaire.nature else "",
        inventaire.fournisseur.nom if inventaire.fournisseur_id else "",
    ]
    return " · ".join(p for p in parties if p)


def stocks_theoriques(inventaire):
    """{article_id: stock} des articles du périmètre ayant un stock non nul dans le magasin."""
    totaux = (
        MouvementStock.tous.filter(
            _filtre(inventaire, "article__"), magasin_id=inventaire.magasin_id
        )
        .values("article_id")
        .annotate(stock=Sum("quantite"))
    )
    return {t["article_id"]: t["stock"] for t in totaux if t["stock"]}


def etat(inventaire):
    """Lignes à afficher : articles comptés et articles en stock non comptés, avec l'écart.

    Pour un inventaire validé, ce sont les lignes enregistrées à la validation.
    """
    lignes = list(inventaire.lignes.select_related("article").order_by("article__reference"))
    if inventaire.statut not in OUVERTS:
        return [
            {
                "article": ligne.article,
                "stock_theorique": ligne.stock_theorique or 0,
                "quantite_comptee": ligne.quantite_comptee,
                "comptee": True,
                "ecart": ligne.ecart or 0,
                "observation": ligne.observation,
            }
            for ligne in lignes
        ]
    theoriques = stocks_theoriques(inventaire)
    resultat = []
    for ligne in lignes:
        theorique = theoriques.pop(ligne.article_id, 0)
        resultat.append(
            {
                "article": ligne.article,
                "stock_theorique": theorique,
                "quantite_comptee": ligne.quantite_comptee,
                "comptee": True,
                "ecart": ligne.quantite_comptee - theorique,
                "observation": ligne.observation,
            }
        )
    for article in Article.objects.filter(pk__in=theoriques).order_by("reference"):
        theorique = theoriques[article.pk]
        resultat.append(
            {
                "article": article,
                "stock_theorique": theorique,
                "quantite_comptee": 0,
                "comptee": False,
                "ecart": -theorique,
                "observation": "",
            }
        )
    return resultat


@transaction.atomic
def ouvrir_inventaire(
    *, magasin, auteur, famille="", marque="", nature="", fournisseur=None, observation=""
):
    """Ouvre le comptage ; une marque ou une nature limite l'inventaire aux montures."""
    if not magasin.est_actif:
        raise InventaireImpossible(f"Le magasin {magasin.nom} n'est plus actif.")
    marque = marque.strip()
    if marque or nature:
        if famille and famille != Article.Famille.MONTURE:
            raise InventaireImpossible("La marque et la nature concernent les montures.")
        famille = Article.Famille.MONTURE
    # Un comptage à la fois par magasin : deux inventaires sur les mêmes articles
    # corrigeraient deux fois le stock.
    deja = Inventaire.tous.filter(magasin=magasin, statut__in=OUVERTS).first()
    if deja:
        raise InventaireImpossible(
            f"L'inventaire {deja.numero} est déjà en cours dans ce magasin : "
            "validez-le ou annulez-le d'abord."
        )
    annee = _aujourd_hui(magasin.pays).year
    sequence = _prochain_numero(magasin, annee, TypeDocument.INVENTAIRE)
    return Inventaire.tous.create(
        magasin=magasin,
        numero=_numero(magasin, TypeDocument.INVENTAIRE, annee, sequence),
        annee=annee,
        sequence=sequence,
        famille=famille,
        marque=marque,
        nature=nature,
        fournisseur=fournisseur,
        observation=observation,
        cree_par=auteur,
    )


def _exiger(inventaire, *statuts):
    if inventaire.statut not in statuts:
        raise InventaireImpossible(
            f"L'inventaire {inventaire.numero} est {inventaire.get_statut_display().lower()}."
        )


def trouver_article(code):
    """Article d'après un code barre scanné ou une référence tapée."""
    code = code.strip()
    if not code:
        raise InventaireImpossible("Saisissez un code barre ou une référence.")
    article = (
        Article.objects.filter(code_barres=code).first()
        or Article.objects.filter(reference__iexact=code).first()
    )
    if article is None:
        raise InventaireImpossible(f"Aucun article avec le code ou la référence « {code} ».")
    return article


@transaction.atomic
def compter(inventaire, article, *, quantite, remplacer=False, observation=None):
    """Ajoute ``quantite`` au compté de l'article, ou la met à la place si ``remplacer``.

    Pendant la vérification, c'est la correction d'une quantité (recomptage) par le responsable.
    """
    inventaire = Inventaire.tous.select_for_update().get(pk=inventaire.pk)
    _exiger(inventaire, *OUVERTS)
    if article.sur_commande:
        raise InventaireImpossible(
            f"{article.libelle} est commandé pour chaque client : il n'est pas tenu en stock."
        )
    if not Article.objects.filter(_filtre(inventaire), pk=article.pk).exists():
        raise InventaireImpossible(
            f"{article.libelle} n'entre pas dans cet inventaire ({perimetre(inventaire)})."
        )
    if quantite < 0 or (not remplacer and quantite == 0):
        raise InventaireImpossible("Quantité invalide.")
    ligne, _ = LigneInventaire.objects.get_or_create(inventaire=inventaire, article=article)
    ligne.quantite_comptee = quantite if remplacer else ligne.quantite_comptee + quantite
    champs = ["quantite_comptee"]
    if observation is not None:
        ligne.observation = observation[:200]
        champs.append("observation")
    ligne.save(update_fields=champs)
    return ligne


@transaction.atomic
def retirer(inventaire, article):
    """Retire un article compté par erreur (il redevient « non compté »)."""
    inventaire = Inventaire.tous.select_for_update().get(pk=inventaire.pk)
    _exiger(inventaire, *OUVERTS)
    LigneInventaire.objects.filter(inventaire=inventaire, article=article).delete()


@transaction.atomic
def terminer_comptage(inventaire, *, auteur):
    """Fin du comptage : l'inventaire passe en vérification (contrôle et correction des écarts)."""
    inventaire = Inventaire.tous.select_for_update().get(pk=inventaire.pk)
    _exiger(inventaire, Inventaire.Statut.EN_COURS)
    inventaire.statut = Inventaire.Statut.A_VERIFIER
    inventaire.comptage_termine_par = auteur
    inventaire.comptage_termine_le = timezone.now()
    inventaire.save(
        update_fields=["statut", "comptage_termine_par", "comptage_termine_le", "modifie_le"]
    )
    return inventaire


@transaction.atomic
def reprendre_comptage(inventaire):
    """Retour au comptage depuis la vérification (une zone à recompter entièrement…)."""
    inventaire = Inventaire.tous.select_for_update().get(pk=inventaire.pk)
    _exiger(inventaire, Inventaire.Statut.A_VERIFIER)
    inventaire.statut = Inventaire.Statut.EN_COURS
    inventaire.save(update_fields=["statut", "modifie_le"])
    return inventaire


@transaction.atomic
def valider_inventaire(inventaire, *, auteur, observation):
    """Validation finale, après vérification : un mouvement d'ajustement par article dont le
    compté diffère du stock, et l'observation de validation."""
    inventaire = Inventaire.tous.select_for_update().get(pk=inventaire.pk)
    if inventaire.statut == Inventaire.Statut.EN_COURS:
        raise InventaireImpossible(
            "Terminez d'abord le comptage : les écarts se vérifient avant la validation finale."
        )
    _exiger(inventaire, Inventaire.Statut.A_VERIFIER)
    observation = observation.strip()
    if not observation:
        raise InventaireImpossible("Saisissez l'observation de la validation finale.")
    for ligne in etat(inventaire):
        LigneInventaire.objects.update_or_create(
            inventaire=inventaire,
            article=ligne["article"],
            defaults={
                "quantite_comptee": ligne["quantite_comptee"],
                "stock_theorique": ligne["stock_theorique"],
                "ecart": ligne["ecart"],
            },
        )
        if ligne["ecart"]:
            MouvementStock.tous.create(
                magasin_id=inventaire.magasin_id,
                article=ligne["article"],
                quantite=ligne["ecart"],
                type=MouvementStock.Type.AJUSTEMENT,
                utilisateur=auteur,
                reference=inventaire.numero,
            )
    inventaire.statut = Inventaire.Statut.VALIDE
    inventaire.valide_par = auteur
    inventaire.valide_le = timezone.now()
    inventaire.observation_validation = observation
    inventaire.save(
        update_fields=[
            "statut",
            "valide_par",
            "valide_le",
            "observation_validation",
            "modifie_le",
        ]
    )
    return inventaire


@transaction.atomic
def annuler_inventaire(inventaire):
    inventaire = Inventaire.tous.select_for_update().get(pk=inventaire.pk)
    _exiger(inventaire, *OUVERTS)
    inventaire.statut = Inventaire.Statut.ANNULE
    inventaire.save(update_fields=["statut", "modifie_le"])
    return inventaire
