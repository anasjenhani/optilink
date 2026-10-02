from django.urls import path

from .api import views

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
]
