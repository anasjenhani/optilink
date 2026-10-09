from rest_framework.routers import DefaultRouter

from .api.views import BanqueViewSet, MagasinViewSet, SocieteViewSet, VilleViewSet

router = DefaultRouter()
router.register("magasins", MagasinViewSet, basename="magasin")
router.register("societes", SocieteViewSet, basename="societe")
router.register("villes", VilleViewSet, basename="ville")
router.register("banques", BanqueViewSet, basename="banque")

urlpatterns = router.urls
