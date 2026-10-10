"""Péremption des lentilles en stock d'un dépôt."""

from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from ..peremptions import peremptions
from .sorties import _depot, _magasin


class LotPeremptionSerializer(serializers.Serializer):
    date = serializers.DateField(allow_null=True, help_text="Vide : date inconnue.")
    quantite = serializers.IntegerField()


class PeremptionSerializer(serializers.Serializer):
    article = serializers.UUIDField(source="article.public_id")
    reference = serializers.CharField(source="article.reference")
    libelle = serializers.CharField(source="article.libelle")
    stock = serializers.IntegerField()
    prochaine = serializers.DateField(allow_null=True)
    etat = serializers.ChoiceField(choices=["perimee", "proche", "inconnue", "ok"])
    lots = LotPeremptionSerializer(many=True)


class PeremptionViewSet(viewsets.ViewSet):
    """Lentilles en stock et leurs dates de péremption : périmées, puis proches, puis à dater."""

    permissions_requises = {"list": "stock.view_article"}

    @extend_schema(
        parameters=[
            OpenApiParameter("magasin", OpenApiTypes.UUID, required=True),
            OpenApiParameter(
                "depot", OpenApiTypes.UUID, description="Par défaut : le dépôt de vente."
            ),
            OpenApiParameter(
                "jours", OpenApiTypes.INT, description="« Proche » : dans ce délai (90 jours)."
            ),
        ],
        responses=PeremptionSerializer(many=True),
    )
    def list(self, request):
        if not request.query_params.get("magasin"):
            raise ValidationError({"magasin": "Choisir le magasin."})
        magasin = _magasin(request.query_params["magasin"], "magasin")
        if not request.user.has_perm("stock.view_article", magasin):
            raise PermissionDenied("Pas de droit de voir le stock de ce magasin.")
        try:
            jours = int(request.query_params.get("jours") or 90)
        except ValueError:
            raise ValidationError({"jours": "Nombre de jours invalide."}) from None
        depot = _depot(magasin, request.query_params.get("depot"))
        lignes = peremptions(depot, timezone.localdate(), proche_jours=max(jours, 0))
        return Response(PeremptionSerializer(lignes, many=True).data)
