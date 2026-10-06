import uuid

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.reseau.models import Magasin, Societe
from apps.securite.corbeille import mettre_a_la_corbeille

from .. import banque, services
from ..models import ClotureCaisse, CompteTresorerie, DepenseCaisse, OperationTresorerie
from .serializers import (
    ARemettreSerializer,
    ClotureSaisieSerializer,
    ClotureSerializer,
    ComptageSerializer,
    CompteSerializer,
    DepenseSerializer,
    DepotSerializer,
    EffectuerSerializer,
    OperationSaisieSerializer,
    OperationSerializer,
    RapprocherSerializer,
    SituationSerializer,
    VerificationSerializer,
)


def magasin_autorise(request, public_id, permission):
    try:
        public_id = uuid.UUID(str(public_id))
    except ValueError as erreur:
        raise ValidationError({"magasin": "Identifiant de magasin invalide."}) from erreur
    magasin = get_object_or_404(Magasin.objects.select_related("pays"), public_id=public_id)
    if not request.user.has_perm(permission, magasin):
        raise PermissionDenied("Vous n'avez pas ce droit dans ce magasin.")
    return magasin


def _executer(fonction, *args, **kwargs):
    try:
        return fonction(*args, **kwargs)
    except services.ClotureImpossible as erreur:
        raise ValidationError({"detail": str(erreur)}) from erreur


class ClotureViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Clôtures de caisse : le caissier clôture, la finance vérifie."""

    serializer_class = ClotureSerializer
    lookup_field = "public_id"
    filterset_fields = ["statut", "magasin__public_id"]
    permissions_requises = {
        "list": "tresorerie.view_cloturecaisse",
        "retrieve": "tresorerie.view_cloturecaisse",
        "situation": "tresorerie.add_cloturecaisse",
        "create": "tresorerie.add_cloturecaisse",
        "corriger": "tresorerie.add_cloturecaisse",
        "valider": "tresorerie.valider_cloturecaisse",
        "rejeter": "tresorerie.valider_cloturecaisse",
    }

    def get_queryset(self):
        return ClotureCaisse.objects.select_related("magasin", "cloturee_par", "verifiee_par")

    @extend_schema(
        parameters=[OpenApiParameter("magasin", OpenApiTypes.UUID, required=True)],
        responses=SituationSerializer,
    )
    @action(detail=False)
    def situation(self, request):
        """Ce qui doit se trouver dans la caisse maintenant, avant comptage."""
        magasin = magasin_autorise(
            request, request.query_params.get("magasin"), "tresorerie.add_cloturecaisse"
        )
        attendu = services.situation(magasin)
        rejetee = ClotureCaisse.objects.filter(
            magasin=magasin, statut=ClotureCaisse.Statut.REJETEE
        ).first()
        provisoire = ClotureCaisse(**attendu)
        return Response(
            SituationSerializer(
                attendu
                | {
                    "especes_attendues": provisoire.especes_attendues,
                    "cheques_attendus": provisoire.cheques_attendus,
                    "cartes_attendues": provisoire.cartes_attendues,
                    "cloture_rejetee": rejetee.public_id if rejetee else None,
                }
            ).data
        )

    @extend_schema(request=ClotureSaisieSerializer, responses={201: ClotureSerializer})
    def create(self, request):
        saisie = ClotureSaisieSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        donnees = dict(saisie.validated_data)
        magasin = magasin_autorise(request, donnees.pop("magasin"), "tresorerie.add_cloturecaisse")
        cloture = _executer(services.cloturer, magasin, request.user, donnees)
        return Response(ClotureSerializer(cloture).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=ComptageSerializer, responses=ClotureSerializer)
    @action(detail=True, methods=["post"])
    def corriger(self, request, public_id=None):
        """Nouveau comptage après un rejet ; la clôture repart vers la finance."""
        cloture = self.get_object()
        if not request.user.has_perm("tresorerie.add_cloturecaisse", cloture.magasin):
            raise PermissionDenied("Vous n'avez pas ce droit dans ce magasin.")
        saisie = ComptageSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        cloture = _executer(services.corriger, cloture, request.user, saisie.validated_data)
        return Response(ClotureSerializer(cloture).data)

    def _verifier(self, request, valider):
        cloture = self.get_object()
        if not request.user.has_perm("tresorerie.valider_cloturecaisse", cloture.magasin):
            raise PermissionDenied("Vous n'avez pas ce droit dans ce magasin.")
        saisie = VerificationSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        cloture = _executer(
            services.verifier, cloture, request.user, valider, saisie.validated_data["commentaire"]
        )
        return Response(ClotureSerializer(cloture).data)

    @extend_schema(request=VerificationSerializer, responses=ClotureSerializer)
    @action(detail=True, methods=["post"])
    def valider(self, request, public_id=None):
        return self._verifier(request, valider=True)

    @extend_schema(request=VerificationSerializer, responses=ClotureSerializer)
    @action(detail=True, methods=["post"])
    def rejeter(self, request, public_id=None):
        return self._verifier(request, valider=False)


class DepenseViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Dépenses payées en espèces depuis la caisse du magasin.

    Une dépense se corrige ou se supprime tant que la caisse n'est pas clôturée ; ensuite elle
    fait partie de la clôture (pièce comptable).
    """

    serializer_class = DepenseSerializer
    lookup_field = "public_id"
    http_method_names = ["get", "post", "patch", "delete"]
    filterset_fields = {"magasin__public_id": ["exact"], "cloture": ["isnull"]}
    permissions_requises = {
        "list": "tresorerie.view_depensecaisse",
        "create": "tresorerie.add_depensecaisse",
        "partial_update": "tresorerie.add_depensecaisse",
        "destroy": "tresorerie.add_depensecaisse",
    }

    def get_queryset(self):
        return DepenseCaisse.objects.select_related("magasin", "saisie_par", "cloture")

    def perform_create(self, serializer):
        magasin = magasin_autorise(
            self.request,
            serializer.validated_data.pop("magasin_id"),
            "tresorerie.add_depensecaisse",
        )
        serializer.save(magasin=magasin, saisie_par=self.request.user, payee_le=timezone.now())

    def get_object(self):
        depense = super().get_object()
        if depense.cloture_id:
            raise ValidationError(
                {"detail": f"Dépense déjà comprise dans la clôture {depense.cloture.numero}."}
            )
        return depense

    def perform_destroy(self, depense):
        mettre_a_la_corbeille(depense, auteur=self.request.user)

    def perform_update(self, serializer):
        # Le magasin d'une dépense ne change pas.
        serializer.validated_data.pop("magasin_id", None)
        serializer.save()


def societes_couvertes(utilisateur, permission):
    """Sociétés où l'utilisateur a ce droit pour toute la société ; ``None`` = toutes."""
    if utilisateur.is_superuser:
        return None
    app, code = permission.split(".")
    affectations = utilisateur.affectations_actives().filter(
        role__permissions__codename=code, role__permissions__content_type__app_label=app
    )
    if affectations.filter(portee="reseau").exists():
        return None
    return set(affectations.filter(portee="societe").values_list("societe_id", flat=True))


def couvre(ensemble, societe_id):
    return ensemble is None or societe_id in ensemble


def magasins_couverts(utilisateur, permission):
    return {m.pk for m in Magasin.tous.all() if utilisateur.has_perm(permission, m)}


def _banque(fonction, *args, **kwargs):
    try:
        return fonction(*args, **kwargs)
    except banque.OperationImpossible as erreur:
        raise ValidationError({"detail": str(erreur)}) from erreur


class CompteViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Comptes bancaires, coffres et caisses centrales, avec leurs soldes.

    La finance de la société voit tout. Un responsable de magasin voit les comptes bancaires
    de sa société et le coffre de son magasin, pour y déposer l'argent, mais pas leurs soldes.
    """

    serializer_class = CompteSerializer
    lookup_field = "public_id"
    pagination_class = None
    http_method_names = ["get", "post", "patch"]
    filterset_fields = ["type", "est_actif", "societe__public_id"]
    permissions_requises = {
        "list": "tresorerie.view_comptetresorerie",
        "create": "tresorerie.add_comptetresorerie",
        "partial_update": "tresorerie.change_comptetresorerie",
    }

    def get_queryset(self):
        comptes = CompteTresorerie.objects.select_related("societe", "magasin")
        if getattr(self, "swagger_fake_view", False):
            return comptes
        vue = "tresorerie.view_comptetresorerie"
        societes = societes_couvertes(self.request.user, vue)
        if societes is None:
            return comptes
        magasins = magasins_couverts(self.request.user, vue)
        societes_magasins = Magasin.tous.filter(pk__in=magasins).values("societe_id")
        return comptes.filter(
            Q(societe_id__in=societes)
            | Q(type=CompteTresorerie.Type.BANQUE, societe_id__in=societes_magasins)
            | Q(type=CompteTresorerie.Type.COFFRE, magasin_id__in=magasins)
        )

    def get_serializer_context(self):
        contexte = super().get_serializer_context()
        if not getattr(self, "swagger_fake_view", False):
            contexte["soldes_visibles"] = societes_couvertes(
                self.request.user, "tresorerie.view_comptetresorerie"
            )
        return contexte

    def _verifier_societe(self, societe_id):
        gerer = societes_couvertes(self.request.user, "tresorerie.add_comptetresorerie")
        if not couvre(gerer, societe_id):
            raise PermissionDenied("Vous ne gérez pas les comptes de cette société.")

    def perform_create(self, serializer):
        self._verifier_societe(serializer.validated_data["societe"].pk)
        serializer.save()

    def perform_update(self, serializer):
        self._verifier_societe(serializer.instance.societe_id)
        if serializer.validated_data.get("societe", serializer.instance.societe) != (
            serializer.instance.societe
        ):
            raise ValidationError({"societe": "Un compte ne change pas de société."})
        serializer.save()


class OperationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Dépôts des clôtures, versements, transferts, alimentations du fond, rapprochement."""

    serializer_class = OperationSerializer
    lookup_field = "public_id"
    filterset_fields = ["statut", "type", "societe__public_id"]
    permissions_requises = {
        "list": "tresorerie.view_operationtresorerie",
        "retrieve": "tresorerie.view_operationtresorerie",
        "a_remettre": "tresorerie.add_operationtresorerie",
        "deposer": "tresorerie.add_operationtresorerie",
        "create": "tresorerie.add_operationtresorerie",
        "effectuer": "tresorerie.add_operationtresorerie",
        "annuler": "tresorerie.add_operationtresorerie",
        "rapprocher": "tresorerie.rapprocher_operationtresorerie",
    }

    def get_queryset(self):
        operations = OperationTresorerie.objects.select_related(
            "societe", "source", "destination", "magasin", "cree_par", "rapprochee_par"
        )
        if getattr(self, "swagger_fake_view", False):
            return operations
        vue = "tresorerie.view_operationtresorerie"
        societes = societes_couvertes(self.request.user, vue)
        if societes is None:
            return operations
        # Hors finance de la société : seulement ce qui touche ses magasins.
        magasins = magasins_couverts(self.request.user, vue)
        return operations.filter(
            Q(societe_id__in=societes)
            | Q(magasin_id__in=magasins)
            | Q(clotures_especes__magasin_id__in=magasins)
            | Q(clotures_cheques__magasin_id__in=magasins)
            | Q(clotures_cartes__magasin_id__in=magasins)
        ).distinct()

    def _compte(self, public_id):
        if public_id is None:
            return None
        compte = CompteTresorerie.objects.filter(public_id=public_id).first()
        if compte is None:
            raise ValidationError({"detail": "Compte introuvable."})
        return compte

    def _exiger_societe(self, permission, societe_id):
        if not couvre(societes_couvertes(self.request.user, permission), societe_id):
            raise PermissionDenied("Ce droit vous est donné pour un magasin, pas la société.")

    @extend_schema(responses=ARemettreSerializer(many=True))
    @action(detail=False, url_path="a-remettre", pagination_class=None)
    def a_remettre(self, request):
        """Clôtures validées dont l'argent n'est pas encore déposé."""
        magasins = magasins_couverts(request.user, "tresorerie.add_operationtresorerie")
        clotures = ClotureCaisse.objects.filter(magasin_id__in=magasins).order_by("fin")
        lignes = []
        for cloture, restes in banque.clotures_a_remettre(clotures):
            cheques = restes.get(OperationTresorerie.Type.DEPOT_CHEQUES)
            lignes.append(
                {
                    "cloture": cloture,
                    "especes": restes.get(OperationTresorerie.Type.DEPOT_ESPECES),
                    "cheques": cheques,
                    "nombre_cheques": cloture.nombre_cheques_comptes if cheques else None,
                    "cartes": restes.get(OperationTresorerie.Type.ENCAISSEMENT_CARTES),
                }
            )
        return Response(ARemettreSerializer(lignes, many=True).data)

    @extend_schema(request=DepotSerializer, responses={201: OperationSerializer})
    @action(detail=False, methods=["post"])
    def deposer(self, request):
        """Dépose l'argent d'une ou plusieurs clôtures validées : coffre ou banque."""
        saisie = DepotSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        d = saisie.validated_data
        clotures = list(
            ClotureCaisse.objects.filter(public_id__in=d["clotures"]).select_related("magasin")
        )
        if len(clotures) != len(set(d["clotures"])):
            raise ValidationError({"clotures": "Clôture introuvable."})
        for cloture in clotures:
            if not request.user.has_perm("tresorerie.add_operationtresorerie", cloture.magasin):
                raise PermissionDenied(f"Vous ne déposez pas l'argent de {cloture.magasin}.")
        operation = _banque(
            banque.deposer,
            d["type"],
            clotures,
            self._compte(d["destination"]),
            request.user,
            prevue=d["prevue"],
            reference=d["reference"],
            date=d["date"],
        )
        return Response(OperationSerializer(operation).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=OperationSaisieSerializer, responses={201: OperationSerializer})
    def create(self, request):
        """Transfert entre comptes, alimentation du fond d'une caisse, opération bancaire."""
        saisie = OperationSaisieSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        d = saisie.validated_data
        societe = Societe.objects.filter(public_id=d["societe"]).first()
        if societe is None:
            raise ValidationError({"societe": "Société introuvable."})
        self._exiger_societe("tresorerie.add_operationtresorerie", societe.pk)
        magasin = None
        if d["magasin"] is not None:
            magasin = Magasin.tous.filter(public_id=d["magasin"]).first()
            if magasin is None:
                raise ValidationError({"magasin": "Magasin introuvable."})
        operation = _banque(
            banque.enregistrer,
            d["type"],
            societe,
            request.user,
            montant=d["montant"],
            source=self._compte(d["source"]),
            destination=self._compte(d["destination"]),
            magasin=magasin,
            prevue=d["prevue"],
            reference=d["reference"],
            libelle=d["libelle"],
            date=d["date"],
        )
        return Response(OperationSerializer(operation).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=EffectuerSerializer, responses=OperationSerializer)
    @action(detail=True, methods=["post"])
    def effectuer(self, request, public_id=None):
        """La prévision est faite : le bordereau est remis à la banque."""
        operation = self.get_object()
        saisie = EffectuerSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        operation = _banque(banque.effectuer, operation, **saisie.validated_data)
        return Response(OperationSerializer(operation).data)

    @extend_schema(request=None, responses={204: None})
    @action(detail=True, methods=["post"])
    def annuler(self, request, public_id=None):
        """Abandonne une prévision ; ses clôtures redeviennent à déposer."""
        _banque(banque.annuler, self.get_object())
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=RapprocherSerializer, responses=OperationSerializer)
    @action(detail=True, methods=["post"])
    def rapprocher(self, request, public_id=None):
        """La finance retrouve l'opération sur le relevé bancaire."""
        operation = self.get_object()
        self._exiger_societe("tresorerie.rapprocher_operationtresorerie", operation.societe_id)
        saisie = RapprocherSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        operation = _banque(banque.rapprocher, operation, request.user, **saisie.validated_data)
        return Response(OperationSerializer(operation).data)
