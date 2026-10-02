from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.crm.models import Client
from apps.reseau.models import Magasin
from apps.stock.models import Article

from ..models import Facture, Vente
from ..services import FactureImpossible, VenteInvalide, enregistrer_vente, generer_facture
from .serializers import (
    FactureSaisieSerializer,
    FactureSerializer,
    VenteSaisieSerializer,
    VenteSerializer,
)


class VenteViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Ventes du périmètre ; une vente enregistrée n'est jamais modifiée."""

    serializer_class = VenteSerializer
    lookup_field = "public_id"
    filterset_fields = ["numero"]

    def get_queryset(self):
        return Vente.objects.select_related(
            "magasin", "vendeur", "client", "facture"
        ).prefetch_related("lignes__article", "paiements")

    @extend_schema(request=VenteSaisieSerializer, responses={201: VenteSerializer})
    def create(self, request):
        saisie = VenteSaisieSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        donnees = saisie.validated_data

        magasin = Magasin.objects.filter(public_id=donnees["magasin"]).first()
        if magasin is None:
            raise ValidationError({"magasin": "Magasin inconnu ou hors de votre périmètre."})
        user = request.user
        if not user.has_perm("ventes.add_vente", magasin):
            raise PermissionDenied("Pas de droit de vente dans ce magasin.")
        if any(ligne["remise_pct"] > 0 for ligne in donnees["lignes"]) and not user.has_perm(
            "ventes.appliquer_remise", magasin
        ):
            raise PermissionDenied("Remise non autorisée pour votre rôle.")

        articles = Article.objects.filter(
            public_id__in={ligne["article"] for ligne in donnees["lignes"]}, est_actif=True
        ).in_bulk(field_name="public_id")
        manquants = {ligne["article"] for ligne in donnees["lignes"]} - set(articles)
        if manquants:
            raise ValidationError({"lignes": "Article inconnu ou retiré de la vente."})

        client = None
        if donnees.get("client"):
            if not user.has_perm("crm.view_client"):
                raise PermissionDenied("Pas d'accès aux fiches clients.")
            client = Client.objects.filter(public_id=donnees["client"]).first()
            if client is None:
                raise ValidationError({"client": "Client inconnu."})

        try:
            vente = enregistrer_vente(
                magasin=magasin,
                vendeur=user,
                lignes=[
                    {**ligne, "article": articles[ligne["article"]]} for ligne in donnees["lignes"]
                ],
                paiements=donnees["paiements"],
                client=client,
            )
        except VenteInvalide as erreur:
            return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        vente = self.get_queryset().get(pk=vente.pk)
        return Response(VenteSerializer(vente).data, status=status.HTTP_201_CREATED)


class FactureViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Factures du périmètre. Une facture se génère à part, pour une vente entièrement payée."""

    serializer_class = FactureSerializer
    lookup_field = "public_id"
    filterset_fields = ["numero"]

    def get_queryset(self):
        return Facture.objects.select_related(
            "magasin", "vente", "client", "emise_par"
        ).prefetch_related("vente__lignes__article")

    @extend_schema(request=FactureSaisieSerializer, responses={201: FactureSerializer})
    def create(self, request):
        saisie = FactureSaisieSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        donnees = saisie.validated_data

        vente = (
            Vente.objects.select_related("magasin", "client")
            .filter(public_id=donnees["vente"])
            .first()
        )
        if vente is None:
            raise ValidationError({"vente": "Vente inconnue ou hors de votre périmètre."})
        if not request.user.has_perm("ventes.add_facture", vente.magasin):
            raise PermissionDenied("Pas de droit de facturation dans ce magasin.")
        client = vente.client
        if donnees.get("client"):
            client = Client.objects.filter(public_id=donnees["client"]).first()
            if client is None:
                raise ValidationError({"client": "Client inconnu."})

        try:
            facture = generer_facture(
                vente=vente,
                client=client,
                emetteur=request.user,
                mode_paiement_timbre=donnees.get("mode_paiement_timbre", ""),
            )
        except FactureImpossible as erreur:
            return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        facture = self.get_queryset().get(pk=facture.pk)
        return Response(FactureSerializer(facture).data, status=status.HTTP_201_CREATED)
