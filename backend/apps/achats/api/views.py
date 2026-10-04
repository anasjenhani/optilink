import uuid

from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.reseau.models import Magasin

from ..models import CasseVerre, CommandeFournisseur, Fournisseur, LigneCommandeFournisseur
from ..services import (
    CasseImpossible,
    CommandeFournisseurImpossible,
    annuler_commande_fournisseur,
    declarer_casse,
    passer_commande,
    receptionner,
    verres_a_commander,
)
from .serializers import (
    CasseVerreSaisieSerializer,
    CasseVerreSerializer,
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


class CasseVerreViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    """Verres cassés ou défectueux après réception, à recommander au fournisseur."""

    serializer_class = CasseVerreSerializer
    filterset_fields = ["cause", "vente__magasin__public_id"]
    permissions_requises = {"list": "achats.view_casseverre", "create": "achats.add_casseverre"}

    def get_queryset(self):
        # Les ventes visibles portent le périmètre de magasins de l'utilisateur.
        from apps.ventes.models import Vente

        return CasseVerre.objects.filter(vente__in=Vente.objects.all()).select_related(
            "vente__magasin",
            "vente__client",
            "ligne_commande__ligne_vente",
            "ligne_commande__commande__fournisseur",
            "declaree_par",
        )

    @extend_schema(request=CasseVerreSaisieSerializer, responses={201: CasseVerreSerializer})
    def create(self, request):
        """Déclare une casse : le verre repasse « à commander » et le suivi y revient."""
        from apps.ventes.models import Vente

        saisie = CasseVerreSaisieSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        donnees = saisie.validated_data
        ligne = (
            LigneCommandeFournisseur.objects.filter(
                pk=donnees["ligne_commande"], ligne_vente__vente__in=Vente.objects.all()
            )
            .select_related("ligne_vente__vente")
            .first()
        )
        if ligne is None:
            raise ValidationError({"ligne_commande": "Verre inconnu ou hors de votre périmètre."})
        if not request.user.has_perm("achats.add_casseverre", ligne.ligne_vente.vente):
            raise PermissionDenied("Pas de droit de déclarer une casse dans ce magasin.")
        try:
            casse = declarer_casse(
                ligne_commande=ligne,
                cause=donnees["cause"],
                observation=donnees.get("observation", ""),
                utilisateur=request.user,
            )
        except CasseImpossible as erreur:
            return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        casse = self.get_queryset().get(pk=casse.pk)
        return Response(CasseVerreSerializer(casse).data, status=status.HTTP_201_CREATED)
