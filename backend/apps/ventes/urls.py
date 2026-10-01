from rest_framework.routers import DefaultRouter

from .api.views import AvoirViewSet, DevisViewSet, FactureViewSet, VenteViewSet

router = DefaultRouter()
router.register("ventes", VenteViewSet, basename="vente")
router.register("factures", FactureViewSet, basename="facture")
router.register("devis", DevisViewSet, basename="devis")
router.register("avoirs", AvoirViewSet, basename="avoir")

urlpatterns = router.urls
