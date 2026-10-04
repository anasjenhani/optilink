from rest_framework.routers import DefaultRouter

from .api.views import ClientViewSet, OrganismeViewSet

router = DefaultRouter()
router.register("clients", ClientViewSet, basename="client")
router.register("organismes", OrganismeViewSet, basename="organisme")

urlpatterns = router.urls
