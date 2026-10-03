from rest_framework.routers import DefaultRouter

from .api.views import ClotureViewSet, DepenseViewSet

router = DefaultRouter()
router.register("tresorerie/clotures", ClotureViewSet, basename="cloture")
router.register("tresorerie/depenses", DepenseViewSet, basename="depense")

urlpatterns = router.urls
