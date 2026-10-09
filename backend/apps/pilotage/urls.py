from rest_framework.routers import DefaultRouter

from .api import StatistiqueViewSet

router = DefaultRouter()
router.register("statistiques", StatistiqueViewSet, basename="statistique")

urlpatterns = router.urls
