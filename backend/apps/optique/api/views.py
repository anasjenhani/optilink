from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.crm.models import Client
from apps.securite.journal import adresse_ip

from ..models import AccesPrescription, Ophtalmologue, Prescription
from ..ophtalmologues import cle_ophtalmologue
from .serializers import OphtalmologueSerializer, PrescriptionSerializer


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter(
                "client", OpenApiTypes.UUID, required=True, description="Client concerné"
            )
        ]
    )
)
class PrescriptionViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Ordonnances d'un client. Chaque lecture et chaque saisie est journalisée.

    La liste exige ``?client=`` : on consulte le dossier d'une personne, jamais l'ensemble des
    ordonnances du réseau.
    """

    serializer_class = PrescriptionSerializer
    lookup_field = "public_id"
    permissions_requises = {
        "list": "optique.view_prescription",
        "retrieve": "optique.view_prescription",
        "create": "optique.add_prescription",
    }

    def get_queryset(self):
        prescriptions = Prescription.objects.select_related(
            "client", "magasin_saisie", "saisie_par"
        )
        if self.action == "list" and not getattr(self, "swagger_fake_view", False):
            client_id = self.request.query_params.get("client")
            if not client_id:
                raise ValidationError({"client": "Préciser le client."})
            try:
                client = get_object_or_404(Client, public_id=client_id)
            except DjangoValidationError:
                raise ValidationError({"client": "Identifiant invalide."}) from None
            prescriptions = prescriptions.filter(client=client)
        return prescriptions

    def _journaliser(self, prescriptions, action):
        AccesPrescription.objects.bulk_create(
            AccesPrescription(
                utilisateur=self.request.user,
                prescription=prescription,
                action=action,
                adresse_ip=adresse_ip(self.request),
            )
            for prescription in prescriptions
        )

    def list(self, request, *args, **kwargs):
        reponse = super().list(request, *args, **kwargs)
        page = getattr(self.paginator, "page", None)
        lues = list(page.object_list) if page is not None else []
        self._journaliser(lues, AccesPrescription.Action.CONSULTATION)
        return reponse

    def retrieve(self, request, *args, **kwargs):
        prescription = self.get_object()
        self._journaliser([prescription], AccesPrescription.Action.CONSULTATION)
        return Response(self.get_serializer(prescription).data)

    def perform_create(self, serializer):
        magasin = serializer.validated_data["magasin_saisie"]
        if not self.request.user.has_perm("optique.add_prescription", magasin):
            raise PermissionDenied("Pas de droit de saisie d'ordonnance sur ce magasin.")
        with transaction.atomic():
            prescription = serializer.save(saisie_par=self.request.user)
            self._journaliser([prescription], AccesPrescription.Action.SAISIE)


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter(
                "recherche", OpenApiTypes.STR, description="Nom (sans « Dr », accents ni casse)"
            )
        ]
    )
)
class OphtalmologueViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    """Liste des ophtalmologistes à choisir sur une ordonnance ; un ajout refuse un doublon.

    La liste se tient aussi dans /admin/ (Ventes › Ophtalmologistes).
    """

    serializer_class = OphtalmologueSerializer
    pagination_class = None
    permissions_requises = {
        "list": "optique.view_prescription",
        "create": "optique.add_prescription",
    }

    def get_queryset(self):
        medecins = Ophtalmologue.objects.filter(est_actif=True)
        recherche = cle_ophtalmologue(self.request.query_params.get("recherche", ""))
        for mot in recherche.split():
            medecins = medecins.filter(cle__contains=mot)
        return medecins[:50]
