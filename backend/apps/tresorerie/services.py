"""Clôture de caisse : ce qu'OptiLink attend dans la caisse, et la vérification par la finance."""

from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.reseau.models import Magasin
from apps.ventes.models import Avoir, Paiement

from .models import ClotureCaisse, DepenseCaisse

ZERO = Decimal("0")
ESPECES, CHEQUE, CARTE = Paiement.Mode.ESPECES, Paiement.Mode.CHEQUE, Paiement.Mode.CARTE


class ClotureImpossible(Exception):
    pass


def derniere_cloture(magasin):
    return ClotureCaisse.tous.filter(magasin=magasin).order_by("-fin").first()


def situation(magasin, fin=None):
    """Montants attendus depuis la dernière clôture du magasin jusqu'à ``fin`` (maintenant)."""
    fin = fin or timezone.now()
    precedente = derniere_cloture(magasin)
    debut = precedente.fin if precedente else None

    periode = Q(recu_le__lte=fin) & (Q(recu_le__gt=debut) if debut else Q())
    paiements = Paiement.objects.filter(periode, vente__magasin=magasin)
    par_mode = {
        ligne["mode"]: ligne
        for ligne in paiements.values("mode").annotate(total=Sum("montant"), nombre=Count("id"))
    }

    def encaisse(mode):
        return par_mode.get(mode, {}).get("total") or ZERO

    avoirs = Avoir.tous.filter(magasin=magasin, cree_le__lte=fin)
    if debut:
        avoirs = avoirs.filter(cree_le__gt=debut)
    rembourse = dict(
        avoirs.values_list("mode_remboursement").annotate(total=Sum("montant_rembourse"))
    )
    depenses = DepenseCaisse.tous.filter(magasin=magasin, cloture__isnull=True, payee_le__lte=fin)

    return {
        "debut": debut,
        "fin": fin,
        "devise": magasin.pays.devise,
        "fond_initial": precedente.fond_conserve if precedente else ZERO,
        "encaisse_especes": encaisse(ESPECES),
        "encaisse_cheques": encaisse(CHEQUE),
        "nombre_cheques": par_mode.get(CHEQUE, {}).get("nombre", 0),
        "encaisse_cartes": encaisse(CARTE),
        "rembourse_especes": rembourse.get(ESPECES) or ZERO,
        "rembourse_cheques": rembourse.get(CHEQUE) or ZERO,
        "rembourse_cartes": rembourse.get(CARTE) or ZERO,
        "depenses": depenses.aggregate(total=Sum("montant"))["total"] or ZERO,
    }


@transaction.atomic
def cloturer(magasin, utilisateur, comptage):
    """Clôture la caisse : fige la période, rattache ses dépenses et l'envoie à la finance."""
    # Un seul caissier à la fois : la clôture suivante attend la fin de celle-ci.
    magasin = Magasin.tous.select_for_update().select_related("pays").get(pk=magasin.pk)
    if ClotureCaisse.tous.filter(magasin=magasin, statut=ClotureCaisse.Statut.REJETEE).exists():
        raise ClotureImpossible(
            "Une clôture rejetée par la finance attend votre correction avant la suivante."
        )
    attendu = situation(magasin)
    if comptage["fond_conserve"] > comptage["especes_comptees"]:
        raise ClotureImpossible("Le fond laissé en caisse dépasse les espèces comptées.")
    annee = attendu["fin"].year
    rang = ClotureCaisse.tous.filter(magasin=magasin, fin__year=annee).count() + 1
    cloture = ClotureCaisse.objects.create(
        magasin=magasin,
        numero=f"{magasin.code}-CL{annee}-{rang:06d}",
        cloturee_par=utilisateur,
        **attendu,
        **comptage,
    )
    DepenseCaisse.tous.filter(
        magasin=magasin, cloture__isnull=True, payee_le__lte=attendu["fin"]
    ).update(cloture=cloture)
    return cloture


@transaction.atomic
def corriger(cloture, utilisateur, comptage):
    """Après un rejet : nouveau comptage, et la clôture repart vers la finance."""
    cloture = ClotureCaisse.objects.select_for_update().get(pk=cloture.pk)
    if cloture.statut != ClotureCaisse.Statut.REJETEE:
        raise ClotureImpossible("Seule une clôture rejetée se corrige.")
    if comptage["fond_conserve"] > comptage["especes_comptees"]:
        raise ClotureImpossible("Le fond laissé en caisse dépasse les espèces comptées.")
    for champ, valeur in comptage.items():
        setattr(cloture, champ, valeur)
    cloture.statut = ClotureCaisse.Statut.ENVOYEE
    cloture.cloturee_par = utilisateur
    cloture.save()
    return cloture


@transaction.atomic
def verifier(cloture, utilisateur, valider, commentaire=""):
    """La finance valide la clôture, ou la rejette en disant pourquoi."""
    cloture = ClotureCaisse.objects.select_for_update().get(pk=cloture.pk)
    if cloture.statut != ClotureCaisse.Statut.ENVOYEE:
        raise ClotureImpossible("Cette clôture n'attend pas de vérification.")
    if cloture.cloturee_par_id == utilisateur.pk:
        raise ClotureImpossible("Une clôture se vérifie par une autre personne que son auteur.")
    if not valider and not commentaire.strip():
        raise ClotureImpossible("Dites au caissier ce qui ne va pas.")
    cloture.statut = ClotureCaisse.Statut.VALIDEE if valider else ClotureCaisse.Statut.REJETEE
    cloture.verifiee_par = utilisateur
    cloture.verifiee_le = timezone.now()
    cloture.commentaire_finance = commentaire.strip()
    cloture.save()
    return cloture
