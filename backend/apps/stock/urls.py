from django.urls import path
from rest_framework.routers import DefaultRouter

from .api.fiches import FicheArticleViewSet
from .api.imports import ImportCatalogueView, ImportStockView, ImportVerresView, ModeleImportView
from .api.inventaires import InventaireViewSet
from .api.transferts import TransfertViewSet
from .api.views import ArticleViewSet, MouvementStockViewSet

router = DefaultRouter()
router.register("articles", ArticleViewSet, basename="article")
router.register("fiches-articles", FicheArticleViewSet, basename="fiche-article")
router.register("mouvements-stock", MouvementStockViewSet, basename="mouvement-stock")
router.register("transferts", TransfertViewSet, basename="transfert")
router.register("inventaires", InventaireViewSet, basename="inventaire")

urlpatterns = [
    path("imports/catalogue/", ImportCatalogueView.as_view(), name="import-catalogue"),
    path("imports/stock/", ImportStockView.as_view(), name="import-stock"),
    path("imports/verres/", ImportVerresView.as_view(), name="import-verres"),
    path(
        "imports/modeles/<str:modele>.<str:extension>",
        ModeleImportView.as_view(),
        name="modele-import",
    ),
    *router.urls,
]
