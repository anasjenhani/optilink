from django.urls import path
from rest_framework.routers import DefaultRouter

from .api.imports import ImportClientsView
from .api.views import ClientViewSet

router = DefaultRouter()
router.register("clients", ClientViewSet, basename="client")

urlpatterns = [
    path("imports/clients/", ImportClientsView.as_view(), name="import-clients"),
    *router.urls,
]
