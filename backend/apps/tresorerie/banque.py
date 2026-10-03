"""Banque et versements : où va l'argent des clôtures, et son suivi jusqu'au relevé bancaire."""

from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.reseau.models import Societe

from .models import ClotureCaisse, CompteTresorerie, OperationTresorerie
from .services import ClotureImpossible as OperationImpossible

ZERO = Decimal("0")
Type = OperationTresorerie.Type
Statut = OperationTresorerie.Statut
COMPTEES = (Statut.EFFECTUEE, Statut.RAPPROCHEE)

# Pour chaque dépôt : champ de la clôture qui le relie, et montant de la clôture qu'il emporte.
DEPOTS = {
    Type.DEPOT_ESPECES: ("depot_especes", "especes_a_remettre"),
    Type.DEPOT_CHEQUES: ("depot_cheques", "cheques_comptes"),
    Type.ENCAISSEMENT_CARTES: ("encaissement_cartes", "cartes_comptees"),
}


def _montant_reel(operation):
    """Les cartes rapprochées comptent pour ce que la banque a réellement crédité."""
    if operation.montant_credite is not None:
        return operation.montant_credite
    return operation.montant


def soldes(compte):
    """Solde selon OptiLink (opérations effectuées) et solde que la banque doit afficher."""
    comptable = banque = compte.solde_initial
    mouvements = OperationTresorerie.objects.filter(
        Q(source=compte) | Q(destination=compte), statut__in=COMPTEES
    )
    for operation in mouvements:
        montant = _montant_reel(operation)
        signe = 1 if operation.destination_id == compte.pk else -1
        comptable += signe * montant
        if operation.statut == Statut.RAPPROCHEE:
            banque += signe * montant
    return comptable, banque


def clotures_a_remettre(clotures):
    """Clôtures validées dont une partie de l'argent n'est pas encore déposée."""
    validees = clotures.filter(statut=ClotureCaisse.Statut.VALIDEE)
    manquant = Q()
    for champ, _ in DEPOTS.values():
        manquant |= Q(**{f"{champ}__isnull": True})
    resultat = []
    for cloture in validees.filter(manquant).select_related("magasin__societe"):
        restes = {
            type_: getattr(cloture, montant)
            for type_, (champ, montant) in DEPOTS.items()
            if getattr(cloture, f"{champ}_id") is None and getattr(cloture, montant) > 0
        }
        if restes:
            resultat.append((cloture, restes))
    return resultat


def _numero(societe):
    # Suit le dernier numéro et non le nombre d'opérations : une prévision annulée disparaît.
    prefixe = f"{societe.code}-OP{timezone.localdate().year}-"
    dernier = (
        OperationTresorerie.objects.filter(numero__startswith=prefixe)
        .order_by("-numero")
        .values_list("numero", flat=True)
        .first()
    )
    rang = int(dernier.removeprefix(prefixe)) + 1 if dernier else 1
    return f"{prefixe}{rang:06d}"


def _verrouiller(societe):
    return Societe.objects.select_for_update().get(pk=societe.pk)


def _verifier_compte(compte, societe, *types):
    if compte is None:
        return
    if compte.societe_id != societe.pk:
        raise OperationImpossible(f"Le compte {compte} appartient à une autre société.")
    if not compte.est_actif:
        raise OperationImpossible(f"Le compte {compte} est fermé.")
    if types and compte.type not in types:
        raise OperationImpossible(f"Le compte {compte} ne convient pas à cette opération.")


def _verifier_provision(compte, montant):
    """Un coffre ou une caisse centrale ne peut pas donner plus qu'il ne contient."""
    if compte is None or compte.type == CompteTresorerie.Type.BANQUE:
        return
    disponible, _ = soldes(compte)
    if montant > disponible:
        raise OperationImpossible(f"{compte} ne contient que {disponible} : opération impossible.")


def _statut_initial(prevue, reference, destination):
    if prevue:
        return Statut.PREVUE, None
    if destination is not None and destination.type == CompteTresorerie.Type.BANQUE:
        if not reference:
            raise OperationImpossible("Indiquez le n° du bordereau ou de la pièce bancaire.")
    return Statut.EFFECTUEE, timezone.now()


@transaction.atomic
def deposer(type_, clotures, destination, utilisateur, *, prevue=False, reference="", date=None):
    """Dépose l'argent de clôtures validées : espèces au coffre ou en banque, chèques, cartes."""
    champ, champ_montant = DEPOTS[type_]
    clotures = list(ClotureCaisse.tous.select_for_update().filter(pk__in=[c.pk for c in clotures]))
    if not clotures:
        raise OperationImpossible("Choisissez au moins une clôture.")
    societes = {c.magasin.societe_id for c in clotures}
    if len(societes) != 1:
        raise OperationImpossible("Un dépôt ne regroupe que les clôtures d'une même société.")
    societe = _verrouiller(clotures[0].magasin.societe)
    for cloture in clotures:
        if cloture.statut != ClotureCaisse.Statut.VALIDEE:
            raise OperationImpossible(f"La clôture {cloture} n'est pas encore validée.")
        if getattr(cloture, f"{champ}_id") is not None:
            raise OperationImpossible(f"La clôture {cloture} est déjà déposée.")
    banque_seule = () if type_ == Type.DEPOT_ESPECES else (CompteTresorerie.Type.BANQUE,)
    _verifier_compte(destination, societe, *banque_seule)
    statut, effectuee_le = _statut_initial(prevue, reference, destination)
    operation = OperationTresorerie.objects.create(
        societe=societe,
        numero=_numero(societe),
        type=type_,
        statut=statut,
        destination=destination,
        montant=sum((getattr(c, champ_montant) for c in clotures), ZERO),
        date_prevue=date if prevue else None,
        date_operation=None if prevue else (date or timezone.localdate()),
        effectuee_le=effectuee_le,
        reference=reference,
        libelle=", ".join(c.numero for c in clotures),
        cree_par=utilisateur,
    )
    ClotureCaisse.tous.filter(pk__in=[c.pk for c in clotures]).update(**{champ: operation})
    return operation


@transaction.atomic
def enregistrer(
    type_,
    societe,
    utilisateur,
    *,
    montant,
    source=None,
    destination=None,
    magasin=None,
    prevue=False,
    reference="",
    libelle="",
    date=None,
):
    """Transfert entre comptes, alimentation du fond d'une caisse, ou opération bancaire."""
    societe = _verrouiller(societe)
    if montant <= 0:
        raise OperationImpossible("Le montant doit être positif.")
    _verifier_compte(source, societe)
    _verifier_compte(destination, societe)
    if type_ == Type.TRANSFERT:
        if source is None or destination is None or source == destination:
            raise OperationImpossible("Choisissez deux comptes différents.")
        magasin = None
    elif type_ == Type.ALIMENTATION_FOND:
        _verifier_compte(
            source, societe, CompteTresorerie.Type.COFFRE, CompteTresorerie.Type.CAISSE_CENTRALE
        )
        if source is None or magasin is None or magasin.societe_id != societe.pk:
            raise OperationImpossible("Choisissez le coffre et la caisse du magasin à alimenter.")
        destination = None
    elif type_ == Type.OPERATION_BANCAIRE:
        if (source is None) == (destination is None):
            raise OperationImpossible("Une opération bancaire débite ou crédite un seul compte.")
        _verifier_compte(source or destination, societe, CompteTresorerie.Type.BANQUE)
        if not libelle:
            raise OperationImpossible("Dites de quoi il s'agit (frais, agios…).")
        magasin = None
    else:
        raise OperationImpossible("Ce type d'opération se fait à partir des clôtures.")
    statut, effectuee_le = _statut_initial(prevue, reference, destination)
    if statut == Statut.EFFECTUEE:
        _verifier_provision(source, montant)
    return OperationTresorerie.objects.create(
        societe=societe,
        numero=_numero(societe),
        type=type_,
        statut=statut,
        source=source,
        destination=destination,
        magasin=magasin,
        montant=montant,
        date_prevue=date if prevue else None,
        date_operation=None if prevue else (date or timezone.localdate()),
        effectuee_le=effectuee_le,
        reference=reference,
        libelle=libelle,
        cree_par=utilisateur,
    )


@transaction.atomic
def effectuer(operation, reference="", date=None):
    """Une prévision devient réelle : le bordereau est remis à la banque."""
    operation = OperationTresorerie.objects.select_for_update().get(pk=operation.pk)
    if operation.statut != Statut.PREVUE:
        raise OperationImpossible("Cette opération n'est pas une prévision.")
    reference = reference or operation.reference
    _statut_initial(False, reference, operation.destination)
    _verifier_provision(operation.source, operation.montant)
    operation.statut = Statut.EFFECTUEE
    operation.reference = reference
    operation.date_operation = date or timezone.localdate()
    operation.effectuee_le = timezone.now()
    operation.save()
    return operation


@transaction.atomic
def rapprocher(operation, utilisateur, date_valeur, montant_credite=None):
    """La finance retrouve l'opération sur le relevé bancaire."""
    operation = OperationTresorerie.objects.select_for_update().get(pk=operation.pk)
    if operation.statut != Statut.EFFECTUEE:
        raise OperationImpossible("Seule une opération effectuée se rapproche.")
    comptes = [c for c in (operation.source, operation.destination) if c is not None]
    if not any(c.type == CompteTresorerie.Type.BANQUE for c in comptes):
        raise OperationImpossible("Cette opération ne passe pas par la banque.")
    if operation.type == Type.ENCAISSEMENT_CARTES:
        if montant_credite is None:
            raise OperationImpossible("Indiquez le montant crédité par la banque.")
        if not ZERO <= montant_credite <= operation.montant:
            raise OperationImpossible("Le montant crédité dépasse le montant des tickets.")
        operation.montant_credite = montant_credite
    operation.statut = Statut.RAPPROCHEE
    operation.date_valeur = date_valeur
    operation.rapprochee_par = utilisateur
    operation.save()
    return operation


@transaction.atomic
def annuler(operation):
    """Abandonne une prévision ; ses clôtures redeviennent à déposer."""
    operation = OperationTresorerie.objects.select_for_update().get(pk=operation.pk)
    if operation.statut != Statut.PREVUE:
        raise OperationImpossible("Seule une prévision s'annule.")
    for champ, _ in DEPOTS.values():
        ClotureCaisse.tous.filter(**{champ: operation}).update(**{champ: None})
    operation.delete()


def alimentations(magasin, debut, fin):
    """Espèces ajoutées au fond de la caisse du magasin pendant la période."""
    periode = Q(effectuee_le__lte=fin) & (Q(effectuee_le__gt=debut) if debut else Q())
    return (
        OperationTresorerie.objects.filter(
            periode, type=Type.ALIMENTATION_FOND, magasin=magasin, statut__in=COMPTEES
        ).aggregate(total=Sum("montant"))["total"]
        or ZERO
    )
