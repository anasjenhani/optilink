from rest_framework.routers import DefaultRouter

from .api.views import DevisViewSet, FactureViewSet, VenteViewSet

router = DefaultRouter()
router.register("ventes", VenteViewSet, basename="vente")
router.register("factures", FactureViewSet, basename="facture")
router.register("devis", DevisViewSet, basename="devis")

urlpatterns = router.urls
