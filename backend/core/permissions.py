from django.conf import settings
from rest_framework.permissions import BasePermission

_ACTIONS_PAR_METHODE = {
    "GET": "view",
    "HEAD": "view",
    "OPTIONS": "view",
    "POST": "add",
    "PUT": "change",
    "PATCH": "change",
    "DELETE": "delete",
}


def mfa_verifiee(user):
    """Second facteur validé pour cette session (appareil posé par OTPMiddleware ou otp_login)."""
    return getattr(user, "otp_device", None) is not None


def mfa_requise(user):
    """Le second facteur n'est exigé que des administrateurs : accès à /admin/ ou profil listé
    dans MFA_PROFILS. Les autres comptes se connectent avec leur seul mot de passe."""
    if not settings.MFA_OBLIGATOIRE:
        return False
    if user.is_staff or user.is_superuser:
        return True
    return user.affectations.filter(role__name__in=settings.MFA_PROFILS).exists()


class MfaVerifiee(BasePermission):
    """Session ouverte et second facteur validé pendant cette session."""

    message = "Double authentification requise."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if mfa_verifiee(user):
            return True
        return not mfa_requise(user)


class PermissionsParAction(BasePermission):
    """Vérifie la permission RBAC exigée par l'action appelée.

    Une vue peut déclarer ``permissions_requises = {"list": "app.view_x", "valider": [...]}``
    (par action de ViewSet, ou par méthode HTTP en minuscules). Sinon, la permission standard du
    modèle est déduite de la méthode (view, add, change, delete). Si rien ne permet de la
    déterminer, l'accès est refusé.
    """

    def _requises(self, request, view):
        declarees = getattr(view, "permissions_requises", None)
        if declarees is not None:
            action = getattr(view, "action", None) or request.method.lower()
            perms = declarees.get(action)
            if perms is None:
                return None
            return [perms] if isinstance(perms, str) else list(perms)

        queryset = getattr(view, "queryset", None)
        if queryset is None and hasattr(view, "get_queryset"):
            try:
                queryset = view.get_queryset()
            except AssertionError:
                queryset = None
        if queryset is None or request.method not in _ACTIONS_PAR_METHODE:
            return None
        meta = queryset.model._meta
        return [f"{meta.app_label}.{_ACTIONS_PAR_METHODE[request.method]}_{meta.model_name}"]

    def has_permission(self, request, view):
        perms = self._requises(request, view)
        return perms is not None and request.user.has_perms(perms)

    def has_object_permission(self, request, view, obj):
        perms = self._requises(request, view)
        return perms is not None and request.user.has_perms(perms, obj)
