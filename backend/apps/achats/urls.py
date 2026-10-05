from django.urls import path
from rest_framework.routers import DefaultRouter

from .api.factures import FactureAchatViewSet
from .api.imports import ImportFournisseursView, ImportReceptionsView
from .api.views import (
    BonReceptionViewSet,
    CasseVerreViewSet,
    CommandeFournisseurViewSet,
    FournisseurViewSet,
)

router = DefaultRouter()
router.register("fournisseurs", FournisseurViewSet, basename="fournisseur")
router.register(
    "commandes-fournisseurs", CommandeFournisseurViewSet, basename="commande-fournisseur"
)
router.register("casses-verres", CasseVerreViewSet, basename="casse-verre")
router.register("bons-reception", BonReceptionViewSet, basename="bon-reception")
router.register("factures-achat", FactureAchatViewSet, basename="facture-achat")

urlpatterns = [
    path("imports/fournisseurs/", ImportFournisseursView.as_view(), name="import-fournisseurs"),
    path("imports/receptions/", ImportReceptionsView.as_view(), name="import-receptions"),
    *router.urls,
]
