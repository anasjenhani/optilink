from rest_framework.routers import DefaultRouter

from .api.views import (
    AcompteViewSet,
    CongeViewSet,
    EmployeViewSet,
    MonEspaceViewSet,
    PresenceViewSet,
    PrimeViewSet,
    RecapViewSet,
)

router = DefaultRouter()
router.register("rh/employes", EmployeViewSet, basename="employe")
router.register("rh/presence", PresenceViewSet, basename="presence")
router.register("rh/conges", CongeViewSet, basename="conge")
router.register("rh/mon-espace", MonEspaceViewSet, basename="mon-espace")
router.register("rh/acomptes", AcompteViewSet, basename="acompte")
router.register("rh/primes", PrimeViewSet, basename="prime")
router.register("rh/recap", RecapViewSet, basename="recap-paie")

urlpatterns = router.urls
