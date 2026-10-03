"""Acomptes et primes : ce que la paie du mois retiendra ou ajoutera."""

from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import Acompte, Employe, Prime

ZERO = Decimal("0")
EN_COURS = (Acompte.Statut.DEMANDE, Acompte.Statut.ACCORDE, Acompte.Statut.VERSE)
A_RETENIR = (Acompte.Statut.ACCORDE, Acompte.Statut.VERSE)


class OperationImpossible(Exception):
    pass


def premier_du_mois(jour):
    return jour.replace(day=1)


def plafond_acomptes(employe):
    """Part du salaire de base qu'on peut avancer dans un mois ; ``None`` sans salaire saisi."""
    if employe.salaire_base is None:
        return None
    return (employe.salaire_base * settings.ACOMPTE_PLAFOND_POURCENT / 100).quantize(
        Decimal("0.001")
    )


def acomptes_du_mois(employe, mois, statuts=EN_COURS):
    return (
        Acompte.tous.filter(employe=employe, mois=mois, statut__in=statuts).aggregate(
            t=Sum("montant")
        )["t"]
        or ZERO
    )


def _verifier_mois(mois):
    if mois < premier_du_mois(timezone.localdate()):
        raise OperationImpossible("La paie de ce mois est passée.")


@transaction.atomic
def demander_acompte(employe, utilisateur, montant, mois=None, motif=""):
    employe = Employe.tous.select_for_update().get(pk=employe.pk)
    mois = premier_du_mois(mois or timezone.localdate())
    _verifier_mois(mois)
    if montant <= 0:
        raise OperationImpossible("Le montant doit être positif.")
    if employe.date_sortie:
        raise OperationImpossible("Cet employé a quitté l'entreprise.")
    plafond = plafond_acomptes(employe)
    if plafond is not None:
        reste = plafond - acomptes_du_mois(employe, mois)
        if montant > reste:
            raise OperationImpossible(
                f"Plafond dépassé : il reste {reste} d'acompte possible sur ce mois "
                f"({settings.ACOMPTE_PLAFOND_POURCENT} % du salaire de base)."
            )
    return Acompte.tous.create(
        employe=employe,
        magasin_id=employe.magasin_id,
        montant=montant,
        mois=mois,
        motif=motif,
        demande_par=utilisateur,
    )


def _pas_soi_meme(employe, utilisateur, quoi):
    if employe.utilisateur_id == utilisateur.pk:
        raise OperationImpossible(f"On ne décide pas de {quoi} pour soi-même.")


@transaction.atomic
def decider_acompte(acompte, utilisateur, accorder, commentaire=""):
    acompte = Acompte.tous.select_for_update().select_related("employe").get(pk=acompte.pk)
    if acompte.statut != Acompte.Statut.DEMANDE:
        raise OperationImpossible("Cette demande a déjà reçu une réponse.")
    _pas_soi_meme(acompte.employe, utilisateur, "son acompte")
    if not accorder and not commentaire.strip():
        raise OperationImpossible("Dites à l'employé pourquoi l'acompte est refusé.")
    acompte.statut = Acompte.Statut.ACCORDE if accorder else Acompte.Statut.REFUSE
    acompte.decide_par = utilisateur
    acompte.decide_le = timezone.now()
    acompte.commentaire_decision = commentaire.strip()
    acompte.save()
    return acompte


@transaction.atomic
def verser_acompte(acompte, mode, reference="", date=None):
    acompte = Acompte.tous.select_for_update().get(pk=acompte.pk)
    if acompte.statut != Acompte.Statut.ACCORDE:
        raise OperationImpossible("Seul un acompte accordé se verse.")
    if mode != Acompte.Mode.ESPECES and not reference:
        raise OperationImpossible("Indiquez le n° du virement ou du chèque.")
    acompte.statut = Acompte.Statut.VERSE
    acompte.mode_versement = mode
    acompte.reference_versement = reference
    acompte.verse_le = date or timezone.localdate()
    acompte.save()
    return acompte


@transaction.atomic
def annuler_acompte(acompte):
    acompte = Acompte.tous.select_for_update().get(pk=acompte.pk)
    if acompte.statut not in (Acompte.Statut.DEMANDE, Acompte.Statut.ACCORDE):
        raise OperationImpossible("Un acompte versé ou refusé ne s'annule plus.")
    acompte.statut = Acompte.Statut.ANNULE
    acompte.save()
    return acompte


@transaction.atomic
def proposer_prime(employe, utilisateur, type_, montant, mois, motif=""):
    mois = premier_du_mois(mois)
    _verifier_mois(mois)
    if montant <= 0:
        raise OperationImpossible("Le montant doit être positif.")
    if employe.utilisateur_id == utilisateur.pk:
        raise OperationImpossible("On ne se propose pas une prime à soi-même.")
    return Prime.tous.create(
        employe=employe,
        magasin_id=employe.magasin_id,
        type=type_,
        montant=montant,
        mois=mois,
        motif=motif,
        proposee_par=utilisateur,
    )


@transaction.atomic
def decider_prime(prime, utilisateur, valider, commentaire=""):
    prime = Prime.tous.select_for_update().select_related("employe").get(pk=prime.pk)
    if prime.statut != Prime.Statut.PROPOSEE:
        raise OperationImpossible("Cette prime a déjà reçu une réponse.")
    _pas_soi_meme(prime.employe, utilisateur, "sa prime")
    if not valider and not commentaire.strip():
        raise OperationImpossible("Dites pourquoi la prime est refusée.")
    prime.statut = Prime.Statut.VALIDEE if valider else Prime.Statut.REFUSEE
    prime.validee_par = utilisateur
    prime.validee_le = timezone.now()
    prime.commentaire_decision = commentaire.strip()
    prime.save()
    return prime


@transaction.atomic
def annuler_prime(prime):
    prime = Prime.tous.select_for_update().get(pk=prime.pk)
    if prime.statut != Prime.Statut.PROPOSEE:
        raise OperationImpossible("Seule une prime en attente s'annule.")
    prime.statut = Prime.Statut.ANNULEE
    prime.save()
    return prime


def recapitulatif(employes, mois):
    """Pour la paie du mois : acomptes à retenir et primes à verser, par employé."""
    acomptes = dict(
        Acompte.tous.filter(employe__in=employes, mois=mois, statut__in=A_RETENIR)
        .values_list("employe")
        .annotate(t=Sum("montant"))
    )
    primes = dict(
        Prime.tous.filter(employe__in=employes, mois=mois, statut=Prime.Statut.VALIDEE)
        .values_list("employe")
        .annotate(t=Sum("montant"))
    )
    return [
        {
            "employe": e,
            "salaire_base": e.salaire_base,
            "acomptes": acomptes.get(e.pk, ZERO),
            "primes": primes.get(e.pk, ZERO),
        }
        for e in employes
    ]
