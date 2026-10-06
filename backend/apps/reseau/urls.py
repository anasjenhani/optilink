from rest_framework.routers import DefaultRouter

from .api.views import MagasinViewSet, SocieteViewSet, VilleViewSet

router = DefaultRouter()
router.register("magasins", MagasinViewSet, basename="magasin")
router.register("societes", SocieteViewSet, basename="societe")
router.register("villes", VilleViewSet, basename="ville")

urlpatterns = router.urls
