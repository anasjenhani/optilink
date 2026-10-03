from rest_framework.routers import DefaultRouter

from .api.views import ClotureViewSet, CompteViewSet, DepenseViewSet, OperationViewSet

router = DefaultRouter()
router.register("tresorerie/clotures", ClotureViewSet, basename="cloture")
router.register("tresorerie/depenses", DepenseViewSet, basename="depense")
router.register("tresorerie/comptes", CompteViewSet, basename="compte-tresorerie")
router.register("tresorerie/operations", OperationViewSet, basename="operation-tresorerie")

urlpatterns = router.urls
