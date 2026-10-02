FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN DJANGO_SETTINGS_MODULE=config.settings.dev DB_ENGINE=sqlite \
    python manage.py collectstatic --noinput

RUN useradd --create-home --uid 1000 optilink && chown -R optilink /app
USER optilink

ENV DJANGO_SETTINGS_MODULE=config.settings.prod
EXPOSE 8000
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
