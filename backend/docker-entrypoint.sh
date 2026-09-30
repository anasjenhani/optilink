#!/bin/sh
set -e

# Seul le conteneur API applique les migrations (RUN_MIGRATIONS=1), pas les workers.
if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
    python manage.py migrate --noinput
fi

exec "$@"
