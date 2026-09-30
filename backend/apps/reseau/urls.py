from rest_framework.routers import DefaultRouter

from .api.views import MagasinViewSet

router = DefaultRouter()
router.register("magasins", MagasinViewSet, basename="magasin")

urlpatterns = router.urls
