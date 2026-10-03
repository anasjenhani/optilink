from rest_framework.routers import DefaultRouter

from .api.views import MagasinViewSet, SocieteViewSet

router = DefaultRouter()
router.register("magasins", MagasinViewSet, basename="magasin")
router.register("societes", SocieteViewSet, basename="societe")

urlpatterns = router.urls
