from django.urls import path
from rest_framework.routers import DefaultRouter

from .api.imports import ImportCatalogueView, ImportStockView
from .api.views import ArticleViewSet, MouvementStockViewSet

router = DefaultRouter()
router.register("articles", ArticleViewSet, basename="article")
router.register("mouvements-stock", MouvementStockViewSet, basename="mouvement-stock")

urlpatterns = [
    path("imports/catalogue/", ImportCatalogueView.as_view(), name="import-catalogue"),
    path("imports/stock/", ImportStockView.as_view(), name="import-stock"),
    *router.urls,
]
