from .base import *  # noqa: F403
from .base import DATABASES, env

SECRET_KEY = "tests"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
CELERY_TASK_ALWAYS_EAGER = True

if env("DB_ENGINE", "mssql") == "sqlite":
    DATABASES["default"]["NAME"] = ":memory:"
