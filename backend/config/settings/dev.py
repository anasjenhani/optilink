from .base import *  # noqa: F403
from .base import env, env_list

DEBUG = True
SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-uniquement-ne-pas-utiliser-en-production")
ALLOWED_HOSTS = ["*"]
# Clé de développement uniquement : les données saisies en dev ne sont pas protégées.
PRESCRIPTIONS_CLES = env_list("PRESCRIPTIONS_CLES", "6ruJ7WIZ44u3rQKSLFDUBuHDD8NF8P0TlK2tzI65mj8=")
