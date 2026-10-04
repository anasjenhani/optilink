import uuid

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, viewsets
from rest_framework.exceptions import ValidationError

from ..models import Lunette, Vente
from .serializers import LunetteClientSerializer


@extend_schema_view(
    list=extend_schema(
        parameters=[OpenApiParameter("client", OpenApiTypes.UUID, description="Lunettes du client")]
    )
)
class LunetteViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Lunettes vendues (monture, verres, péniche), la plus récente d'abord."""

    serializer_class = LunetteClientSerializer
    permissions_requises = {"list": "ventes.view_vente"}

    def get_queryset(self):
        lunettes = (
            Lunette.objects.filter(vente__in=Vente.objects.all())
            .exclude(vente__statut=Vente.Statut.ANNULEE)
            .select_related("vente__magasin", "prescription")
            .prefetch_related("lignes")
            .order_by("-vente__cree_le", "numero")
        )
        client = self.request.query_params.get("client")
        if client:
            try:
                uuid.UUID(client)
            except ValueError:
                raise ValidationError({"client": "Identifiant invalide."}) from None
            lunettes = lunettes.filter(vente__client__public_id=client)
        return lunettes
