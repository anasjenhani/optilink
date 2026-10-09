from django.db.models import Q
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, viewsets
from rest_framework.exceptions import PermissionDenied

from ..models import Client, Organisme
from .serializers import ClientSerializer, OrganismeSerializer, soldes

TRIS = {
    "fiche": ["reference_externe", "numero"],
    "-fiche": ["-reference_externe", "-numero"],
    "nom": ["nom", "prenom"],
    "-nom": ["-nom", "-prenom"],
}


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter(
                "recherche",
                OpenApiTypes.STR,
                description="N° de fiche, nom, prénom, téléphones, e-mail, société, "
                "matricule fiscal ou ancien n° de fiche",
            ),
            *(
                OpenApiParameter(nom, OpenApiTypes.STR, description=description)
                for nom, description in (
                    ("fiche", "Colonne N° fiche : n° de fiche ou ancien n° (contient)"),
                    ("telephone", "Colonne Téléphone : l'un des deux numéros (contient)"),
                    ("nom", "Colonne Nom & Prénom : chaque mot dans le nom ou le prénom"),
                    ("prenom", "Colonne Prénom (contient)"),
                    ("observation", "Colonne Observation : notes de la fiche (contient)"),
                )
            ),
            OpenApiParameter(
                "tri",
                OpenApiTypes.STR,
                enum=list(TRIS),
                description="Ordre de la liste ; par défaut nom puis prénom",
            ),
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
        parametres = self.request.query_params
        colonnes = {
            "fiche": lambda v: (
                Q(reference_externe__icontains=v)
                | (Q(numero=int(v)) if v.isdigit() and len(v) < 10 else Q(pk__in=[]))
            ),
            "telephone": lambda v: Q(telephone__icontains=v) | Q(telephone_2__icontains=v),
            "prenom": lambda v: Q(prenom__icontains=v),
            "observation": lambda v: Q(notes__icontains=v),
        }
        for colonne, condition in colonnes.items():
            valeur = parametres.get(colonne, "").strip()
            if valeur:
                clients = clients.filter(condition(valeur))
        for mot in parametres.get("nom", "").split():
            clients = clients.filter(Q(nom__icontains=mot) | Q(prenom__icontains=mot))
        tri = TRIS.get(parametres.get("tri", ""))
        return clients.order_by(*tri) if tri else clients

    def get_serializer_context(self):
        contexte = super().get_serializer_context()
        if self.action in ("list", "retrieve"):
            contexte["avec_solde"] = True
        return contexte

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.filter_queryset(self.get_queryset()))
        contexte = {**self.get_serializer_context(), "soldes": soldes(page)}
        return self.get_paginated_response(ClientSerializer(page, many=True, context=contexte).data)

    def perform_create(self, serializer):
        magasin = serializer.validated_data["magasin_origine"]
        if not self.request.user.has_perm("crm.add_client", magasin):
            raise PermissionDenied("Pas de droit de création de client sur ce magasin.")
        serializer.save()


class OrganismeViewSet(viewsets.ReadOnlyModelViewSet):
    """CNAM, assurances et mutuelles actives ; on les crée dans l'administration du serveur."""

    serializer_class = OrganismeSerializer
    lookup_field = "public_id"
    pagination_class = None
    permissions_requises = {"list": "crm.view_client", "retrieve": "crm.view_client"}

    def get_queryset(self):
        return Organisme.objects.filter(est_actif=True).select_related("pays")
