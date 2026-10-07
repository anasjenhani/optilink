from rest_framework.routers import DefaultRouter

from .api.views import OphtalmologueViewSet, PrescriptionViewSet

router = DefaultRouter()
router.register("prescriptions", PrescriptionViewSet, basename="prescription")
router.register("ophtalmologues", OphtalmologueViewSet, basename="ophtalmologue")

urlpatterns = router.urls
