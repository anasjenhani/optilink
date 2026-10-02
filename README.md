# OptiLink

CRM/ERP centralisée pour la chaîne de magasins d'optique : ventes, stock, clients, dossiers optiques, achats, finance, RH et pilotage du réseau, hébergée sur vos serveurs.

L'architecture complète est décrite dans le document d'architecture OptiLink. Ce dépôt en est le lot 1, le socle.

## Stack

| Couche | Technologies |
| --- | --- |
| Frontend | React, TypeScript, Material UI, TanStack Query, Vite |
| Backend | Python 3.12, Django 5.2 LTS, Django REST Framework |
| Base de données | PostgreSQL 17 (pilote `psycopg` 3) |
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

## Prototype caisse et stock

- **Stock** (`apps.stock`) : `Article` (catalogue commun au réseau) et `MouvementStock` ; le stock d'un article dans un magasin est la somme de ses mouvements, jamais modifiés.
- **Ventes** (`apps.ventes`) : `enregistrer_vente` écrit dans une seule transaction la vente, ses lignes, les sorties de stock, les paiements et le numéro de facture. Numérotation sans trou par magasin et par année (`M01-2026-000001`) : le compteur est verrouillé pendant la transaction et un échec annule aussi l'incrément.
- Contrôles : stock suffisant, paiements égaux au total, droit de vente sur le magasin choisi, remise réservée aux rôles qui ont `ventes.appliquer_remise`.
- API : `/api/v1/articles/?magasin=…&recherche=…`, `/api/v1/ventes/`, `/api/v1/mouvements-stock/` (réceptions et ajustements).
- Essai rapide : `python manage.py charger_demo` crée quelques articles et 10 unités de chacun dans chaque magasin actif.

La caisse suppose une liaison permanente avec le serveur (lien de secours 4G recommandé) ; un mode hors ligne changerait la numérotation et la gestion du stock.

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

La base de développement tourne dans le conteneur `postgres`, sur le port 5432 de la machine locale uniquement.

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

SQLite ne sert qu'aux essais rapides ; la CI teste sur PostgreSQL.

## Tests et contrôles

```bash
cd backend && DB_ENGINE=sqlite pytest && ruff check . && ruff format --check .
cd frontend && npm run typecheck && npm test && npm run build
```

La CI GitHub Actions lance les tests backend sur un vrai PostgreSQL 17, les contrôles frontend, puis construit les deux images Docker.

## Production

1. PostgreSQL 17 sur son serveur dédié, avec une base `optilink` et un compte applicatif propriétaire de cette base (pas le super-utilisateur `postgres`).
2. `.env` avec une vraie `DJANGO_SECRET_KEY`, `DB_HOST` pointant vers le serveur PostgreSQL, `DB_USER`/`DB_PASSWORD` du compte applicatif.
3. Certificat TLS dans `certs/optilink.crt` et `certs/optilink.key`.
4. `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`

Nginx redirige HTTP vers HTTPS (TLS 1.2 minimum, HSTS). La connexion Django vers PostgreSQL exige TLS (`DB_SSLMODE=require` par défaut) ; en production, utiliser `DB_SSLMODE=verify-full` avec `DB_SSLROOTCERT` (certificat de l'autorité, monté dans le conteneur) pour vérifier aussi le certificat du serveur.

## Suite du lot 1

- Row-Level Security PostgreSQL en complément du filtre applicatif, et droits SQL empêchant la modification des journaux
- Reprise rapide par code PIN sur le poste de caisse
- Notification de la direction à chaque changement de rôle ou d'affectation
- Lot Vendre : clients, dossiers optiques, devis, avoirs, tables spécialisées par famille d'article
