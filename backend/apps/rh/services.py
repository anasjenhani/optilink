"""Présence et congés : solde de congés, demandes et décisions."""

from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import DemandeConge, Employe

ZERO = Decimal("0")
Statut = DemandeConge.Statut


class CongeImpossible(Exception):
    pass


def jours_ouvrables(debut, fin):
    """Jours de congé décomptés : du lundi au samedi, comme les magasins."""
    total = 0
    jour = debut
    while jour <= fin:
        if jour.weekday() != 6:
            total += 1
        jour += timedelta(days=1)
    return Decimal(total)


def mois_travailles(employe, jusquau):
    """Mois complets depuis l'embauche (ou jusqu'à la sortie)."""
    fin = min(jusquau, employe.date_sortie) if employe.date_sortie else jusquau
    debut = employe.date_embauche
    if fin < debut:
        return 0
    mois = (fin.year - debut.year) * 12 + fin.month - debut.month
    if fin.day < debut.day:
        mois -= 1
    return max(mois, 0)


def solde(employe, jusquau=None):
    """Congé annuel : acquis, pris, en attente de décision et encore disponible."""
    jusquau = jusquau or timezone.localdate()
    acquis = employe.solde_conges_initial + employe.conges_par_mois * mois_travailles(
        employe, jusquau
    )
    annuels = DemandeConge.tous.filter(employe=employe, type=DemandeConge.Type.ANNUEL)

    def total(statut):
        return annuels.filter(statut=statut).aggregate(t=Sum("jours"))["t"] or ZERO

    pris, en_attente = total(Statut.ACCEPTEE), total(Statut.DEMANDEE)
    return {
        "acquis": acquis,
        "pris": pris,
        "en_attente": en_attente,
        "disponible": acquis - pris - en_attente,
    }


def _verifier_periode(employe, debut, fin, exclure=None):
    if fin < debut:
        raise CongeImpossible("La date de fin précède la date de début.")
    if debut < employe.date_embauche:
        raise CongeImpossible("Le congé commence avant l'embauche.")
    chevauchement = DemandeConge.tous.filter(
        employe=employe,
        statut__in=[Statut.DEMANDEE, Statut.ACCEPTEE],
        debut__lte=fin,
        fin__gte=debut,
    )
    if exclure is not None:
        chevauchement = chevauchement.exclude(pk=exclure.pk)
    if chevauchement.exists():
        raise CongeImpossible("Un autre congé couvre déjà une partie de ces dates.")


@transaction.atomic
def demander(employe, utilisateur, type_, debut, fin, motif=""):
    employe = Employe.tous.select_for_update().get(pk=employe.pk)
    if employe.date_sortie and fin > employe.date_sortie:
        raise CongeImpossible("L'employé a quitté l'entreprise à cette date.")
    _verifier_periode(employe, debut, fin)
    jours = jours_ouvrables(debut, fin)
    if jours == 0:
        raise CongeImpossible("Ces dates ne comptent aucun jour ouvrable.")
    if type_ == DemandeConge.Type.ANNUEL:
        disponible = solde(employe)["disponible"]
        if jours > disponible:
            raise CongeImpossible(
                f"Solde insuffisant : {disponible} jour(s) disponible(s) pour {jours} demandé(s)."
            )
    return DemandeConge.tous.create(
        employe=employe,
        magasin_id=employe.magasin_id,
        type=type_,
        debut=debut,
        fin=fin,
        jours=jours,
        motif=motif,
        demandee_par=utilisateur,
    )


@transaction.atomic
def decider(demande, utilisateur, accepter, commentaire=""):
    demande = DemandeConge.tous.select_for_update().select_related("employe").get(pk=demande.pk)
    if demande.statut != Statut.DEMANDEE:
        raise CongeImpossible("Cette demande a déjà reçu une réponse.")
    if demande.employe.utilisateur_id == utilisateur.pk:
        raise CongeImpossible("Un responsable ne décide pas de ses propres congés.")
    if not accepter and not commentaire.strip():
        raise CongeImpossible("Dites à l'employé pourquoi la demande est refusée.")
    demande.statut = Statut.ACCEPTEE if accepter else Statut.REFUSEE
    demande.decidee_par = utilisateur
    demande.decidee_le = timezone.now()
    demande.commentaire_decision = commentaire.strip()
    demande.save()
    return demande


@transaction.atomic
def annuler(demande, aujourd_hui=None):
    """Retire une demande en attente, ou un congé accepté qui n'a pas commencé."""
    demande = DemandeConge.tous.select_for_update().get(pk=demande.pk)
    aujourd_hui = aujourd_hui or timezone.localdate()
    if demande.statut == Statut.ACCEPTEE and demande.debut <= aujourd_hui:
        raise CongeImpossible("Ce congé a déjà commencé : il ne s'annule plus.")
    if demande.statut not in (Statut.DEMANDEE, Statut.ACCEPTEE):
        raise CongeImpossible("Cette demande n'est plus active.")
    demande.statut = Statut.ANNULEE
    demande.save()
    return demande


def en_conge(employes, jour: date):
    """Congés acceptés qui couvrent ce jour, par employé."""
    return {
        c.employe_id: c
        for c in DemandeConge.tous.filter(
            employe__in=employes, statut=Statut.ACCEPTEE, debut__lte=jour, fin__gte=jour
        )
    }
