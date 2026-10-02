from django.db.models import IntegerField, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, viewsets
from rest_framework.exceptions import PermissionDenied

from apps.reseau.models import Magasin

from ..models import Article, MouvementStock
from .serializers import ArticleSerializer, MouvementStockSerializer


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter(
                "recherche", OpenApiTypes.STR, description="Référence, libellé ou code-barres"
            ),
            OpenApiParameter(
                "magasin", OpenApiTypes.UUID, description="Ajoute le stock de ce magasin"
            ),
        ]
    )
)
class ArticleViewSet(viewsets.ReadOnlyModelViewSet):
    """Catalogue ; avec ``?magasin=``, chaque article porte son stock dans ce magasin."""

    serializer_class = ArticleSerializer
    lookup_field = "public_id"
    filterset_fields = ["famille"]

    def get_queryset(self):
        articles = Article.objects.filter(est_actif=True)
        recherche = self.request.query_params.get("recherche", "").strip()
        if recherche:
            articles = articles.filter(
                Q(reference__icontains=recherche)
                | Q(libelle__icontains=recherche)
                | Q(code_barres=recherche)
            )
        magasin_id = self.request.query_params.get("magasin")
        if not magasin_id:
            return articles.annotate(stock=Value(None, output_field=IntegerField()))
        magasin = get_object_or_404(Magasin.objects, public_id=magasin_id)
        stock = (
            MouvementStock.tous.filter(magasin=magasin, article=OuterRef("pk"))
            .values("article")
            .annotate(total=Sum("quantite"))
            .values("total")
        )
        return articles.annotate(stock=Coalesce(Subquery(stock), 0))


class MouvementStockViewSet(
    mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet
):
    """Réceptions et ajustements saisis à la main ; les ventes créent leurs propres sorties."""

    serializer_class = MouvementStockSerializer
    filterset_fields = ["type"]

    def get_queryset(self):
        return MouvementStock.objects.select_related("magasin", "article").order_by("-horodatage")

    def perform_create(self, serializer):
        magasin = serializer.validated_data["magasin"]
        if not self.request.user.has_perm("stock.add_mouvementstock", magasin):
            raise PermissionDenied("Pas de droit de saisie de stock sur ce magasin.")
        serializer.save(utilisateur=self.request.user)
