from rest_framework.routers import DefaultRouter

from .api.bordereaux import BordereauPecViewSet
from .api.lunettes import LentillesViewSet, LunetteViewSet
from .api.prises_en_charge import PriseEnChargeViewSet
from .api.sav import DossierSavViewSet
from .api.views import AvoirViewSet, DevisViewSet, FactureViewSet, VenteViewSet

router = DefaultRouter()
router.register("ventes", VenteViewSet, basename="vente")
router.register("factures", FactureViewSet, basename="facture")
router.register("devis", DevisViewSet, basename="devis")
router.register("avoirs", AvoirViewSet, basename="avoir")
router.register("lunettes", LunetteViewSet, basename="lunette")
router.register("lentilles", LentillesViewSet, basename="lentilles")
router.register("prises-en-charge", PriseEnChargeViewSet, basename="prise-en-charge")
router.register("bordereaux-pec", BordereauPecViewSet, basename="bordereau-pec")
router.register("sav", DossierSavViewSet, basename="dossier-sav")

urlpatterns = router.urls
