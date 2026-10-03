from rest_framework.routers import DefaultRouter

from .api.views import CongeViewSet, EmployeViewSet, MonEspaceViewSet, PresenceViewSet

router = DefaultRouter()
router.register("rh/employes", EmployeViewSet, basename="employe")
router.register("rh/presence", PresenceViewSet, basename="presence")
router.register("rh/conges", CongeViewSet, basename="conge")
router.register("rh/mon-espace", MonEspaceViewSet, basename="mon-espace")

urlpatterns = router.urls
