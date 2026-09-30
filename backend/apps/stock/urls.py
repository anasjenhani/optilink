from rest_framework.routers import DefaultRouter

from .api.views import ArticleViewSet, MouvementStockViewSet

router = DefaultRouter()
router.register("articles", ArticleViewSet, basename="article")
router.register("mouvements-stock", MouvementStockViewSet, basename="mouvement-stock")

urlpatterns = router.urls
