"""Statistiques des ventes sur une période : montures et marques, verres, lentilles, remises,
gratuits, ophtalmologues, TVA, bénéfice journalier.

Comme le reporting, une vente compte le jour où elle est enregistrée et les ventes annulées sont
exclues. Les montants ne s'additionnent qu'entre magasins de même monnaie : on choisit la devise.
Chaque statistique renvoie ses colonnes, ses lignes et ses totaux, pour un affichage uniforme.
"""

from collections import defaultdict
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from apps.achats.models import LigneReception
from apps.stock.models import Article, Lentille, Monture, PrixArticle, Verre
from apps.ventes.models import LigneAvoir, LigneVente, Vente
from apps.ventes.services import arrondir

ZERO = Decimal("0")
CENT = Decimal("100")

TEXTE, NOMBRE, MONTANT, POURCENT, DATE = "texte", "nombre", "montant", "pourcent", "date"


def _colonnes(*definitions):
    return [{"cle": cle, "libelle": libelle, "type": type_} for cle, libelle, type_ in definitions]


def _ht(ttc, taux, decimales):
    return arrondir(ttc / (1 + taux / CENT), decimales)


def _pourcent(partie, tout):
    return (partie * CENT / tout).quantize(Decimal("0.01")) if tout else ZERO


class Periode:
    """Ventes non annulées d'une devise, enregistrées entre ``du`` et ``au``, dans ``magasins``."""

    def __init__(self, magasins, devise, decimales, du, au):
        self.magasins, self.devise, self.decimales, self.du, self.au = (
            magasins,
            devise,
            decimales,
            du,
            au,
        )
        self.ventes = Vente.tous.filter(
            magasin__in=magasins,
            devise=devise,
            cree_le__date__gte=du,
            cree_le__date__lte=au,
        ).exclude(statut=Vente.Statut.ANNULEE)

    def lignes(self, **filtre):
        return LigneVente.objects.filter(vente__in=self.ventes, **filtre)


def _par_article(periode, famille, cle_de, colonnes_cle):
    """Quantité et chiffre d'affaires d'une famille, regroupés par ``cle_de(caracteristiques)``."""
    groupes = defaultdict(lambda: {"quantite": 0, "ca_ttc": ZERO, "ca_ht": ZERO, "remise": ZERO})
    lignes = periode.lignes(article__famille=famille).select_related(
        f"article__{famille}", "article__fournisseur"
    )
    for ligne in lignes:
        cle = cle_de(ligne.article)
        groupe = groupes[cle]
        groupe["quantite"] += ligne.quantite
        groupe["ca_ttc"] += ligne.total_ttc
        groupe["ca_ht"] += _ht(ligne.total_ttc, ligne.taux_tva, periode.decimales)
        groupe["remise"] += ligne.prix_unitaire_ttc * ligne.quantite - ligne.total_ttc
    total_ttc = sum((g["ca_ttc"] for g in groupes.values()), ZERO)
    resultat = []
    for cle, groupe in sorted(groupes.items(), key=lambda g: -g[1]["ca_ttc"]):
        resultat.append(
            {
                **dict(zip([c[0] for c in colonnes_cle], cle, strict=True)),
                **groupe,
                "part": _pourcent(groupe["ca_ttc"], total_ttc),
            }
        )
    colonnes = _colonnes(
        *colonnes_cle,
        ("quantite", "Quantité", NOMBRE),
        ("ca_ttc", "CA TTC", MONTANT),
        ("ca_ht", "CA HT", MONTANT),
        ("remise", "Remises accordées", MONTANT),
        ("part", "Part du CA", POURCENT),
    )
    return colonnes, resultat


def _caracteristique(article, famille):
    try:
        return getattr(article, famille)
    except (Monture.DoesNotExist, Verre.DoesNotExist, Lentille.DoesNotExist):
        return None


def _marque(article, carac):
    if carac is not None and carac.marque:
        return carac.marque
    return article.fournisseur.nom if article.fournisseur_id else "Sans marque"


def montures(periode):
    def cle(article):
        carac = _caracteristique(article, "monture")
        categorie = carac.get_categorie_display() if carac and carac.categorie else ""
        return _marque(article, carac), categorie

    return _par_article(
        periode,
        Article.Famille.MONTURE,
        cle,
        [("marque", "Marque", TEXTE), ("categorie", "Catégorie", TEXTE)],
    )


def verres(periode):
    def cle(article):
        carac = _caracteristique(article, "verre")
        if carac is None:
            return _marque(article, None), "", ""
        indice = f"{carac.indice:.2f}" if carac.indice else ""
        return _marque(article, carac), carac.get_geometrie_display(), indice

    return _par_article(
        periode,
        Article.Famille.VERRE,
        cle,
        [
            ("marque", "Marque", TEXTE),
            ("geometrie", "Géométrie", TEXTE),
            ("indice", "Indice", TEXTE),
        ],
    )


def lentilles(periode):
    def cle(article):
        carac = _caracteristique(article, "lentille")
        renouvellement = carac.get_renouvellement_display() if carac else ""
        return _marque(article, carac), renouvellement

    return _par_article(
        periode,
        Article.Famille.LENTILLE,
        cle,
        [("marque", "Marque", TEXTE), ("renouvellement", "Renouvellement", TEXTE)],
    )


def _nom(utilisateur):
    return utilisateur.get_full_name() or utilisateur.get_username()


def remises(periode):
    """Remises accordées, par vendeur : montant cédé et taux moyen sur le prix catalogue."""
    groupes = defaultdict(lambda: {"lignes": 0, "ventes": set(), "catalogue": ZERO, "remise": ZERO})
    for ligne in periode.lignes(remise_pct__gt=0).select_related("vente__vendeur"):
        groupe = groupes[_nom(ligne.vente.vendeur)]
        catalogue = ligne.prix_unitaire_ttc * ligne.quantite
        groupe["lignes"] += 1
        groupe["ventes"].add(ligne.vente_id)
        groupe["catalogue"] += catalogue
        groupe["remise"] += catalogue - ligne.total_ttc
    lignes = [
        {
            "vendeur": vendeur,
            "ventes": len(g["ventes"]),
            "lignes": g["lignes"],
            "catalogue": g["catalogue"],
            "remise": g["remise"],
            "taux": _pourcent(g["remise"], g["catalogue"]),
        }
        for vendeur, g in sorted(groupes.items(), key=lambda g: -g[1]["remise"])
    ]
    colonnes = _colonnes(
        ("vendeur", "Vendeur", TEXTE),
        ("ventes", "Visites remisées", NOMBRE),
        ("lignes", "Articles remisés", NOMBRE),
        ("catalogue", "Prix catalogue TTC", MONTANT),
        ("remise", "Remise accordée", MONTANT),
        ("taux", "Taux moyen", POURCENT),
    )
    return colonnes, lignes


def gratuits(periode):
    """Articles offerts (vendus à 0) : quantité et valeur au prix catalogue, par article."""
    groupes = defaultdict(lambda: {"quantite": 0, "valeur": ZERO})
    for ligne in periode.lignes(total_ttc=0).select_related("article"):
        groupe = groupes[(ligne.article.get_famille_display(), ligne.libelle)]
        groupe["quantite"] += ligne.quantite
        groupe["valeur"] += ligne.prix_unitaire_ttc * ligne.quantite
    lignes = [
        {"famille": famille, "article": libelle, **g}
        for (famille, libelle), g in sorted(groupes.items(), key=lambda g: -g[1]["valeur"])
    ]
    colonnes = _colonnes(
        ("famille", "Famille", TEXTE),
        ("article", "Article", TEXTE),
        ("quantite", "Quantité offerte", NOMBRE),
        ("valeur", "Valeur au prix catalogue", MONTANT),
    )
    return colonnes, lignes


def ophtalmologues(periode):
    """Visites par ophtalmologue prescripteur (ordonnance des lunettes ou des lentilles)."""
    prescripteurs = {}
    for vente in periode.ventes.prefetch_related(
        "lunettes__prescription", "lentilles__prescription"
    ):
        equipements = [*vente.lunettes.all(), *vente.lentilles.all()]
        noms = {e.prescription.prescripteur.strip() for e in equipements if e.prescription_id}
        for nom in noms or ({"Sans ordonnance"} if equipements else set()):
            groupe = prescripteurs.setdefault(nom or "Non précisé", {"visites": 0, "ca_ttc": ZERO})
            groupe["visites"] += 1
            # Une visite à deux ordonnances de médecins différents compte pour chacun.
            groupe["ca_ttc"] += vente.total_ttc
    total = sum((g["visites"] for g in prescripteurs.values()), 0)
    lignes = [
        {"ophtalmologue": nom, **g, "part": _pourcent(Decimal(g["visites"]), Decimal(total))}
        for nom, g in sorted(prescripteurs.items(), key=lambda g: -g[1]["visites"])
    ]
    colonnes = _colonnes(
        ("ophtalmologue", "Ophtalmologue", TEXTE),
        ("visites", "Visites", NOMBRE),
        ("ca_ttc", "CA TTC", MONTANT),
        ("part", "Part des visites", POURCENT),
    )
    return colonnes, lignes


def tva(periode):
    """TVA collectée par taux : ventes de la période, moins les avoirs émis sur la période."""
    groupes = defaultdict(lambda: {"ventes_ttc": ZERO, "ventes_ht": ZERO, "avoirs_ttc": ZERO})
    groupes_avoirs = defaultdict(lambda: ZERO)
    for ligne in periode.lignes():
        groupe = groupes[ligne.taux_tva]
        groupe["ventes_ttc"] += ligne.total_ttc
        groupe["ventes_ht"] += _ht(ligne.total_ttc, ligne.taux_tva, periode.decimales)
    avoirs = LigneAvoir.objects.filter(
        avoir__magasin__in=periode.magasins,
        avoir__devise=periode.devise,
        avoir__cree_le__date__gte=periode.du,
        avoir__cree_le__date__lte=periode.au,
    )
    for ligne in avoirs:
        groupes[ligne.taux_tva]["avoirs_ttc"] += ligne.total_ttc
        groupes_avoirs[ligne.taux_tva] += _ht(ligne.total_ttc, ligne.taux_tva, periode.decimales)
    lignes = []
    for taux, g in sorted(groupes.items(), reverse=True):
        net_ttc = g["ventes_ttc"] - g["avoirs_ttc"]
        net_ht = g["ventes_ht"] - groupes_avoirs[taux]
        lignes.append(
            {
                "taux": f"{taux.normalize():f} %",
                "ventes_ttc": g["ventes_ttc"],
                "avoirs_ttc": g["avoirs_ttc"],
                "base_ht": net_ht,
                "tva": net_ttc - net_ht,
                "net_ttc": net_ttc,
            }
        )
    colonnes = _colonnes(
        ("taux", "Taux", TEXTE),
        ("ventes_ttc", "Ventes TTC", MONTANT),
        ("avoirs_ttc", "Avoirs TTC", MONTANT),
        ("base_ht", "Base HT nette", MONTANT),
        ("tva", "TVA collectée", MONTANT),
        ("net_ttc", "Net TTC", MONTANT),
    )
    return colonnes, lignes


def _cout_unitaire(ligne, couts_recus, tarifs):
    """Coût d'achat HT d'une unité : le verre reçu pour ce client, sinon le tarif d'achat."""
    if ligne.pk in couts_recus:
        return couts_recus[ligne.pk]
    tarif = tarifs.get(ligne.article_id)
    if tarif is None or tarif.prix_achat_ht is None:
        return None
    return tarif.prix_achat_ht * (1 - tarif.taux_remise_achat / CENT)


def benefice(periode):
    """Bénéfice brut par jour : CA HT moins le coût d'achat HT des articles vendus.

    Le coût d'un verre commandé pour le client est celui de sa réception ; pour les autres
    articles, le prix d'achat net du tarif. Une ligne sans coût connu est signalée à part.
    """
    lignes_vente = list(periode.lignes().select_related("vente"))
    recus = (
        LigneReception.objects.filter(
            ligne_commande__ligne_vente__in=[ligne.pk for ligne in lignes_vente],
            non_conforme=False,
        )
        .values("ligne_commande__ligne_vente")
        .annotate(net=Sum("net_ht"), quantite=Sum("quantite"))
    )
    couts_recus = {
        r["ligne_commande__ligne_vente"]: r["net"] / r["quantite"] for r in recus if r["quantite"]
    }
    pays = periode.magasins[0].pays if periode.magasins else None
    tarifs = {
        t.article_id: t
        for t in PrixArticle.objects.filter(
            pays=pays, article_id__in={ligne.article_id for ligne in lignes_vente}
        )
    }
    jours = defaultdict(lambda: {"ca_ht": ZERO, "cout": ZERO, "sans_cout": 0, "ventes": set()})
    for ligne in lignes_vente:
        jour = jours[timezone.localtime(ligne.vente.cree_le).date()]
        jour["ventes"].add(ligne.vente_id)
        jour["ca_ht"] += _ht(ligne.total_ttc, ligne.taux_tva, periode.decimales)
        cout = _cout_unitaire(ligne, couts_recus, tarifs)
        if cout is None:
            jour["sans_cout"] += 1
        else:
            jour["cout"] += arrondir(cout * ligne.quantite, periode.decimales)
    lignes = [
        {
            "jour": jour.isoformat(),
            "ventes": len(j["ventes"]),
            "ca_ht": j["ca_ht"],
            "cout": j["cout"],
            "benefice": j["ca_ht"] - j["cout"],
            "marge": _pourcent(j["ca_ht"] - j["cout"], j["ca_ht"]),
            "sans_cout": j["sans_cout"],
        }
        for jour, j in sorted(jours.items())
    ]
    colonnes = _colonnes(
        ("jour", "Jour", DATE),
        ("ventes", "Visites", NOMBRE),
        ("ca_ht", "CA HT", MONTANT),
        ("cout", "Coût d'achat HT", MONTANT),
        ("benefice", "Bénéfice brut", MONTANT),
        ("marge", "Taux de marge", POURCENT),
        ("sans_cout", "Articles sans coût connu", NOMBRE),
    )
    return colonnes, lignes


RAPPORTS = {
    "montures": ("Montures et marques", montures),
    "verres": ("Verres", verres),
    "lentilles": ("Lentilles", lentilles),
    "remises": ("Remises", remises),
    "gratuits": ("Gratuits", gratuits),
    "ophtalmologues": ("Ophtalmologues", ophtalmologues),
    "tva": ("TVA", tva),
    "benefice": ("Bénéfice journalier", benefice),
}


def calculer(rapport, periode):
    titre, fonction = RAPPORTS[rapport]
    colonnes, lignes = fonction(periode)
    totaux = {}
    for colonne in colonnes:
        if colonne["type"] in (NOMBRE, MONTANT):
            totaux[colonne["cle"]] = sum((ligne[colonne["cle"]] for ligne in lignes), 0)
    # Les taux ne s'additionnent pas : on les recalcule sur les totaux quand c'est possible.
    if rapport == "benefice":
        totaux["marge"] = _pourcent(totaux["benefice"], totaux["ca_ht"])
    if rapport == "remises":
        totaux["taux"] = _pourcent(totaux["remise"], totaux["catalogue"])
    return {"titre": titre, "colonnes": colonnes, "lignes": lignes, "totaux": totaux}
