"""Bons de réception achat : contrôle, calcul des totaux, entrée en stock, verres reçus."""

from collections import defaultdict
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.stock.models import MouvementStock, PrixArticle
from apps.ventes.models import TypeDocument
from apps.ventes.services import _aujourd_hui, _numero, _prochain_numero, arrondir

from .depot import autre_depot
from .models import BonReception, CommandeFournisseur, LigneCommandeFournisseur, LigneReception

TAUX_FODEC = Decimal("1")
CENT = Decimal("100")
OEIL_DU_ROLE = {"verre_d": "D", "verre_g": "G", "supplement_d": "D", "supplement_g": "G"}


class ReceptionImpossible(Exception):
    pass


def lignes_a_recevoir(magasin, fournisseur):
    """Verres commandés à ce fournisseur pour les clients du magasin, pas encore reçus."""
    return (
        LigneCommandeFournisseur.objects.filter(
            commande__magasin=magasin,
            commande__fournisseur=fournisseur,
            commande__statut=CommandeFournisseur.Statut.ENVOYEE,
        )
        .exclude(receptions__non_conforme=False)
        .select_related("commande", "article", "ligne_vente__vente__client")
        .order_by("commande__numero", "pk")
    )


def oeil_de(ligne_commande):
    return OEIL_DU_ROLE.get(getattr(ligne_commande.ligne_vente, "role", ""), "")


def derniers_prix(articles):
    """Dernier prix d'achat HT de chaque article (bon de réception le plus récent)."""
    prix = {}
    lignes = (
        LigneReception.objects.filter(article__in=articles)
        .order_by("article_id", "-bon__date_saisie", "-bon__cree_le", "-pk")
        .values_list("article_id", "prix_achat_ht")
    )
    for article_id, montant in lignes:
        prix.setdefault(article_id, montant)
    return prix


def taux_tva_par_defaut(articles, pays):
    """Taux du prix de vente de l'article dans le pays, sinon le taux le plus élevé du pays."""
    taux = dict(
        PrixArticle.objects.filter(article__in=articles, pays=pays).values_list(
            "article_id", "tva__taux"
        )
    )
    normal = pays.taux_tva.order_by("-taux").values_list("taux", flat=True).first()
    return {article.pk: taux.get(article.pk, normal or Decimal("0")) for article in articles}


def calculer(lignes, *, taux_remise_ex, fodec, decimales):
    """Totaux d'un bon : tout ce que le fournisseur a livré, comme sur son BL. Les lignes non
    conformes comptent aussi (le fournisseur les facture) ; elles n'entrent pas en stock et se
    renvoient par un bon retour, déduit de la facture achat.

    La remise exceptionnelle s'applique au net HT ; le FODEC (1 %) au net HT après remise ;
    la TVA, taux par taux, au net HT après remise plus le FODEC.
    """
    total_ht = total_remise = total_net = Decimal("0")
    bases = defaultdict(Decimal)
    for ligne in lignes:
        brut = ligne["prix_achat_ht"] * ligne["quantite"]
        remise = brut * ligne["taux_remise"] / CENT
        net = brut - remise
        ligne["net_ht"] = arrondir(net, decimales)
        ligne["montant_ttc"] = arrondir(net * (1 + ligne["taux_tva"] / CENT), decimales)
        total_ht += brut
        total_remise += remise
        total_net += net
        bases[ligne["taux_tva"]] += net
    coefficient = (1 - taux_remise_ex / CENT) * (1 + (TAUX_FODEC if fodec else 0) / CENT)
    tva = {
        taux: arrondir(base * coefficient * taux / CENT, decimales) for taux, base in bases.items()
    }
    remise_ex = arrondir(total_net * taux_remise_ex / CENT, decimales)
    net_ht = arrondir(total_net, decimales) - remise_ex
    total_fodec = arrondir(net_ht * TAUX_FODEC / CENT, decimales) if fodec else Decimal("0")
    total_tva = sum(tva.values(), Decimal("0"))
    return {
        "total_ht": arrondir(total_ht, decimales),
        "total_remise": arrondir(total_remise, decimales),
        "remise_ex": remise_ex,
        "total_net_ht": net_ht,
        "total_fodec": total_fodec,
        "total_tva": total_tva,
        "total_ttc": net_ht + total_fodec + total_tva,
    }


def detail_tva(bon):
    """[(taux, base HT, montant TVA)] d'un bon enregistré, du plus petit taux au plus grand."""
    decimales = bon.magasin.pays.decimales
    coefficient = (1 - bon.taux_remise_ex / CENT) * (
        1 + (TAUX_FODEC if bon.fournisseur.fodec else 0) / CENT
    )
    bases = defaultdict(Decimal)
    for ligne in bon.lignes.all():
        bases[ligne.taux_tva] += ligne.net_ht
    return [
        {
            "taux": taux,
            "base_ht": arrondir(base * (1 - bon.taux_remise_ex / CENT), decimales),
            "montant_tva": arrondir(base * coefficient * taux / CENT, decimales),
        }
        for taux, base in sorted(bases.items())
    ]


def _controler_lignes(magasin, fournisseur, lignes):
    if not lignes:
        raise ReceptionImpossible("Le bon ne contient aucun article.")
    deja = set()
    for numero, ligne in enumerate(lignes, start=1):
        article, commande = ligne["article"], ligne.get("ligne_commande")
        if ligne["quantite"] < 1:
            raise ReceptionImpossible(f"Ligne {numero} : quantité d'au moins 1.")
        if ligne["prix_achat_ht"] < 0 or not 0 <= ligne["taux_remise"] <= 100:
            raise ReceptionImpossible(f"Ligne {numero} : prix ou remise invalide.")
        if ligne["non_conforme"] and not ligne.get("motif", "").strip():
            raise ReceptionImpossible(f"Ligne {numero} ({article.libelle}) : motif obligatoire.")
        if commande is None:
            if article.sur_commande:
                raise ReceptionImpossible(
                    f"Ligne {numero} : {article.libelle} se commande pour un client ; "
                    "importez le bon de commande."
                )
            continue
        if commande.pk in deja:
            raise ReceptionImpossible(f"Ligne {numero} : ce verre commandé est en double.")
        deja.add(commande.pk)
        if (
            commande.commande.magasin_id != magasin.pk
            or commande.commande.fournisseur_id != fournisseur.pk
            or commande.commande.statut != CommandeFournisseur.Statut.ENVOYEE
            or commande.receptions.filter(non_conforme=False).exists()
        ):
            raise ReceptionImpossible(
                f"Ligne {numero} : le verre de la commande {commande.commande.numero} n'est pas "
                "à recevoir de ce fournisseur dans ce magasin."
            )
        if commande.article_id != article.pk:
            raise ReceptionImpossible(f"Ligne {numero} : article différent de celui commandé.")


@transaction.atomic
def enregistrer_reception(
    *,
    magasin,
    fournisseur,
    numero_bl,
    date_bl,
    lignes,
    auteur,
    date_saisie=None,
    taux_remise_ex=Decimal("0"),
    observation="",
):
    """Enregistre le bon : stock du dépôt de réception, verres des clients reçus, totaux figés.

    ``lignes`` : [{"article", "quantite", "prix_achat_ht", "taux_remise", "taux_tva",
    "non_conforme", "motif", "ligne_commande"?, "numero_serie"?, "numero_lot"?,
    "date_peremption"?}]
    """
    if not fournisseur.est_actif:
        raise ReceptionImpossible(f"Le fournisseur {fournisseur} n'est plus actif.")
    depot = autre_depot(magasin)
    if depot is not None and any(not ligne.get("ligne_commande") for ligne in lignes):
        raise ReceptionImpossible(
            f"Les montures, lentilles et produits se reçoivent au dépôt central ({depot.nom}). "
            "Le magasin reçoit seulement les verres commandés pour ses clients."
        )
    numero_bl = numero_bl.strip()
    if BonReception.tous.filter(fournisseur=fournisseur, numero_bl=numero_bl).exists():
        raise ReceptionImpossible(f"Le BL {numero_bl} de {fournisseur} est déjà enregistré.")
    if not 0 <= taux_remise_ex <= 100:
        raise ReceptionImpossible("Remise exceptionnelle entre 0 et 100 %.")
    commandes = {
        c.pk: c
        for c in LigneCommandeFournisseur.objects.select_for_update(of=("self",))
        .select_related("commande", "ligne_vente")
        .filter(pk__in=[ligne["ligne_commande"] for ligne in lignes if ligne.get("ligne_commande")])
    }
    for ligne in lignes:
        if ligne.get("ligne_commande"):
            if ligne["ligne_commande"] not in commandes:
                raise ReceptionImpossible("Verre commandé introuvable ou hors de ce magasin.")
            ligne["ligne_commande"] = commandes[ligne["ligne_commande"]]
    _controler_lignes(magasin, fournisseur, lignes)

    pays = magasin.pays
    totaux = calculer(
        lignes, taux_remise_ex=taux_remise_ex, fodec=fournisseur.fodec, decimales=pays.decimales
    )
    annee = _aujourd_hui(pays).year
    sequence = _prochain_numero(magasin, annee, TypeDocument.RECEPTION)
    depot_stock = magasin.depot_de_reception
    bon = BonReception.tous.create(
        magasin=magasin,
        depot=depot_stock,
        numero=_numero(magasin, TypeDocument.RECEPTION, annee, sequence),
        annee=annee,
        sequence=sequence,
        fournisseur=fournisseur,
        date_saisie=date_saisie or _aujourd_hui(pays),
        numero_bl=numero_bl,
        date_bl=date_bl,
        observation=observation,
        taux_remise_ex=taux_remise_ex,
        cree_par=auteur,
        **totaux,
    )
    for ligne in lignes:
        article, commande = ligne["article"], ligne.get("ligne_commande")
        LigneReception.objects.create(
            bon=bon,
            article=article,
            ligne_commande=commande,
            oeil=oeil_de(commande) if commande else ligne.get("oeil", ""),
            designation=(commande.details if commande and commande.details else article.libelle)[
                :300
            ],
            quantite=ligne["quantite"],
            prix_achat_ht=ligne["prix_achat_ht"],
            taux_remise=ligne["taux_remise"],
            taux_tva=ligne["taux_tva"],
            net_ht=ligne["net_ht"],
            montant_ttc=ligne["montant_ttc"],
            non_conforme=ligne["non_conforme"],
            motif=ligne.get("motif", "").strip() if ligne["non_conforme"] else "",
            numero_serie=ligne.get("numero_serie", ""),
            numero_lot=ligne.get("numero_lot", ""),
            date_peremption=ligne.get("date_peremption"),
        )
        if not ligne["non_conforme"] and commande is None:
            MouvementStock.tous.create(
                magasin=magasin,
                depot=depot_stock,
                article=article,
                quantite=ligne["quantite"],
                type=MouvementStock.Type.RECEPTION,
                utilisateur=auteur,
                reference=bon.numero,
            )
    _marquer_commandes_recues({c.commande for c in commandes.values()}, auteur)
    return bon


def _marquer_commandes_recues(commandes, auteur):
    """Une commande fournisseur dont tous les verres sont reçus conformes passe « reçue »."""
    for commande in commandes:
        reste = commande.lignes.exclude(receptions__non_conforme=False).exists()
        if not reste:
            commande.statut = CommandeFournisseur.Statut.RECUE
            commande.recue_le = timezone.now()
            commande.recue_par = auteur
            commande.save(update_fields=["statut", "recue_le", "recue_par", "modifie_le"])
