"""Suivi qualité des commandes (lunettes et lentilles) et état de la journée de vente.

Étapes d'une commande : à commander, commandée (en attente du BL), montage, contrôle qualité,
client prévenu, puis livrée. Les deux premières viennent des commandes de verres au fournisseur ;
les suivantes sont saisies au fil de l'atelier, chaque passage étant tracé (qui, quand,
observation). « En instance » met une commande de côté (problème, attente du client…).
"""

from decimal import Decimal

from django.db import transaction
from django.db.models import Q

from .models import Etape, EtapeCommande, Paiement, Vente

ORDRE = [Etape.A_COMMANDER, Etape.COMMANDEE, Etape.MONTAGE, Etape.CONTROLE, Etape.CONTACT_CLIENT]
DEPUIS_LES_VERRES = {
    "a_commander": Etape.A_COMMANDER,
    "commandes": Etape.COMMANDEE,
    "recus": Etape.MONTAGE,
}
LIVREE = "livree"


class EtapeImpossible(Exception):
    pass


def commandes(queryset):
    """Commandes en cours ou livrées ; une vente remise tout de suite n'a pas de suivi.

    Une commande est toujours rangée dans une péniche, qui reste notée après la livraison.
    """
    return queryset.filter(
        Q(statut=Vente.Statut.EN_COMMANDE) | Q(statut=Vente.Statut.LIVREE, peniche__isnull=False)
    )


def etat(vente):
    """Étape où en est la commande : la plus avancée entre les verres et la saisie de l'atelier."""
    if vente.statut == Vente.Statut.LIVREE:
        return LIVREE
    if vente.etape == Etape.INSTANCE:
        return Etape.INSTANCE
    from apps.achats.services import etat_verres

    verres = DEPUIS_LES_VERRES.get(etat_verres(vente), Etape.A_COMMANDER)
    if vente.etape and ORDRE.index(vente.etape) > ORDRE.index(verres):
        return Etape(vente.etape)
    return verres


def type_de_commande(vente):
    familles = {ligne.article.famille for ligne in vente.lignes.all()}
    if "verre" in familles:
        return "verre"
    if "lentille" in familles:
        return "lentille"
    return "autre"


@transaction.atomic
def changer_etape(*, vente, etape, utilisateur, observation=""):
    vente = Vente.tous.select_for_update().get(pk=vente.pk)
    if vente.statut != Vente.Statut.EN_COMMANDE:
        raise EtapeImpossible(f"La commande {vente.numero} n'est plus en cours.")
    if etape not in Etape.values:
        raise EtapeImpossible(f"Étape inconnue : {etape}.")
    vente.etape = etape
    vente.save(update_fields=["etape", "modifie_le"])
    EtapeCommande.objects.create(
        vente=vente, etape=etape, observation=observation[:300], par=utilisateur
    )
    return vente


def journee(ventes, paiements):
    """Totaux d'une journée : ventes du jour et encaissements reçus ce jour-là, par mode."""
    zero = Decimal("0")
    total = sum((v.total_ttc for v in ventes), zero)
    regle = sum((v.regle for v in ventes), zero)
    pris_en_charge = sum((v.pris_en_charge for v in ventes), zero)
    modes = dict(Paiement.Mode.choices)
    par_mode = {}
    for paiement in paiements:
        libelle = modes.get(paiement.mode, paiement.mode)
        par_mode[libelle] = par_mode.get(libelle, zero) + paiement.montant
    return {
        "nombre_ventes": len(ventes),
        "total_ventes": total,
        "regle_sur_ventes": regle,
        "pris_en_charge": pris_en_charge,
        "reste_sur_ventes": total - regle - pris_en_charge,
        "encaisse": sum(par_mode.values(), zero),
        "encaisse_par_mode": [{"mode": m, "montant": v} for m, v in sorted(par_mode.items())],
    }
