from django.db.models import Q
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, viewsets
from rest_framework.exceptions import PermissionDenied

from ..models import Client
from .serializers import ClientSerializer


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter(
                "recherche",
                OpenApiTypes.STR,
                description="N° de fiche, nom, prénom, téléphones, e-mail, société, "
                "matricule fiscal ou ancien n° de fiche",
            )
        ]
    )
)
class ClientViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Fiches clients, communes à tout le réseau. Pas de suppression : on désactive."""

    serializer_class = ClientSerializer
    lookup_field = "public_id"
    filterset_fields = ["est_actif"]

    def get_queryset(self):
        clients = Client.objects.select_related("magasin_origine")
        recherche = self.request.query_params.get("recherche", "").strip()
        for mot in recherche.split():
            # Un nombre peut être un n° de fiche aussi bien qu'un morceau de téléphone.
            fiche = Q(numero=int(mot)) if mot.isdigit() and len(mot) < 10 else Q()
            clients = clients.filter(
                fiche
                | Q(nom__icontains=mot)
                | Q(prenom__icontains=mot)
                | Q(telephone__icontains=mot)
                | Q(telephone_2__icontains=mot)
                | Q(email__icontains=mot)
                | Q(societe__icontains=mot)
                | Q(matricule_fiscal__icontains=mot)
                | Q(reference_externe__iexact=mot)
            )
        return clients

    def perform_create(self, serializer):
        magasin = serializer.validated_data["magasin_origine"]
        if not self.request.user.has_perm("crm.add_client", magasin):
            raise PermissionDenied("Pas de droit de création de client sur ce magasin.")
        serializer.save()
