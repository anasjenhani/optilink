"""Bons retour fournisseur : marchandise renvoyée au fournisseur.

Deux sortes de lignes : une ligne non conforme d'un bon de réception (elle n'était pas entrée
en stock), ou un article du stock du magasin (il sort du stock). La valeur du bon retour se
déduit ensuite de la facture achat du fournisseur.
"""

from collections import defaultdict
from decimal import Decimal

from django.db import transaction

from apps.stock.models import MouvementStock, stock_disponible
from apps.ventes.models import TypeDocument
from apps.ventes.services import _aujourd_hui, _numero, _prochain_numero, arrondir

from .depot import autre_depot, magasins_geres
from .models import BonRetour, LigneReception, LigneRetour
from .receptions import CENT, TAUX_FODEC, calculer


class RetourImpossible(Exception):
    pass


def non_conformes_a_retourner(magasin, fournisseur):
    """Lignes non conformes des BL de ce fournisseur gérés ici, pas encore renvoyées."""
    return (
        LigneReception.objects.filter(
            non_conforme=True,
            retour__isnull=True,
            bon__fournisseur=fournisseur,
            bon__magasin_id__in=magasins_geres(magasin),
        )
        .select_related("bon__magasin", "article")
        .order_by("bon__date_bl", "bon__sequence", "pk")
    )


def detail_tva_retour(bon):
    """[(taux, base HT, montant TVA)] d'un bon retour, du plus petit taux au plus grand."""
    decimales = bon.magasin.pays.decimales
    coefficient = 1 + (TAUX_FODEC if bon.fournisseur.fodec else 0) / CENT
    bases = defaultdict(Decimal)
    for ligne in bon.lignes.all():
        bases[ligne.taux_tva] += ligne.net_ht
    return [
        {
            "taux": taux,
            "base_ht": arrondir(base, decimales),
            "montant_tva": arrondir(base * coefficient * taux / CENT, decimales),
        }
        for taux, base in sorted(bases.items())
    ]


def _lignes(magasin, fournisseur, lignes):
    """Lignes complètes et contrôlées : non conformes à renvoyer, ou articles du stock."""
    if not lignes:
        raise RetourImpossible("Le bon retour ne contient aucun article.")
    a_renvoyer = {
        ligne.pk: ligne
        for ligne in non_conformes_a_retourner(magasin, fournisseur).select_for_update(of=("self",))
    }
    deja, quantites, completes = set(), defaultdict(int), []
    for numero, ligne in enumerate(lignes, start=1):
        source = ligne.get("ligne_reception")
        if source is not None:
            trouvee = a_renvoyer.get(getattr(source, "pk", source))
            if trouvee is None:
                raise RetourImpossible(
                    f"Ligne {numero} : cet article non conforme n'est pas à renvoyer à "
                    f"{fournisseur} (déjà renvoyé, ou BL d'un autre fournisseur)."
                )
            if trouvee.pk in deja:
                raise RetourImpossible(f"Ligne {numero} : article non conforme en double.")
            deja.add(trouvee.pk)
            completes.append(
                {
                    "article": trouvee.article,
                    "ligne_reception": trouvee,
                    "designation": trouvee.designation,
                    "quantite": trouvee.quantite,
                    "prix_achat_ht": trouvee.prix_achat_ht,
                    "taux_remise": trouvee.taux_remise,
                    "taux_tva": trouvee.taux_tva,
                    "motif": ligne.get("motif", "").strip() or trouvee.motif,
                    "non_conforme": False,
                }
            )
            continue
        article = ligne["article"]
        if article.sur_commande:
            raise RetourImpossible(
                f"Ligne {numero} : {article.libelle} est un verre commandé pour un client ; "
                "renvoyez la ligne non conforme de son bon de réception."
            )
        if ligne["quantite"] < 1:
            raise RetourImpossible(f"Ligne {numero} : quantité d'au moins 1.")
        if ligne["prix_achat_ht"] < 0 or not 0 <= ligne["taux_remise"] <= 100:
            raise RetourImpossible(f"Ligne {numero} : prix ou remise invalide.")
        quantites[article] += ligne["quantite"]
        completes.append(
            {
                **ligne,
                "ligne_reception": None,
                "designation": article.libelle,
                "motif": ligne.get("motif", "").strip(),
                "non_conforme": False,
            }
        )
    for article, quantite in quantites.items():
        disponible = stock_disponible(magasin, article)
        if quantite > disponible:
            raise RetourImpossible(
                f"{article.libelle} : {quantite} à renvoyer, {disponible} en stock à {magasin.nom}."
            )
    return completes


@transaction.atomic
def enregistrer_retour(
    *, magasin, fournisseur, lignes, auteur, date_retour=None, motif="", observation=""
):
    """Enregistre le bon retour ; les articles du stock en sortent.

    ``lignes`` : [{"ligne_reception"}] pour une ligne non conforme d'un bon de réception, ou
    [{"article", "quantite", "prix_achat_ht", "taux_remise", "taux_tva", "motif"?}] pour un
    article du stock.
    """
    depot = autre_depot(magasin)
    if depot is not None:
        raise RetourImpossible(
            f"Les bons retour fournisseur se saisissent au dépôt central ({depot.nom})."
        )
    lignes = _lignes(magasin, fournisseur, lignes)
    pays = magasin.pays
    totaux = calculer(
        lignes, taux_remise_ex=Decimal("0"), fodec=fournisseur.fodec, decimales=pays.decimales
    )
    annee = _aujourd_hui(pays).year
    sequence = _prochain_numero(magasin, annee, TypeDocument.BON_RETOUR)
    bon = BonRetour.tous.create(
        magasin=magasin,
        numero=_numero(magasin, TypeDocument.BON_RETOUR, annee, sequence),
        annee=annee,
        sequence=sequence,
        fournisseur=fournisseur,
        date_retour=date_retour or _aujourd_hui(pays),
        motif=motif.strip()[:200],
        observation=observation,
        cree_par=auteur,
        **totaux,
    )
    for ligne in lignes:
        LigneRetour.objects.create(
            bon=bon,
            article=ligne["article"],
            ligne_reception=ligne["ligne_reception"],
            designation=ligne["designation"][:300],
            quantite=ligne["quantite"],
            prix_achat_ht=ligne["prix_achat_ht"],
            taux_remise=ligne["taux_remise"],
            taux_tva=ligne["taux_tva"],
            net_ht=ligne["net_ht"],
            montant_ttc=ligne["montant_ttc"],
            motif=ligne["motif"][:200],
        )
        if ligne["ligne_reception"] is None:
            MouvementStock.tous.create(
                magasin=magasin,
                article=ligne["article"],
                quantite=-ligne["quantite"],
                type=MouvementStock.Type.RETOUR_FOURNISSEUR,
                utilisateur=auteur,
                reference=bon.numero,
            )
    return bon
