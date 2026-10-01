from rest_framework.routers import DefaultRouter

from .api.views import FactureViewSet, VenteViewSet

router = DefaultRouter()
router.register("ventes", VenteViewSet, basename="vente")
router.register("factures", FactureViewSet, basename="facture")

urlpatterns = router.urls
