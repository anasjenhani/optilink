FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
# Avec les réglages de production, pour produire le manifeste des fichiers statiques que
# whitenoise exige (sans lui, l'administration répond 500). Valeurs factices le temps du build.
RUN DJANGO_SETTINGS_MODULE=config.settings.prod DB_ENGINE=sqlite \
    DJANGO_SECRET_KEY=build-seulement PRESCRIPTIONS_CLES=build-seulement \
    python manage.py collectstatic --noinput

RUN useradd --create-home --uid 1000 optilink && chown -R optilink /app
USER optilink

# Nombre de processus Gunicorn, lu par Gunicorn lui-même : 2 suffisent en qualification.
ENV DJANGO_SETTINGS_MODULE=config.settings.prod \
    WEB_CONCURRENCY=3
EXPOSE 8000
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--timeout", "60"]
