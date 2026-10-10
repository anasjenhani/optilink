"""Alertes du jour : ce qui attend une action, selon les droits et le périmètre de chacun.

Rien n'est stocké : chaque alerte est recalculée à la demande à partir des données métier.
Une alerte indique le module et l'écran de l'application où la traiter.
"""

from dataclasses import asdict, dataclass

from django.conf import settings
from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.reseau.models import Magasin
from apps.rh.models import Acompte, DemandeConge, Prime
from apps.stock.models import MouvementStock
from apps.tresorerie.models import ClotureCaisse, OperationTresorerie
from apps.ventes.models import DossierSav, Vente


@dataclass
class Alerte:
    code: str
    gravite: str  # haute, moyenne ou info
    titre: str
    detail: str
    magasin: str
    nombre: int
    module: str
    ecran: str


def magasins_couverts(utilisateur, permission):
    return {
        m.pk: m for m in Magasin.tous.select_related("pays") if utilisateur.has_perm(permission, m)
    }


def _par_magasin(lignes, magasins):
    """« [{magasin: id, n: 3}] » → [(magasin, 3)], dans l'ordre des noms de magasin."""
    resultat = [(magasins[ligne["magasin"]], ligne["n"]) for ligne in lignes if ligne["n"]]
    return sorted(resultat, key=lambda paire: paire[0].nom)


def _toutes(modele):
    """Lignes de tous les magasins ; le périmètre est appliqué ici, magasin par magasin."""
    return getattr(modele, "tous", modele._default_manager)


def _pluriel(nombre, singulier, pluriel=None):
    return f"{nombre} {singulier if nombre == 1 else (pluriel or singulier + 's')}"


def _commandes_en_retard(utilisateur, aujourdhui):
    magasins = magasins_couverts(utilisateur, "ventes.view_vente")
    lignes = (
        Vente.tous.filter(
            magasin__in=magasins,
            statut=Vente.Statut.EN_COMMANDE,
            livraison_prevue_le__lt=aujourdhui,
        )
        .values("magasin")
        .annotate(n=Count("pk"))
    )
    for magasin, n in _par_magasin(lignes, magasins):
        yield Alerte(
            "commandes_en_retard",
            "haute",
            "Commandes en retard",
            f"{_pluriel(n, 'commande')} dont la date de livraison prévue est dépassée.",
            magasin.nom,
            n,
            "vente",
            "commandes",
        )


def _stock_faible(utilisateur):
    magasins = magasins_couverts(utilisateur, "stock.view_article")
    seuil = settings.STOCK_ALERTE_SEUIL
    # Seuls les articles déjà entrés dans le magasin sont suivis ; les verres, commandés pour
    # chaque client, n'ont pas de stock. Le dépôt casse ne compte pas.
    lignes = (
        MouvementStock.tous.filter(
            magasin__in=magasins, article__est_actif=True, article__sur_commande=False
        )
        .exclude(depot__type="casse")
        .values("magasin", "article__libelle")
        .annotate(stock=Sum("quantite"))
        .filter(stock__lte=seuil)
        .order_by("magasin", "article__libelle")
    )
    par_magasin = {}
    for ligne in lignes:
        par_magasin.setdefault(ligne["magasin"], []).append(ligne["article__libelle"])
    for magasin_id, libelles in sorted(par_magasin.items(), key=lambda p: magasins[p[0]].nom):
        exemples = ", ".join(libelles[:5]) + ("…" if len(libelles) > 5 else "")
        yield Alerte(
            "stock_faible",
            "moyenne",
            "Stock faible",
            f"{_pluriel(len(libelles), 'article')} à {seuil} ou moins : {exemples}",
            magasins[magasin_id].nom,
            len(libelles),
            "stock",
            "stock-monture",
        )


def _par_statut(utilisateur, permission, modele, statut, code, gravite, titre, phrase, lien):
    magasins = magasins_couverts(utilisateur, permission)
    lignes = (
        _toutes(modele)
        .filter(magasin__in=magasins, statut=statut)
        .values("magasin")
        .annotate(n=Count("pk"))
    )
    for magasin, n in _par_magasin(lignes, magasins):
        yield Alerte(code, gravite, titre, phrase(n), magasin.nom, n, *lien)


def _versements_en_retard(utilisateur, aujourdhui):
    magasins = magasins_couverts(utilisateur, "tresorerie.view_operationtresorerie")
    lignes = (
        _toutes(OperationTresorerie)
        .filter(
            Q(magasin__in=magasins)
            | Q(magasin__isnull=True, societe__in={m.societe_id for m in magasins.values()}),
            statut=OperationTresorerie.Statut.PREVUE,
            date_prevue__lt=aujourdhui,
        )
        .values("magasin")
        .annotate(n=Count("pk"))
    )
    for ligne in lignes:
        magasin = magasins.get(ligne["magasin"])
        yield Alerte(
            "versements_en_retard",
            "moyenne",
            "Versements en retard",
            f"{_pluriel(ligne['n'], 'versement prévu', 'versements prévus')} "
            "dont la date est dépassée.",
            magasin.nom if magasin else "",
            ligne["n"],
            "caisse",
            "versement",
        )


def _sav(utilisateur, aujourdhui):
    magasins = magasins_couverts(utilisateur, "ventes.view_dossiersav")
    en_retard = (
        DossierSav.tous.filter(
            magasin__in=magasins,
            etape__in=DossierSav.EN_ATTENTE,
            retour_prevu_le__lt=aujourdhui,
        )
        .values("magasin")
        .annotate(n=Count("pk"))
    )
    for magasin, n in _par_magasin(en_retard, magasins):
        yield Alerte(
            "sav_en_retard",
            "haute",
            "SAV en retard",
            f"{_pluriel(n, 'dossier')} SAV dont la date de retour prévue est dépassée.",
            magasin.nom,
            n,
            "sav",
            "dossiers-sav",
        )
    prets = (
        DossierSav.tous.filter(magasin__in=magasins, etape=DossierSav.Etape.PRET)
        .values("magasin")
        .annotate(n=Count("pk"))
    )
    for magasin, n in _par_magasin(prets, magasins):
        yield Alerte(
            "sav_prets",
            "info",
            "SAV prêts à rendre",
            f"{_pluriel(n, 'dossier SAV prêt', 'dossiers SAV prêts')} à rendre : "
            "prévenir le client.",
            magasin.nom,
            n,
            "sav",
            "dossiers-sav",
        )


ORDRE = {"haute": 0, "moyenne": 1, "info": 2}


def alertes(utilisateur):
    aujourdhui = timezone.localdate()
    trouvees = [
        *_commandes_en_retard(utilisateur, aujourdhui),
        *_sav(utilisateur, aujourdhui),
        *_stock_faible(utilisateur),
        *_par_statut(
            utilisateur,
            "tresorerie.add_cloturecaisse",
            ClotureCaisse,
            ClotureCaisse.Statut.REJETEE,
            "clotures_rejetees",
            "haute",
            "Clôtures de caisse rejetées",
            lambda n: (
                f"{_pluriel(n, 'clôture rejetée', 'clôtures rejetées')} par la finance, "
                "à corriger et renvoyer."
            ),
            ("caisse", "session-en-cours"),
        ),
        *_par_statut(
            utilisateur,
            "tresorerie.valider_cloturecaisse",
            ClotureCaisse,
            ClotureCaisse.Statut.ENVOYEE,
            "clotures_a_verifier",
            "moyenne",
            "Clôtures de caisse à vérifier",
            lambda n: f"{_pluriel(n, 'clôture envoyée', 'clôtures envoyées')} par les caissiers.",
            ("caisse", "validation"),
        ),
        *_versements_en_retard(utilisateur, aujourdhui),
        *_par_statut(
            utilisateur,
            "rh.decider_demandeconge",
            DemandeConge,
            DemandeConge.Statut.DEMANDEE,
            "conges_a_decider",
            "info",
            "Demandes de congé",
            lambda n: f"{_pluriel(n, 'demande')} de congé à accepter ou refuser.",
            ("administration", "rh"),
        ),
        *_par_statut(
            utilisateur,
            "rh.decider_acompte",
            Acompte,
            Acompte.Statut.DEMANDE,
            "acomptes_a_decider",
            "info",
            "Demandes d'acompte",
            lambda n: f"{_pluriel(n, 'demande')} d'acompte à accorder ou refuser.",
            ("administration", "rh"),
        ),
        *_par_statut(
            utilisateur,
            "rh.valider_prime",
            Prime,
            Prime.Statut.PROPOSEE,
            "primes_a_valider",
            "info",
            "Primes proposées",
            lambda n: f"{_pluriel(n, 'prime proposée', 'primes proposées')} à valider.",
            ("administration", "rh"),
        ),
    ]
    trouvees.sort(key=lambda a: (ORDRE[a.gravite], a.titre, a.magasin))
    return [asdict(a) for a in trouvees]
