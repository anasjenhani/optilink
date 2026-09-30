from django.contrib import admin
from django.urls import include, path
from django_otp.admin import OTPAdminSite
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from core.views import sante

# L'administration exige aussi le second facteur.
admin.site.__class__ = OTPAdminSite

api_v1 = [
    path("sante/", sante, name="sante"),
    path("", include("apps.securite.urls")),
    path("", include("apps.reseau.urls")),
    path("", include("apps.stock.urls")),
    path("", include("apps.ventes.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_v1)),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]
