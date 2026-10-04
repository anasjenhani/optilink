from django.urls import path
from rest_framework.routers import DefaultRouter

from .api.imports import ImportClientsView
from .api.views import ClientViewSet, OrganismeViewSet

router = DefaultRouter()
router.register("clients", ClientViewSet, basename="client")
router.register("organismes", OrganismeViewSet, basename="organisme")

urlpatterns = [
    path("imports/clients/", ImportClientsView.as_view(), name="import-clients"),
    *router.urls,
]
