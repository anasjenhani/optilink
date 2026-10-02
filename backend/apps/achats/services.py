from django.db import transaction
from django.utils import timezone

from apps.ventes.models import LigneVente, TypeDocument, Vente
from apps.ventes.services import _aujourd_hui, _numero, _prochain_numero

from .models import CommandeFournisseur, LigneCommandeFournisseur

EN_COURS = [CommandeFournisseur.Statut.ENVOYEE, CommandeFournisseur.Statut.RECUE]


class CommandeFournisseurImpossible(Exception):
    pass


def verres_a_commander(magasin):
    """Lignes des commandes clients du magasin dont les verres restent à commander."""
    return (
        LigneVente.objects.filter(
            vente__magasin=magasin,
            vente__statut=Vente.Statut.EN_COMMANDE,
            article__sur_commande=True,
        )
        .exclude(commandes_fournisseur__commande__statut__in=EN_COURS)
        .select_related("vente__client", "article")
        .order_by("vente__cree_le", "pk")
    )


def etat_verres(vente):
    """``None`` sans article sur commande ; sinon ``a_commander``, ``commandes`` ou ``recus``."""
    lignes = [ligne for ligne in vente.lignes.all() if ligne.article.sur_commande]
    if not lignes:
        return None
    statuts = []
    for ligne in lignes:
        commandes = LigneCommandeFournisseur.objects.filter(
            ligne_vente=ligne, commande__statut__in=EN_COURS
        ).values_list("commande__statut", flat=True)
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
