import uuid

from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.reseau.models import Magasin

from ..models import CommandeFournisseur, Fournisseur
from ..services import (
    CommandeFournisseurImpossible,
    annuler_commande_fournisseur,
    passer_commande,
    receptionner,
    verres_a_commander,
)
from .serializers import (
    CommandeFournisseurSaisieSerializer,
    CommandeFournisseurSerializer,
    FournisseurSerializer,
    VerreACommanderSerializer,
)


class FournisseurViewSet(viewsets.ReadOnlyModelViewSet):
    """Fournisseurs actifs ; ils se créent et se modifient dans l'administration."""

    serializer_class = FournisseurSerializer
    lookup_field = "public_id"
    queryset = Fournisseur.objects.filter(est_actif=True).select_related("pays")


class CommandeFournisseurViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Commandes de verres aux fournisseurs, pour les commandes clients du magasin."""

    serializer_class = CommandeFournisseurSerializer
    lookup_field = "public_id"
    filterset_fields = ["statut", "magasin__public_id", "numero"]
    permissions_requises = {
        "list": "achats.view_commandefournisseur",
        "retrieve": "achats.view_commandefournisseur",
        "create": "achats.add_commandefournisseur",
        "a_commander": "achats.view_commandefournisseur",
        "receptionner": "achats.change_commandefournisseur",
        "annuler": "achats.change_commandefournisseur",
    }

    def get_queryset(self):
        return CommandeFournisseur.objects.select_related(
            "magasin", "fournisseur", "passee_par"
        ).prefetch_related("lignes__ligne_vente__vente")

    def _magasin(self, public_id):
        magasin = Magasin.objects.select_related("pays").filter(public_id=public_id).first()
        if magasin is None:
            raise ValidationError({"magasin": "Magasin inconnu ou hors de votre périmètre."})
        return magasin

    @extend_schema(
        parameters=[OpenApiParameter("magasin", OpenApiTypes.UUID, required=True)],
        responses={200: VerreACommanderSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="a-commander")
    def a_commander(self, request):
        """Verres des commandes clients qui restent à commander au fournisseur."""
        identifiant = request.query_params.get("magasin")
        if not identifiant:
            raise ValidationError({"magasin": "Préciser le magasin."})
        try:
            uuid.UUID(identifiant)
        except ValueError:
            raise ValidationError({"magasin": "Identifiant invalide."}) from None
        magasin = self._magasin(identifiant)
        lignes = verres_a_commander(magasin)
        return Response(VerreACommanderSerializer(lignes, many=True).data)

    @extend_schema(
        request=CommandeFournisseurSaisieSerializer, responses={201: CommandeFournisseurSerializer}
    )
    def create(self, request):
        saisie = CommandeFournisseurSaisieSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        donnees = saisie.validated_data
        magasin = self._magasin(donnees["magasin"])
        if not request.user.has_perm("achats.add_commandefournisseur", magasin):
            raise PermissionDenied("Pas de droit de commande fournisseur dans ce magasin.")
        fournisseur = get_object_or_404(Fournisseur, public_id=donnees["fournisseur"])
        try:
            commande = passer_commande(
                magasin=magasin,
                fournisseur=fournisseur,
                lignes=[
                    {"ligne_vente": ligne["ligne"], "details": ligne.get("details", "")}
                    for ligne in donnees["lignes"]
                ],
                auteur=request.user,
                reference_fournisseur=donnees.get("reference_fournisseur", ""),
            )
        except CommandeFournisseurImpossible as erreur:
            return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        commande = self.get_queryset().get(pk=commande.pk)
        return Response(
            CommandeFournisseurSerializer(commande).data, status=status.HTTP_201_CREATED
        )

    def _changer(self, operation, **parametres):
        try:
            commande = operation(commande=self.get_object(), **parametres)
        except CommandeFournisseurImpossible as erreur:
            return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(CommandeFournisseurSerializer(self.get_queryset().get(pk=commande.pk)).data)

    @extend_schema(request=None, responses={200: CommandeFournisseurSerializer})
    @action(detail=True, methods=["post"])
    def receptionner(self, request, public_id=None):
        """Verres reçus : les commandes clients concernées peuvent être livrées."""
        return self._changer(receptionner, utilisateur=request.user)

    @extend_schema(request=None, responses={200: CommandeFournisseurSerializer})
    @action(detail=True, methods=["post"])
    def annuler(self, request, public_id=None):
        """Les verres repassent « à commander »."""
        return self._changer(annuler_commande_fournisseur)
