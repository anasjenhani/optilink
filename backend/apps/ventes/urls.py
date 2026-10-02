from rest_framework.routers import DefaultRouter

from .api.views import VenteViewSet

router = DefaultRouter()
router.register("ventes", VenteViewSet, basename="vente")

urlpatterns = router.urls
