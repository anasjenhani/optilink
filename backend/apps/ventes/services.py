from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.stock.models import MouvementStock, PrixArticle

from .models import (
    PREFIXES,
    Avoir,
    CompteurFacture,
    Devis,
    Facture,
    LigneAvoir,
    LigneDevis,
    LigneVente,
    Paiement,
    TypeDocument,
    Vente,
)


class VenteInvalide(Exception):
    pass


def arrondir(montant, decimales):
    """Arrondi à la plus petite unité de la monnaie (centime, millime…)."""
    return montant.quantize(Decimal(1).scaleb(-decimales), rounding=ROUND_HALF_UP)


def _prochain_numero(magasin, annee, type_document):
    """Réserve le numéro suivant ; le verrou tient jusqu'à la fin de la transaction.

    Si la vente échoue, la transaction annule aussi l'incrément : aucun trou dans la suite.
    """
    cle = {"magasin": magasin, "annee": annee, "type_document": type_document}
    CompteurFacture.objects.get_or_create(**cle)
    compteur = CompteurFacture.objects.select_for_update().get(**cle)
    compteur.dernier += 1
    compteur.save(update_fields=["dernier"])
    return compteur.dernier


def _numero(magasin, type_document, annee, sequence):
    return f"{magasin.code}-{PREFIXES[type_document]}{annee}-{sequence:06d}"


def _aujourd_hui(pays):
    return timezone.localdate(timezone=ZoneInfo(pays.fuseau_horaire))


def _chiffrer(pays, lignes):
    """Prix des lignes dans la monnaie du pays.

    Une ligne peut apporter son prix et son taux figés (``prix_unitaire_ttc``, ``taux_tva``),
    comme celles d'un devis ; sinon le tarif en vigueur du pays s'applique.
    Renvoie [(article, quantite, remise, total_ttc, total_ht, prix, taux, ligne)].
    """
    a_tarifer = {ligne["article"].pk for ligne in lignes if "prix_unitaire_ttc" not in ligne}
    tarifs = {
        prix.article_id: prix
        for prix in PrixArticle.objects.select_related("tva").filter(
            pays=pays, article__in=a_tarifer
        )
    }
    detail = []
    for ligne in lignes:
        article, quantite = ligne["article"], ligne["quantite"]
        if "prix_unitaire_ttc" in ligne:
            prix, taux = ligne["prix_unitaire_ttc"], ligne["taux_tva"]
        else:
            tarif = tarifs.get(article.pk)
            if tarif is None:
                raise VenteInvalide(f"L'article {article.reference} n'a pas de prix en {pays}.")
            prix, taux = tarif.prix_vente_ttc, tarif.tva.taux
        remise = ligne.get("remise_pct") or Decimal("0")
        total_ttc = arrondir(prix * quantite * (1 - remise / 100), pays.decimales)
        total_ht = arrondir(total_ttc / (1 + taux / 100), pays.decimales)
        detail.append((article, quantite, remise, total_ttc, total_ht, prix, taux, ligne))
    return detail


def _stocks(magasin, articles):
    lignes = (
        MouvementStock.tous.filter(magasin=magasin, article__in=articles)
        .values("article_id")
        .annotate(total=Sum("quantite"))
    )
    return {ligne["article_id"]: ligne["total"] for ligne in lignes}


@transaction.atomic
def enregistrer_vente(
    *,
    magasin,
    vendeur,
    lignes,
    paiements,
    client=None,
    commande=False,
    livraison_prevue_le=None,
    articles_retires_admis=False,
):
    """Enregistre une vente : lignes, sortie de stock, paiements et numéro de ticket.

    ``lignes`` : [{"article", "quantite", "remise_pct"}] ; ``paiements`` : [{"mode", "montant"}].
    Remise tout de suite, la vente est payée en totalité. En ``commande``, le client verse un
    acompte (éventuellement nul) et paiera le solde à la livraison (``livrer_commande``) ; une
    vente qui comporte un article sur commande (verres…) est forcément une commande.
    Les articles sur commande ne sortent pas du stock du magasin.
    La facture, elle, se génère à part (``generer_facture``).
    Tout est écrit dans une seule transaction, ou rien.
    """
    if not lignes:
        raise VenteInvalide("La vente ne contient aucun article.")

    quantites = {}
    for ligne in lignes:
        quantites[ligne["article"].pk] = quantites.get(ligne["article"].pk, 0) + ligne["quantite"]
    en_stock = [ligne["article"] for ligne in lignes if not ligne["article"].sur_commande]
    stocks = _stocks(magasin, en_stock)
    for ligne in lignes:
        article = ligne["article"]
        if not article.est_actif and not articles_retires_admis:
            raise VenteInvalide(f"L'article {article.reference} n'est plus vendu.")
        if article.sur_commande:
            if not commande:
                raise VenteInvalide(
                    f"{article.libelle} est commandé au fournisseur : enregistrer une commande."
                )
        elif stocks.get(article.pk, 0) < quantites[article.pk]:
            raise VenteInvalide(f"Stock insuffisant pour {article.reference}.")

    pays = magasin.pays
    detail = _chiffrer(pays, lignes)
    total_ttc = sum((d[3] for d in detail), Decimal("0"))
    total_ht = sum((d[4] for d in detail), Decimal("0"))
    total_paye = sum((arrondir(p["montant"], pays.decimales) for p in paiements), Decimal("0"))
    if commande and total_paye > total_ttc:
        raise VenteInvalide(
            f"L'acompte ({total_paye} {pays.devise}) dépasse le total ({total_ttc} {pays.devise})."
        )
    if not commande and total_paye != total_ttc:
        raise VenteInvalide(
            f"Les paiements ({total_paye} {pays.devise}) ne couvrent pas le total "
            f"({total_ttc} {pays.devise})."
        )

    # L'année du ticket est celle du magasin, pas celle du serveur.
    annee = _aujourd_hui(pays).year
    sequence = _prochain_numero(magasin, annee, TypeDocument.TICKET)
    vente = Vente.tous.create(
        magasin=magasin,
        client=client,
        numero=_numero(magasin, TypeDocument.TICKET, annee, sequence),
        annee=annee,
        sequence=sequence,
        vendeur=vendeur,
        devise=pays.devise,
        total_ht=total_ht,
        total_tva=total_ttc - total_ht,
        total_ttc=total_ttc,
        statut=Vente.Statut.EN_COMMANDE if commande else Vente.Statut.LIVREE,
        livraison_prevue_le=livraison_prevue_le if commande else None,
        livree_le=None if commande else timezone.now(),
        livree_par=None if commande else vendeur,
    )
    LigneVente.objects.bulk_create(
        LigneVente(
            vente=vente,
            article=article,
            libelle=article.libelle,
            quantite=quantite,
            prix_unitaire_ttc=prix,
            remise_pct=remise,
            taux_tva=taux,
            total_ttc=ttc,
        )
        for article, quantite, remise, ttc, _, prix, taux, _ in detail
    )
    MouvementStock.tous.bulk_create(
        MouvementStock(
            magasin=magasin,
            article=article,
            quantite=-quantite,
            type=MouvementStock.Type.VENTE,
            utilisateur=vendeur,
            reference=vente.numero,
        )
        for article, quantite, *_ in detail
        if not article.sur_commande
    )
    _encaisser(vente, paiements, vendeur)
    return vente


def _encaisser(vente, paiements, utilisateur):
    decimales = vente.magasin.pays.decimales
    Paiement.objects.bulk_create(
        Paiement(
            vente=vente,
            mode=p["mode"],
            montant=arrondir(p["montant"], decimales),
            recu_par=utilisateur,
        )
        for p in paiements
        if p["montant"] > 0
    )


def _verrouiller_vente(vente):
    return Vente.tous.select_for_update().select_related("magasin__pays").get(pk=vente.pk)


@transaction.atomic
def regler_commande(*, vente, paiements, utilisateur):
    """Encaisse un règlement sur une vente qui n'est pas soldée (acompte complémentaire, solde)."""
    vente = _verrouiller_vente(vente)
    if vente.statut == Vente.Statut.ANNULEE:
        raise VenteInvalide(f"La vente {vente.numero} est annulée.")
    montant = sum((p["montant"] for p in paiements), Decimal("0"))
    if montant <= 0:
        raise VenteInvalide("Le règlement doit être positif.")
    reste = vente.reste_a_payer
    if arrondir(montant, vente.magasin.pays.decimales) > reste:
        raise VenteInvalide(f"Le règlement dépasse le reste à payer ({reste} {vente.devise}).")
    _encaisser(vente, paiements, utilisateur)
    return vente


@transaction.atomic
def livrer_commande(*, vente, utilisateur, paiements=()):
    """Remet l'équipement au client. Le solde est encaissé au plus tard à ce moment-là."""
    vente = _verrouiller_vente(vente)
    if vente.statut == Vente.Statut.ANNULEE:
        raise VenteInvalide(f"La vente {vente.numero} est annulée.")
    if vente.statut != Vente.Statut.EN_COMMANDE:
        raise VenteInvalide(f"La vente {vente.numero} est déjà livrée.")
    from apps.achats.services import etat_verres

    if etat_verres(vente) not in (None, "recus"):
        raise VenteInvalide(
            f"Les verres de la commande {vente.numero} ne sont pas encore reçus du fournisseur."
        )
    if paiements:
        regler_commande(vente=vente, paiements=paiements, utilisateur=utilisateur)
    reste = vente.reste_a_payer
    if reste > 0:
        raise VenteInvalide(
            f"Le client doit encore {reste} {vente.devise} : encaisser le solde avant la livraison."
        )
    vente.statut = Vente.Statut.LIVREE
    vente.livree_le = timezone.now()
    vente.livree_par = utilisateur
    vente.save(update_fields=["statut", "livree_le", "livree_par", "modifie_le"])
    return vente


class FactureImpossible(Exception):
    pass


@transaction.atomic
def generer_facture(*, vente, client, emetteur, mode_paiement_timbre=""):
    """Émet la facture d'une vente entièrement payée, au nom d'un client.

    Le droit de timbre du pays s'ajoute au net à payer : c'est le client qui le règle, au moment
    de la facture (``mode_paiement_timbre``). Une vente n'a qu'une facture.
    """
    vente = Vente.tous.select_for_update().select_related("magasin__pays").get(pk=vente.pk)
    if Facture.tous.filter(vente=vente).exists():
        raise FactureImpossible(f"La vente {vente.numero} est déjà facturée.")
    if Avoir.tous.filter(vente=vente).exists():
        raise FactureImpossible(
            f"La vente {vente.numero} a fait l'objet d'un avoir : elle ne se facture plus."
        )
    if client is None:
        raise FactureImpossible("Une facture est établie au nom d'un client.")
    reste = vente.reste_a_payer
    if reste > 0:
        raise FactureImpossible(
            f"La commande n'est pas entièrement payée : reste {reste} {vente.devise}."
        )
    pays = vente.magasin.pays
    timbre = pays.timbre_fiscal
    if timbre > 0 and not mode_paiement_timbre:
        raise FactureImpossible(
            f"Encaisser le timbre fiscal ({timbre} {pays.devise}) : préciser le mode de paiement."
        )
    annee = _aujourd_hui(pays).year
    sequence = _prochain_numero(vente.magasin, annee, TypeDocument.FACTURE)
    facture = Facture.tous.create(
        magasin=vente.magasin,
        vente=vente,
        client=client,
        numero=_numero(vente.magasin, TypeDocument.FACTURE, annee, sequence),
        annee=annee,
        sequence=sequence,
        devise=vente.devise,
        total_ht=vente.total_ht,
        total_tva=vente.total_tva,
        total_ttc=vente.total_ttc,
        timbre_fiscal=timbre,
        net_a_payer=vente.total_ttc + timbre,
        mode_paiement_timbre=mode_paiement_timbre if timbre > 0 else "",
        emise_par=emetteur,
    )
    return facture


class DevisImpossible(Exception):
    pass


@transaction.atomic
def etablir_devis(
    *, magasin, auteur, client, lignes, prescription=None, valable_jusqu_au=None, remarques=""
):
    """Établit un devis au tarif du jour, figé jusqu'à sa date de validité.

    ``lignes`` : [{"article", "quantite", "remise_pct", "oeil"}]. Le stock n'est pas vérifié :
    un devis peut porter sur des verres à commander.
    """
    if not lignes:
        raise DevisImpossible("Le devis ne contient aucun article.")
    if client is None:
        raise DevisImpossible("Un devis est établi au nom d'un client.")
    if prescription is not None and prescription.client_id != client.pk:
        raise DevisImpossible("Cette ordonnance appartient à un autre client.")
    for ligne in lignes:
        if not ligne["article"].est_actif:
            raise DevisImpossible(f"L'article {ligne['article'].reference} n'est plus vendu.")
    pays = magasin.pays
    try:
        detail = _chiffrer(pays, lignes)
    except VenteInvalide as erreur:
        raise DevisImpossible(str(erreur)) from erreur
    aujourd_hui = _aujourd_hui(pays)
    if valable_jusqu_au is None:
        valable_jusqu_au = aujourd_hui + timedelta(days=settings.DEVIS_VALIDITE_JOURS)
    if valable_jusqu_au < aujourd_hui:
        raise DevisImpossible("La date de validité est déjà passée.")

    total_ttc = sum((d[3] for d in detail), Decimal("0"))
    total_ht = sum((d[4] for d in detail), Decimal("0"))
    sequence = _prochain_numero(magasin, aujourd_hui.year, TypeDocument.DEVIS)
    devis = Devis.tous.create(
        magasin=magasin,
        numero=_numero(magasin, TypeDocument.DEVIS, aujourd_hui.year, sequence),
        annee=aujourd_hui.year,
        sequence=sequence,
        client=client,
        prescription=prescription,
        etabli_par=auteur,
        devise=pays.devise,
        total_ht=total_ht,
        total_tva=total_ttc - total_ht,
        total_ttc=total_ttc,
        valable_jusqu_au=valable_jusqu_au,
        remarques=remarques,
    )
    LigneDevis.objects.bulk_create(
        LigneDevis(
            devis=devis,
            article=article,
            libelle=article.libelle,
            oeil=ligne.get("oeil", ""),
            quantite=quantite,
            prix_unitaire_ttc=prix,
            remise_pct=remise,
            taux_tva=taux,
            total_ttc=ttc,
        )
        for article, quantite, remise, ttc, _, prix, taux, ligne in detail
    )
    return devis


def _verrouiller(devis):
    devis = Devis.tous.select_for_update().select_related("magasin__pays").get(pk=devis.pk)
    if devis.statut in (Devis.Statut.REFUSE, Devis.Statut.ENCAISSE):
        raise DevisImpossible(
            f"Le devis {devis.numero} est déjà {devis.get_statut_display().lower()}."
        )
    return devis


def _verifier_validite(devis):
    if _aujourd_hui(devis.magasin.pays) > devis.valable_jusqu_au:
        raise DevisImpossible(
            f"Le devis {devis.numero} a expiré le {devis.valable_jusqu_au:%d/%m/%Y} : "
            "établir un nouveau devis."
        )


@transaction.atomic
def accepter_devis(*, devis):
    devis = _verrouiller(devis)
    _verifier_validite(devis)
    devis.statut = Devis.Statut.ACCEPTE
    devis.save(update_fields=["statut", "modifie_le"])
    return devis


@transaction.atomic
def refuser_devis(*, devis):
    devis = _verrouiller(devis)
    devis.statut = Devis.Statut.REFUSE
    devis.save(update_fields=["statut", "modifie_le"])
    return devis


@transaction.atomic
def encaisser_devis(*, devis, vendeur, paiements, commande=False, livraison_prevue_le=None):
    """Encaisse un devis en caisse, au prix du devis : ticket, sortie de stock, paiements.

    Possible tant que le devis est valable, qu'il ait été accepté avant ou non. En
    ``commande``, le client ne verse qu'un acompte (verres à commander, par exemple).
    """
    devis = _verrouiller(devis)
    _verifier_validite(devis)
    lignes = [
        {
            "article": ligne.article,
            "quantite": ligne.quantite,
            "remise_pct": ligne.remise_pct,
            "prix_unitaire_ttc": ligne.prix_unitaire_ttc,
            "taux_tva": ligne.taux_tva,
        }
        for ligne in devis.lignes.select_related("article")
    ]
    try:
        vente = enregistrer_vente(
            magasin=devis.magasin,
            vendeur=vendeur,
            lignes=lignes,
            paiements=paiements,
            client=devis.client,
            commande=commande,
            livraison_prevue_le=livraison_prevue_le,
            articles_retires_admis=True,
        )
    except VenteInvalide as erreur:
        raise DevisImpossible(str(erreur)) from erreur
    devis.vente = vente
    devis.statut = Devis.Statut.ENCAISSE
    devis.save(update_fields=["vente", "statut", "modifie_le"])
    return vente


class AvoirImpossible(Exception):
    pass


def _deja_rendu(vente):
    """Quantités déjà reprises par ligne de vente, et montant déjà remboursé."""
    rendues = {}
    for ligne in LigneAvoir.objects.filter(avoir__vente=vente):
        rendues[ligne.ligne_vente_id] = rendues.get(ligne.ligne_vente_id, 0) + ligne.quantite
    rembourse = sum((a.montant_rembourse for a in Avoir.tous.filter(vente=vente)), Decimal("0"))
    return rendues, rembourse


def _emettre(*, vente, retours, motif, emetteur, mode_remboursement, annulation):
    """``retours`` : [(ligne_vente, quantite, remis_en_stock)]."""
    if not motif.strip():
        raise AvoirImpossible("Préciser le motif de l'avoir.")
    pays = vente.magasin.pays
    rendues, deja_rembourse = _deja_rendu(vente)
    detail = []
    for ligne, quantite, remis_en_stock in retours:
        restante = ligne.quantite - rendues.get(ligne.pk, 0)
        if quantite < 1 or quantite > restante:
            raise AvoirImpossible(f"{ligne.libelle} : {restante} au plus peut encore être repris.")
        if quantite == restante:
            # Le dernier retour d'une ligne prend le solde : pas d'écart d'arrondi cumulé.
            deja = sum((r.total_ttc for r in ligne.retours.all()), Decimal("0"))
            ttc = ligne.total_ttc - deja
        else:
            ttc = arrondir(ligne.total_ttc * quantite / ligne.quantite, pays.decimales)
        ht = arrondir(ttc / (1 + ligne.taux_tva / 100), pays.decimales)
        detail.append((ligne, quantite, remis_en_stock, ttc, ht))
    if not detail:
        raise AvoirImpossible("L'avoir ne reprend aucun article.")

    total_ttc = sum((d[3] for d in detail), Decimal("0"))
    total_ht = sum((d[4] for d in detail), Decimal("0"))
    paye = vente.total_ttc - vente.reste_a_payer
    # On ne rend jamais plus que ce que le client a versé (acomptes d'une commande annulée).
    rembourse = max(Decimal("0"), min(total_ttc, paye - deja_rembourse))
    if rembourse > 0 and not mode_remboursement:
        raise AvoirImpossible(
            f"Rembourser {rembourse} {vente.devise} au client : préciser le mode de remboursement."
        )

    annee = _aujourd_hui(pays).year
    sequence = _prochain_numero(vente.magasin, annee, TypeDocument.AVOIR)
    avoir = Avoir.tous.create(
        magasin=vente.magasin,
        numero=_numero(vente.magasin, TypeDocument.AVOIR, annee, sequence),
        annee=annee,
        sequence=sequence,
        vente=vente,
        facture=Facture.tous.filter(vente=vente).first(),
        client=vente.client,
        annulation=annulation,
        motif=motif.strip(),
        devise=vente.devise,
        total_ht=total_ht,
        total_tva=total_ttc - total_ht,
        total_ttc=total_ttc,
        montant_rembourse=rembourse,
        mode_remboursement=mode_remboursement if rembourse > 0 else "",
        emis_par=emetteur,
    )
    LigneAvoir.objects.bulk_create(
        LigneAvoir(
            avoir=avoir,
            ligne_vente=ligne,
            libelle=ligne.libelle,
            quantite=quantite,
            taux_tva=ligne.taux_tva,
            total_ttc=ttc,
            remis_en_stock=remis_en_stock,
        )
        for ligne, quantite, remis_en_stock, ttc, _ in detail
    )
    MouvementStock.tous.bulk_create(
        MouvementStock(
            magasin=vente.magasin,
            article=ligne.article,
            quantite=quantite,
            type=MouvementStock.Type.RETOUR,
            utilisateur=emetteur,
            reference=avoir.numero,
        )
        for ligne, quantite, remis_en_stock, *_ in detail
        if remis_en_stock and not ligne.article.sur_commande
    )
    # Tout est repris : la vente est annulée.
    rendues_apres = dict(rendues)
    for ligne, quantite, *_ in detail:
        rendues_apres[ligne.pk] = rendues_apres.get(ligne.pk, 0) + quantite
    if all(rendues_apres.get(lv.pk, 0) >= lv.quantite for lv in vente.lignes.all()):
        vente.statut = Vente.Statut.ANNULEE
        vente.save(update_fields=["statut", "modifie_le"])
    return avoir


@transaction.atomic
def emettre_avoir(*, vente, retours, motif, emetteur, mode_remboursement=""):
    """Avoir pour un retour d'articles sur une vente livrée.

    ``retours`` : [{"ligne_vente", "quantite", "remis_en_stock"}]. Les articles remis en stock y
    reviennent (pas ceux faits sur commande) ; le client est remboursé de leur prix.
    """
    vente = _verrouiller_vente(vente)
    if vente.statut == Vente.Statut.EN_COMMANDE:
        raise AvoirImpossible(
            f"La commande {vente.numero} n'est pas livrée : l'annuler plutôt que "
            "reprendre des articles."
        )
    if vente.statut == Vente.Statut.ANNULEE:
        raise AvoirImpossible(f"La vente {vente.numero} est déjà annulée.")
    lignes = {ligne.pk: ligne for ligne in vente.lignes.select_related("article")}
    try:
        demandes = [
            (lignes[r["ligne_vente"]], r["quantite"], r.get("remis_en_stock", True))
            for r in retours
        ]
    except KeyError:
        raise AvoirImpossible("Cette ligne n'appartient pas à la vente.") from None
    return _emettre(
        vente=vente,
        retours=demandes,
        motif=motif,
        emetteur=emetteur,
        mode_remboursement=mode_remboursement,
        annulation=False,
    )


@transaction.atomic
def annuler_vente(*, vente, motif, emetteur, mode_remboursement="", remis_en_stock=True):
    """Annule une vente ou une commande : avoir sur tout ce qui n'a pas encore été repris.

    Une commande non livrée rend son acompte et remet en stock ce qui en était sorti.
    """
    vente = _verrouiller_vente(vente)
    if vente.statut == Vente.Statut.ANNULEE:
        raise AvoirImpossible(f"La vente {vente.numero} est déjà annulée.")
    jamais_livree = vente.statut == Vente.Statut.EN_COMMANDE
    rendues, _ = _deja_rendu(vente)
    demandes = [
        (ligne, ligne.quantite - rendues.get(ligne.pk, 0), remis_en_stock or jamais_livree)
        for ligne in vente.lignes.select_related("article")
        if ligne.quantite > rendues.get(ligne.pk, 0)
    ]
    return _emettre(
        vente=vente,
        retours=demandes,
        motif=motif,
        emetteur=emetteur,
        mode_remboursement=mode_remboursement,
        annulation=True,
    )
