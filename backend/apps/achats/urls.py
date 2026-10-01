from rest_framework.routers import DefaultRouter

from .api.views import CommandeFournisseurViewSet, FournisseurViewSet

router = DefaultRouter()
router.register("fournisseurs", FournisseurViewSet, basename="fournisseur")
router.register(
    "commandes-fournisseurs", CommandeFournisseurViewSet, basename="commande-fournisseur"
)

urlpatterns = router.urls
