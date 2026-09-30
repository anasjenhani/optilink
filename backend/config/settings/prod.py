from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import SECRET_KEY

if not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY doit être défini en production.")

DEBUG = False
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
STORAGES = {
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# La redirection HTTP -> HTTPS est faite par Nginx ; le préchargement HSTS est un choix à faire
# une fois le nom de domaine définitif en place.
SILENCED_SYSTEM_CHECKS = ["security.W008", "security.W021"]
