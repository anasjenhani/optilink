import uuid

from django.db.models import (
    CharField,
    DecimalField,
    Exists,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, viewsets
from rest_framework.exceptions import PermissionDenied

from apps.reseau.models import Magasin

from ..models import Article, MouvementStock, PrixArticle
from .serializers import ArticleSerializer, MouvementStockSerializer

# Le vendeur choisit d'abord ce qu'il vend ; chaque type correspond à des familles d'articles.
TYPES_DE_VENTE = {
    "optique": Q(famille=Article.Famille.VERRE)
    | Q(famille=Article.Famille.MONTURE, monture__solaire=False)
    | Q(famille=Article.Famille.MONTURE, monture__isnull=True),
    "solaire": Q(famille=Article.Famille.MONTURE, monture__solaire=True),
    "lentille": Q(famille=Article.Famille.LENTILLE) | Q(famille=Article.Famille.DIVERS),
    "produit": Q(famille=Article.Famille.DIVERS),
}


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter(
                "recherche",
                OpenApiTypes.STR,
                description="Référence, libellé, code-barres, marque, modèle ou gamme",
            ),
            OpenApiParameter("marque", OpenApiTypes.STR, description="Marque (toutes familles)"),
            OpenApiParameter(
                "type_vente",
                OpenApiTypes.STR,
                enum=list(TYPES_DE_VENTE),
                description="Ce qu'on vend au comptoir : lunettes optiques (montures et verres), "
                "lunettes solaires, lentilles, ou produits et accessoires",
            ),
            OpenApiParameter(
                "fournisseur", OpenApiTypes.UUID, description="Articles de ce fournisseur"
            ),
            OpenApiParameter(
                "magasin",
                OpenApiTypes.UUID,
                description="Ajoute stock et prix dans ce magasin (articles vendables seulement)",
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
        articles = Article.objects.filter(est_actif=True).select_related(
            "monture", "verre", "lentille", "fournisseur"
        )
        fournisseur = self.request.query_params.get("fournisseur")
        if fournisseur:
            try:
                articles = articles.filter(fournisseur__public_id=uuid.UUID(fournisseur))
            except ValueError:
                articles = articles.none()
        recherche = self.request.query_params.get("recherche", "").strip()
        if recherche:
            articles = articles.filter(
                Q(reference__icontains=recherche)
                | Q(libelle__icontains=recherche)
                | Q(code_barres=recherche)
                | Q(reference_fournisseur__iexact=recherche)
                | Q(monture__marque__icontains=recherche)
                | Q(monture__modele__icontains=recherche)
                | Q(verre__marque__icontains=recherche)
                | Q(verre__gamme__icontains=recherche)
                | Q(lentille__marque__icontains=recherche)
                | Q(lentille__modele__icontains=recherche)
            )
        type_vente = self.request.query_params.get("type_vente")
        if type_vente in TYPES_DE_VENTE:
            articles = articles.filter(TYPES_DE_VENTE[type_vente])
        marque = self.request.query_params.get("marque", "").strip()
        if marque:
            articles = articles.filter(
                Q(monture__marque__iexact=marque)
                | Q(verre__marque__iexact=marque)
                | Q(lentille__marque__iexact=marque)
            )
        magasin_id = self.request.query_params.get("magasin")
        if not magasin_id:
            return articles.annotate(
                stock=Value(None, output_field=IntegerField()),
                prix_vente_ttc=Value(None, output_field=DecimalField()),
                taux_tva=Value(None, output_field=DecimalField()),
                devise=Value(None, output_field=CharField()),
            )
        magasin = get_object_or_404(Magasin.objects.select_related("pays"), public_id=magasin_id)
        # Seuls les articles qui ont un prix dans le pays du magasin y sont vendables.
        tarif = PrixArticle.objects.filter(article=OuterRef("pk"), pays=magasin.pays)
        articles = articles.filter(Exists(tarif)).annotate(
            prix_vente_ttc=Subquery(tarif.values("prix_vente_ttc")),
            taux_tva=Subquery(tarif.values("tva__taux")),
            devise=Value(magasin.pays.devise, output_field=CharField()),
        )
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
