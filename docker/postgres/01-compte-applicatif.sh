#!/bin/sh
# Premier démarrage du PostgreSQL de développement : crée le compte applicatif et sa base.
# Ce compte n'est pas super-utilisateur, sinon PostgreSQL ignorerait la Row-Level Security.
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
    -v app_user="$APP_DB_USER" -v app_password="$APP_DB_PASSWORD" -v app_db="$APP_DB_NAME" <<'SQL'
CREATE ROLE :"app_user" LOGIN NOSUPERUSER NOBYPASSRLS CREATEDB PASSWORD :'app_password';
CREATE DATABASE :"app_db" OWNER :"app_user";
SQL
