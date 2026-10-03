import uuid

from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.reseau.models import Magasin

from .. import services
from ..models import ClotureCaisse, DepenseCaisse
from .serializers import (
    ClotureSaisieSerializer,
    ClotureSerializer,
    ComptageSerializer,
    DepenseSerializer,
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


class DepenseViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    """Dépenses payées en espèces depuis la caisse du magasin."""

    serializer_class = DepenseSerializer
    filterset_fields = {"magasin__public_id": ["exact"], "cloture": ["isnull"]}
    permissions_requises = {
        "list": "tresorerie.view_depensecaisse",
        "create": "tresorerie.add_depensecaisse",
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
