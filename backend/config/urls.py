from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.securite.admin import brancher_corbeille
from core.admin_site import OptiLinkAdminSite
from core.views import sante

# L'administration exige aussi le second facteur, et présente ses pages en onglets ; ses
# suppressions passent par la corbeille.
admin.site.__class__ = OptiLinkAdminSite
brancher_corbeille(admin.site)

api_v1 = [
    path("sante/", sante, name="sante"),
    path("", include("apps.securite.urls")),
    path("", include("apps.reseau.urls")),
    path("", include("apps.stock.urls")),
    path("", include("apps.ventes.urls")),
    path("", include("apps.crm.urls")),
    path("", include("apps.optique.urls")),
    path("", include("apps.achats.urls")),
    path("", include("apps.tresorerie.urls")),
    path("", include("apps.rh.urls")),
    path("", include("apps.pilotage.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_v1)),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]
