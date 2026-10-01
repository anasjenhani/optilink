from rest_framework.routers import DefaultRouter

from .api.views import ClientViewSet

router = DefaultRouter()
router.register("clients", ClientViewSet, basename="client")

urlpatterns = router.urls
