from django.urls import path
from rest_framework.routers import DefaultRouter

from .api import acces, corbeille, views
from .api.imports import ImportUtilisateursView

router = DefaultRouter()
router.register("securite/utilisateurs", acces.UtilisateurViewSet, basename="utilisateur")
router.register("securite/profils", acces.ProfilViewSet, basename="profil")
router.register("corbeille", corbeille.CorbeilleViewSet, basename="corbeille")

urlpatterns = [
    path("auth/session/", views.SessionView.as_view(), name="auth-session"),
    path("auth/connexion/", views.ConnexionView.as_view(), name="auth-connexion"),
    path("auth/deconnexion/", views.DeconnexionView.as_view(), name="auth-deconnexion"),
    path("auth/mfa/verification/", views.VerificationMfaView.as_view(), name="mfa-verification"),
    path("auth/mfa/activation/", views.ActivationMfaView.as_view(), name="mfa-activation"),
    path(
        "auth/mfa/activation/confirmation/",
        views.ConfirmationMfaView.as_view(),
        name="mfa-confirmation",
    ),
    path("securite/privileges/", acces.PrivilegesView.as_view(), name="privileges"),
    path("imports/utilisateurs/", ImportUtilisateursView.as_view(), name="import-utilisateurs"),
    *router.urls,
]
