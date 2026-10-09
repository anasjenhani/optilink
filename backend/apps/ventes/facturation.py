"""Facturation groupée : plusieurs visites ou ventes comptoir sur une facture ; clôture du mois.

À la clôture, les ventes livrées dans le mois et restées sans facture passent sur une facture
récapitulative (« Clients divers »). Le mois est alors figé : plus aucune facture sur ses ventes.
"""

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Exists, OuterRef, Q

from .models import (
    Avoir,
    ClotureMois,
    Facture,
    FactureGroupee,
    Lentilles,
    LigneVente,
    Lunette,
    TypeDocument,
    Vente,
)
from .services import FactureImpossible, _aujourd_hui, _numero, _prochain_numero, arrondir

ZERO = Decimal("0")
CLIENTS_DIVERS = "Clients divers"


def bornes_du_mois(pays, annee, mois):
    """Début du mois et début du suivant, à l'heure du pays."""
    fuseau = ZoneInfo(pays.fuseau_horaire)
    suivant = (annee + 1, 1) if mois == 12 else (annee, mois + 1)
    return datetime(annee, mois, 1, tzinfo=fuseau), datetime(*suivant, 1, tzinfo=fuseau)


def jour_de_vente(vente, pays):
    """Jour où la vente compte : sa livraison (une commande compte quand elle est remise)."""
    moment = vente.livree_le or vente.cree_le
    return moment.astimezone(ZoneInfo(pays.fuseau_horaire)).date()


def verifier_mois_ouvert(vente):
    jour = jour_de_vente(vente, vente.magasin.pays)
    if ClotureMois.tous.filter(magasin=vente.magasin, annee=jour.year, mois=jour.month).exists():
        raise FactureImpossible(
            f"{vente.numero} : le mois {jour.month:02d}/{jour.year} est clôturé, la vente est "
            "sur la facture récapitulative."
        )


def _sans_facture(ventes):
    return ventes.filter(
        statut=Vente.Statut.LIVREE, facture__isnull=True, facture_groupee__isnull=True
    )


def ventes_a_facturer(magasin, *, client=None, du=None, au=None, comptoir=None):
    """Ventes livrées, soldées, sans facture ni avoir, dans un mois encore ouvert.

    ``comptoir`` : True pour les ventes sans lunettes ni lentilles (articles vendus au comptoir),
    False pour les visites (équipement optique), None pour toutes.
    """
    ventes = (
        _sans_facture(Vente.objects.filter(magasin=magasin))
        .exclude(Exists(Avoir.tous.filter(vente=OuterRef("pk"))))
        .select_related("magasin__pays", "client")
        .prefetch_related("paiements", "prises_en_charge")
        .order_by("livree_le", "sequence")
    )
    if client is not None:
        ventes = ventes.filter(client=client)
    if comptoir is not None:
        equipement = Q(Exists(Lunette.objects.filter(vente=OuterRef("pk")))) | Q(
            Exists(Lentilles.objects.filter(vente=OuterRef("pk")))
        )
        ventes = ventes.exclude(equipement) if comptoir else ventes.filter(equipement)
    pays = magasin.pays
    if du:
        ventes = ventes.filter(livree_le__gte=bornes_du_mois(pays, du.year, du.month)[0])
    if au:
        ventes = ventes.filter(livree_le__lt=bornes_du_mois(pays, au.year, au.month)[1])
    clos = set(ClotureMois.tous.filter(magasin=magasin).values_list("annee", "mois"))
    resultat = []
    for vente in ventes:
        jour = jour_de_vente(vente, pays)
        if (du and jour < du) or (au and jour > au) or (jour.year, jour.month) in clos:
            continue
        if vente.reste_a_payer <= 0:
            resultat.append(vente)
    return resultat


def detail_tva(ventes, decimales):
    """Base HT et TVA par taux, nettes des articles repris par avoir.

    Renvoie [{"taux", "total_ht", "total_tva", "total_ttc"}], du taux le plus fort au plus bas.
    """
    par_taux = defaultdict(lambda: [ZERO, ZERO])
    lignes = LigneVente.objects.filter(vente__in=ventes).prefetch_related("retours")
    for ligne in lignes:
        ttc = ligne.total_ttc - sum((r.total_ttc for r in ligne.retours.all()), ZERO)
        if ttc == 0:
            continue
        ht = arrondir(ttc / (1 + ligne.taux_tva / 100), decimales)
        par_taux[ligne.taux_tva][0] += ttc
        par_taux[ligne.taux_tva][1] += ht
    return [
        {"taux": taux, "total_ht": ht, "total_tva": ttc - ht, "total_ttc": ttc}
        for taux, (ttc, ht) in sorted(par_taux.items(), reverse=True)
    ]


def _totaux(detail):
    ht = sum((d["total_ht"] for d in detail), ZERO)
    ttc = sum((d["total_ttc"] for d in detail), ZERO)
    return ht, ttc - ht, ttc


def _emettre(*, magasin, type, ventes, emetteur, detail, jours, timbre=ZERO, **champs):
    pays = magasin.pays
    annee = _aujourd_hui(pays).year
    sequence = _prochain_numero(magasin, annee, TypeDocument.FACTURE)
    total_ht, total_tva, total_ttc = _totaux(detail)
    facture = FactureGroupee.tous.create(
        magasin=magasin,
        type=type,
        numero=_numero(magasin, TypeDocument.FACTURE, annee, sequence),
        annee=annee,
        sequence=sequence,
        du=min(jours),
        au=max(jours),
        devise=pays.devise,
        total_ht=total_ht,
        total_tva=total_tva,
        total_ttc=total_ttc,
        timbre_fiscal=timbre,
        net_a_payer=total_ttc + timbre,
        emise_par=emetteur,
        **champs,
    )
    Vente.tous.filter(pk__in=[v.pk for v in ventes]).update(facture_groupee=facture)
    return facture


@transaction.atomic
def facturer_ensemble(
    *,
    magasin,
    ventes,
    emetteur,
    client=None,
    client_nom="",
    client_adresse="",
    client_matricule_fiscal="",
    mode_paiement_timbre="",
):
    """Une facture pour plusieurs visites ou ventes comptoir soldées d'un même client.

    Sans fiche client (société servie au comptoir), le nom est saisi à la main. Une vente d'un
    autre client ne peut pas y figurer.
    """
    if not ventes:
        raise FactureImpossible("Choisir les ventes à facturer.")
    if client is not None:
        client_nom = client_nom.strip() or client.nom_de_facturation
        client_adresse = client_adresse.strip() or client.adresse_complete
        client_matricule_fiscal = client_matricule_fiscal.strip() or client.matricule_fiscal
    if not client_nom.strip():
        raise FactureImpossible("Indiquer au nom de qui est la facture.")
    pays = magasin.pays
    verrouillees = list(
        Vente.tous.select_for_update(of=("self",))
        .select_related("magasin__pays", "client")
        .filter(pk__in=[v.pk for v in ventes])
        .order_by("livree_le", "sequence")
    )
    for vente in verrouillees:
        if vente.magasin_id != magasin.pk:
            raise FactureImpossible(f"{vente.numero} : vente d'un autre magasin.")
        if vente.statut != Vente.Statut.LIVREE:
            raise FactureImpossible(f"{vente.numero} : la vente n'est pas livrée.")
        if vente.facture_groupee_id or Facture.tous.filter(vente=vente).exists():
            raise FactureImpossible(f"{vente.numero} : la vente est déjà facturée.")
        if Avoir.tous.filter(vente=vente).exists():
            raise FactureImpossible(f"{vente.numero} : la vente a fait l'objet d'un avoir.")
        if vente.client_id and client is not None and vente.client_id != client.pk:
            raise FactureImpossible(f"{vente.numero} : vente d'un autre client.")
        if vente.client_id and client is None:
            raise FactureImpossible(f"{vente.numero} : vente au nom d'un client, choisir sa fiche.")
        reste = vente.reste_a_payer
        if reste > 0:
            raise FactureImpossible(f"{vente.numero} : reste {reste} {vente.devise} à payer.")
        verifier_mois_ouvert(vente)
    timbre = pays.timbre_fiscal
    if timbre > 0 and not mode_paiement_timbre:
        raise FactureImpossible(
            f"Encaisser le timbre fiscal ({timbre} {pays.devise}) : préciser le mode de paiement."
        )
    return _emettre(
        magasin=magasin,
        type=FactureGroupee.Type.CLIENT,
        ventes=verrouillees,
        emetteur=emetteur,
        detail=detail_tva(verrouillees, pays.decimales),
        jours=[jour_de_vente(v, pays) for v in verrouillees],
        timbre=timbre,
        client=client,
        client_nom=client_nom.strip(),
        client_adresse=client_adresse.strip(),
        client_matricule_fiscal=client_matricule_fiscal.strip(),
        mode_paiement_timbre=mode_paiement_timbre if timbre > 0 else "",
    )


def ventes_du_mois(magasin, annee, mois):
    """Ventes livrées dans le mois et restées sans facture : ce que la clôture récapitule."""
    debut, fin = bornes_du_mois(magasin.pays, annee, mois)
    return list(
        _sans_facture(Vente.tous.filter(magasin=magasin))
        .filter(livree_le__gte=debut, livree_le__lt=fin)
        .select_related("client")
        .prefetch_related("paiements", "prises_en_charge", "avoirs")
        .order_by("livree_le", "sequence")
    )


def preparer_cloture(magasin, annee, mois):
    """Ce que fera la clôture : ventes à récapituler, TVA par taux, ventes pas encore soldées."""
    if not 1 <= mois <= 12:
        raise FactureImpossible("Mois invalide.")
    ventes = ventes_du_mois(magasin, annee, mois)
    detail = detail_tva(ventes, magasin.pays.decimales)
    total_ht, total_tva, total_ttc = _totaux(detail)
    cloture = (
        ClotureMois.tous.select_related("facture", "cloture_par")
        .filter(magasin=magasin, annee=annee, mois=mois)
        .first()
    )
    return {
        "annee": annee,
        "mois": mois,
        "cloture": cloture,
        "ventes": ventes,
        "detail_tva": detail,
        "total_ht": total_ht,
        "total_tva": total_tva,
        "total_ttc": total_ttc,
    }


@transaction.atomic
def cloturer_mois(*, magasin, annee, mois, utilisateur):
    """Clôt un mois terminé : facture récapitulative des ventes restées sans facture."""
    if not 1 <= mois <= 12:
        raise FactureImpossible("Mois invalide.")
    pays = magasin.pays
    if _aujourd_hui(pays) < bornes_du_mois(pays, annee, mois)[1].date():
        raise FactureImpossible("Le mois n'est pas terminé : il se clôture à partir du 1er.")
    if ClotureMois.tous.filter(magasin=magasin, annee=annee, mois=mois).exists():
        raise FactureImpossible(f"Le mois {mois:02d}/{annee} est déjà clôturé.")
    # Verrouille les ventes du mois : aucune facture ne peut s'y glisser pendant la clôture.
    debut, fin = bornes_du_mois(pays, annee, mois)
    list(
        Vente.tous.select_for_update(of=("self",)).filter(
            magasin=magasin, livree_le__gte=debut, livree_le__lt=fin
        )
    )
    ventes = ventes_du_mois(magasin, annee, mois)
    detail = detail_tva(ventes, pays.decimales)
    facture = None
    if detail:
        facture = _emettre(
            magasin=magasin,
            type=FactureGroupee.Type.MENSUELLE,
            ventes=ventes,
            emetteur=utilisateur,
            detail=detail,
            jours=[jour_de_vente(v, pays) for v in ventes],
            client_nom=CLIENTS_DIVERS,
        )
    return ClotureMois.tous.create(
        magasin=magasin, annee=annee, mois=mois, facture=facture, cloture_par=utilisateur
    )
