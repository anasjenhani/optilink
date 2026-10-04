from rest_framework.routers import DefaultRouter

from .api.views import CasseVerreViewSet, CommandeFournisseurViewSet, FournisseurViewSet

router = DefaultRouter()
router.register("fournisseurs", FournisseurViewSet, basename="fournisseur")
router.register(
    "commandes-fournisseurs", CommandeFournisseurViewSet, basename="commande-fournisseur"
)
router.register("casses-verres", CasseVerreViewSet, basename="casse-verre")

urlpatterns = router.urls
