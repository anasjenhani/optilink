# OptiLink

CRM/ERP centralisée pour la chaîne de magasins d'optique : ventes, stock, clients, dossiers optiques, achats, finance, RH et pilotage du réseau, hébergée sur vos serveurs.

L'architecture complète est décrite dans le document d'architecture OptiLink. Ce dépôt en est le lot 1, le socle.

## Stack

| Couche | Technologies |
| --- | --- |
| Frontend | React, TypeScript, Material UI, TanStack Query, Vite |
| Backend | Python 3.12, Django 5.2 LTS, Django REST Framework |
| Base de données | SQL Server 2022 (pilote `mssql-django`, ODBC Driver 18) |
| Cache et traitements | Redis, Celery (worker et Beat) |
| Infrastructure | Docker Compose, Nginx, HTTPS |

## Organisation

```
backend/
  config/        réglages (dev, test, prod), URLs, Celery
  core/          noyau partagé : périmètre magasin, modèle de base, santé
  apps/reseau/   régions et magasins
  apps/securite/ utilisateurs et affectations (rôle + périmètre)
  tests/         tests pytest
frontend/
  src/           application React
  nginx/         configurations HTTP (dev) et HTTPS (production)
```

## Cloisonnement par magasin

Chaque utilisateur reçoit des **affectations** : un rôle (groupe Django) sur une portée, un magasin, une région ou tout le réseau, avec des dates de début et de fin. À chaque requête, `PerimetreMagasinMiddleware` calcule les magasins autorisés, et le manager `ParMagasinManager` filtre automatiquement les requêtes des modèles de magasin. Les tâches Celery et les commandes d'administration ne sont pas filtrées. Pour lire volontairement hors périmètre, utiliser le manager `tous`.

## Sécurité

- **Rôles et permissions (RBAC).** Les droits viennent uniquement des rôles des affectations en cours (`PermissionsParAffectationBackend`). Les neuf rôles de départ du document d'architecture sont créés au premier `migrate` ; le siège les ajuste ensuite dans l'administration. Sur un objet rattaché à un magasin, seuls les rôles dont le périmètre couvre ce magasin comptent. Côté API, `PermissionsParAction` exige la permission de chaque action (déclarée dans `permissions_requises`, sinon la permission standard du modèle) et refuse tout ce qui n'est pas déclaré.
- **Double authentification (MFA).** Connexion en deux temps : mot de passe, puis code d'une application d'authentification (TOTP) ou un des 10 codes de secours remis à l'activation. Sans MFA validée, l'API ne répond qu'aux routes `/api/v1/auth/`. L'administration Django exige aussi le code. Tentatives limitées par Nginx, par l'API (`THROTTLE_CONNEXION`, `THROTTLE_MFA`) et par django-otp (délai croissant après chaque code faux).
- **Journal d'audit.** django-auditlog enregistre auteur, date, adresse IP, ancienne et nouvelle valeur pour les magasins, régions, comptes (hors mot de passe), affectations et rôles. Les connexions, déconnexions, codes MFA et désactivations sont dans `EvenementSecurite`, que l'application ne peut ni modifier ni supprimer. Les deux se consultent dans l'administration.
- **Comptes inactifs.** Une tâche Celery quotidienne désactive les comptes sans connexion depuis 90 jours (`COMPTES_INACTIFS_JOURS`), hors super-utilisateurs.

## Démarrer en développement

Prérequis : Docker avec Docker Compose.

```bash
cp .env.example .env        # puis modifier les mots de passe
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec backend python manage.py createsuperuser
```

Premier accès : se connecter à l'application avec le compte créé, scanner le QR code avec une application d'authentification (Google Authenticator, Microsoft Authenticator, FreeOTP…), puis conserver les codes de secours. L'administration Django n'est accessible qu'après cette activation. Donner ensuite à chaque compte une affectation (rôle + magasin, région ou réseau) ; le super-utilisateur ne sert qu'à l'amorçage.

- Application : http://localhost
- Administration Django : http://localhost/admin/
- Documentation de l'API : http://localhost/api/docs/
- État de la plateforme : http://localhost/api/v1/sante/

Le mot de passe SQL Server (`DB_PASSWORD`) doit respecter la politique de SQL Server : au moins 8 caractères avec majuscules, minuscules, chiffres et symboles.

### Sans Docker

```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
DB_ENGINE=sqlite python manage.py migrate
DB_ENGINE=sqlite python manage.py runserver

cd ../frontend
npm install
npm run dev                 # http://localhost:5173, relaie /api vers Django
```

SQLite ne sert qu'aux essais rapides ; la CI teste sur SQL Server.

## Tests et contrôles

```bash
cd backend && DB_ENGINE=sqlite pytest && ruff check . && ruff format --check .
cd frontend && npm run typecheck && npm test && npm run build
```

La CI GitHub Actions lance les tests backend sur un vrai SQL Server 2022, les contrôles frontend, puis construit les deux images Docker.

## Production

1. SQL Server sur son serveur dédié, avec une base `optilink` et un compte applicatif propre (pas `sa`).
2. `.env` avec une vraie `DJANGO_SECRET_KEY`, `DB_HOST` pointant vers le serveur SQL, `DB_USER`/`DB_PASSWORD` du compte applicatif.
3. Certificat TLS dans `certs/optilink.crt` et `certs/optilink.key`.
4. `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`

Nginx redirige HTTP vers HTTPS (TLS 1.2 minimum, HSTS). La connexion Django vers SQL Server est chiffrée ; le certificat du serveur SQL est vérifié sauf si `DB_TRUST_SERVER_CERTIFICATE=1`.

## Suite du lot 1

- Row-Level Security SQL Server en complément du filtre applicatif, et droits SQL empêchant la modification des journaux
- Reprise rapide par code PIN sur le poste de caisse
- Notification de la direction à chaque changement de rôle ou d'affectation
- Prototype caisse et stock pour valider Django sur SQL Server
