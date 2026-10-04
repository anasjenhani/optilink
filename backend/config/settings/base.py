"""Réglages communs à tous les environnements.

Tout ce qui varie vient des variables d'environnement.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def env(name, default=None):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    return env(name, str(default)).lower() in ("1", "true", "yes", "on")


def env_list(name, default=""):
    return [item.strip() for item in env(name, default).split(",") if item.strip()]


SECRET_KEY = env("DJANGO_SECRET_KEY", "")
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", "")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "django_otp",
    "django_otp.plugins.otp_totp",
    "django_otp.plugins.otp_static",
    "auditlog",
    "core",
    "apps.securite",
    "apps.reseau",
    "apps.stock",
    "apps.ventes",
    "apps.crm",
    "apps.optique",
    "apps.achats",
    "apps.tresorerie",
    "apps.rh",
    "apps.pilotage",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "auditlog.middleware.AuditlogMiddleware",
    "core.middleware.PerimetreMagasinMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# Base de données : PostgreSQL (pilote psycopg 3).
# DB_ENGINE=sqlite n'est prévu que pour les tests rapides en local.
if env("DB_ENGINE", "postgresql") == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": env("DB_NAME", str(BASE_DIR / "db.sqlite3")),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("DB_NAME", "optilink"),
            "HOST": env("DB_HOST", "localhost"),
            "PORT": env("DB_PORT", "5432"),
            "USER": env("DB_USER", "optilink"),
            "PASSWORD": env("DB_PASSWORD", ""),
            "CONN_MAX_AGE": int(env("DB_CONN_MAX_AGE", "60")),
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": {
                # TLS exigé par défaut ; verify-full en production avec le certificat du serveur,
                # disable uniquement pour la base locale de développement.
                "sslmode": env("DB_SSLMODE", "require"),
            },
        }
    }
    if env("DB_SSLROOTCERT"):
        # Certificat de l'autorité qui a signé celui du serveur PostgreSQL (pour verify-full).
        DATABASES["default"]["OPTIONS"]["sslrootcert"] = env("DB_SSLROOTCERT")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "securite.Utilisateur"
# Les permissions viennent uniquement des rôles des affectations en cours.
AUTHENTICATION_BACKENDS = ["apps.securite.backends.PermissionsParAffectationBackend"]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr-fr"
# Fuseau du serveur (tâches planifiées, journaux) ; chaque magasin a aussi celui de son pays.
TIME_ZONE = env("TIME_ZONE", "Africa/Tunis")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

REDIS_URL = env("REDIS_URL", "redis://localhost:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    }
}

CELERY_BROKER_URL = env("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = None
CELERY_TASK_ACKS_LATE = True
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULE = {
    "desactiver-comptes-inactifs": {
        "task": "apps.securite.tasks.desactiver_comptes_inactifs",
        "schedule": 24 * 60 * 60,
    },
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    # Refus par défaut : session ouverte, MFA validée et permission de l'action.
    "DEFAULT_PERMISSION_CLASSES": [
        "core.permissions.MfaVerifiee",
        "core.permissions.PermissionsParAction",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "connexion": env("THROTTLE_CONNEXION", "10/min"),
        "mfa": env("THROTTLE_MFA", "10/min"),
    },
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "API OptiLink",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "ENUM_NAME_OVERRIDES": {
        "ModePaiementEnum": "apps.ventes.models.Paiement.Mode",
        "StatutPointageEnum": "apps.rh.models.Pointage.Statut",
        "StatutCongeEnum": "apps.rh.models.DemandeConge.Statut",
        "TypeCongeEnum": "apps.rh.models.DemandeConge.Type",
        "StatutAcompteEnum": "apps.rh.models.Acompte.Statut",
        "ModeVersementEnum": "apps.rh.models.Acompte.Mode",
        "StatutPrimeEnum": "apps.rh.models.Prime.Statut",
        "TypePrimeEnum": "apps.rh.models.Prime.Type",
        "StatutPriseEnChargeEnum": "apps.ventes.models.PriseEnCharge.Statut",
        "StatutVenteEnum": "apps.ventes.models.Vente.Statut",
    },
}

# Sécurité : MFA, sessions et comptes.
MFA_OBLIGATOIRE = env_bool("MFA_OBLIGATOIRE", True)
OTP_TOTP_ISSUER = "OptiLink"
COMPTES_INACTIFS_JOURS = int(env("COMPTES_INACTIFS_JOURS", "90"))

# Clés de chiffrement des prescriptions (core/chiffrement.py), séparées par des virgules :
# la première chiffre, les suivantes ne servent qu'à relire pendant une rotation.
PRESCRIPTIONS_CLES = env_list("PRESCRIPTIONS_CLES", "")

# Durée de validité par défaut d'un devis, modifiable devis par devis.
DEVIS_VALIDITE_JOURS = int(env("DEVIS_VALIDITE_JOURS", "30"))

# Acomptes : part du salaire de base qu'un employé peut recevoir en avance chaque mois.
ACOMPTE_PLAFOND_POURCENT = int(env("ACOMPTE_PLAFOND_POURCENT", "50"))
# Alerte de stock : un article suivi en magasin est signalé à ce stock ou en dessous.
STOCK_ALERTE_SEUIL = int(env("STOCK_ALERTE_SEUIL", "1"))

# Journal d'audit : le manager de base évite que le filtre de périmètre masque l'état précédent.
AUDITLOG_USE_BASE_MANAGER = True

SESSION_COOKIE_AGE = int(env("SESSION_DUREE_SECONDES", str(10 * 60 * 60)))
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
