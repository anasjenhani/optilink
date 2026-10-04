from django.db import transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone

from apps.ventes.models import LigneVente, TypeDocument, Vente
from apps.ventes.services import _aujourd_hui, _numero, _prochain_numero

from .models import CasseVerre, CommandeFournisseur, LigneCommandeFournisseur

EN_COURS = [CommandeFournisseur.Statut.ENVOYEE, CommandeFournisseur.Statut.RECUE]


class CommandeFournisseurImpossible(Exception):
    pass


class CasseImpossible(Exception):
    pass


def _verres_valides():
    """Lignes fournisseurs qui comptent encore : commande en cours et verre non cassé."""
    return LigneCommandeFournisseur.objects.filter(
        commande__statut__in=EN_COURS, casse__isnull=True
    )


def verres_a_commander(magasin):
    """Lignes des commandes clients du magasin dont les verres restent à commander."""
    return (
        LigneVente.objects.filter(
            vente__magasin=magasin,
            vente__statut=Vente.Statut.EN_COMMANDE,
            article__sur_commande=True,
        )
        .exclude(Exists(_verres_valides().filter(ligne_vente=OuterRef("pk"))))
        .select_related("vente__client", "article__fournisseur")
        .order_by("vente__cree_le", "pk")
    )


def etat_verres(vente):
    """``None`` sans article sur commande ; sinon ``a_commander``, ``commandes`` ou ``recus``."""
    lignes = [ligne for ligne in vente.lignes.all() if ligne.article.sur_commande]
    if not lignes:
        return None
    statuts = []
    for ligne in lignes:
        commandes = (
            _verres_valides().filter(ligne_vente=ligne).values_list("commande__statut", flat=True)
        )
        statuts.append(next(iter(commandes), None))
    if None in statuts:
        return "a_commander"
    if CommandeFournisseur.Statut.ENVOYEE in statuts:
        return "commandes"
    return "recus"


@transaction.atomic
def passer_commande(*, magasin, fournisseur, lignes, auteur, reference_fournisseur=""):
    """Commande au fournisseur les verres de commandes clients du magasin.

    ``lignes`` : [{"ligne_vente", "details"}] ; chaque ligne n'est commandée qu'une fois.
    """
    if not lignes:
        raise CommandeFournisseurImpossible("La commande ne contient aucun verre.")
    if not fournisseur.est_actif:
        raise CommandeFournisseurImpossible(f"Le fournisseur {fournisseur} n'est plus actif.")
    a_commander = {ligne.pk: ligne for ligne in verres_a_commander(magasin)}
    detail = []
    for demande in lignes:
        ligne = a_commander.get(demande["ligne_vente"])
        if ligne is None:
            raise CommandeFournisseurImpossible(
                "Ligne déjà commandée, sans verre à commander ou hors de ce magasin."
            )
        detail.append((ligne, demande.get("details", "")))

    annee = _aujourd_hui(magasin.pays).year
    sequence = _prochain_numero(magasin, annee, TypeDocument.ACHAT)
    commande = CommandeFournisseur.tous.create(
        magasin=magasin,
        numero=_numero(magasin, TypeDocument.ACHAT, annee, sequence),
        annee=annee,
        sequence=sequence,
        fournisseur=fournisseur,
        reference_fournisseur=reference_fournisseur,
        passee_par=auteur,
    )
    LigneCommandeFournisseur.objects.bulk_create(
        LigneCommandeFournisseur(
            commande=commande,
            ligne_vente=ligne,
            article=ligne.article,
            quantite=ligne.quantite,
            details=details,
        )
        for ligne, details in detail
    )
    return commande


def _verrouiller(commande):
    commande = CommandeFournisseur.tous.select_for_update().get(pk=commande.pk)
    if commande.statut != CommandeFournisseur.Statut.ENVOYEE:
        raise CommandeFournisseurImpossible(
            f"La commande {commande.numero} est déjà {commande.get_statut_display().lower()}."
        )
    return commande


@transaction.atomic
def receptionner(*, commande, utilisateur):
    """Les verres sont arrivés : les commandes clients concernées peuvent être livrées."""
    commande = _verrouiller(commande)
    commande.statut = CommandeFournisseur.Statut.RECUE
    commande.recue_le = timezone.now()
    commande.recue_par = utilisateur
    commande.save(update_fields=["statut", "recue_le", "recue_par", "modifie_le"])
    return commande


@transaction.atomic
def annuler_commande_fournisseur(*, commande):
    """Les verres repassent « à commander » (chez ce fournisseur ou un autre)."""
    commande = _verrouiller(commande)
    commande.statut = CommandeFournisseur.Statut.ANNULEE
    commande.save(update_fields=["statut", "modifie_le"])
    return commande


@transaction.atomic
def declarer_casse(*, ligne_commande, cause, utilisateur, observation=""):
    """Un verre reçu est cassé ou défectueux : il est à recommander, le suivi y revient."""
    from apps.ventes.models import Etape, EtapeCommande

    ligne_commande = (
        LigneCommandeFournisseur.objects.select_for_update(of=("self",))
        .select_related("commande", "ligne_vente__vente")
        .get(pk=ligne_commande.pk)
    )
    vente = Vente.tous.select_for_update().get(pk=ligne_commande.ligne_vente.vente_id)
    if ligne_commande.commande.statut != CommandeFournisseur.Statut.RECUE:
        raise CasseImpossible("Seul un verre déjà reçu du fournisseur peut être déclaré cassé.")
    if CasseVerre.objects.filter(ligne_commande=ligne_commande).exists():
        raise CasseImpossible("Cette casse est déjà déclarée ; le verre est à recommander.")
    if vente.statut != Vente.Statut.EN_COMMANDE:
        raise CasseImpossible(f"La visite {vente.numero} n'est plus une commande en cours.")
    casse = CasseVerre.objects.create(
        ligne_commande=ligne_commande,
        vente=vente,
        cause=cause,
        observation=observation,
        declaree_par=utilisateur,
    )
    # Le suivi repart des verres à commander ; la casse reste tracée dans ses étapes.
    vente.etape = ""
    vente.save(update_fields=["etape", "modifie_le"])
    EtapeCommande.objects.create(
        vente=vente,
        etape=Etape.A_COMMANDER,
        observation=f"Casse verre : {casse.get_cause_display()}"
        + (f" ({observation})" if observation else ""),
        par=utilisateur,
    )
    return casse
