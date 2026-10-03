from rest_framework.routers import DefaultRouter

from .api.views import AlerteViewSet, ReportingViewSet

router = DefaultRouter()
router.register("pilotage/alertes", AlerteViewSet, basename="alerte")
router.register("pilotage/reporting", ReportingViewSet, basename="reporting")

urlpatterns = router.urls
