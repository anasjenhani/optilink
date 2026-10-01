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

## Pays : Tunisie d'abord, puis d'autres pays

OptiLink est conçu pour la Tunisie en premier lieu et s'ouvrira à d'autres pays. Rien de propre à un pays n'est écrit dans le code : chaque magasin est rattaché à un **pays** (`reseau.Pays`, modifiable dans l'administration) qui porte :

- la monnaie et son nombre de décimales : dinar tunisien (TND) à 3 décimales, les millimes. Tous les montants sont stockés avec 3 décimales et arrondis à l'unité de la monnaie du magasin ;
- les taux de TVA autorisés (Tunisie : 19 %, 13 %, 7 %) ;
- le droit de timbre ajouté à chaque facture (Tunisie : 1,000 TND), payé avec la vente : `net_a_payer = total_ttc + timbre_fiscal` ;
- le fuseau horaire (année de numérotation des factures), l'indicatif téléphonique, et l'identifiant du prescripteur sur une ordonnance (Tunisie : n° d'inscription à l'Ordre des médecins ; France : n° RPPS à 11 chiffres).

Un article a un prix et un taux de TVA par pays (`PrixArticle`) ; sans prix dans le pays du magasin, il n'y est pas vendable. Une vente garde la devise de son magasin. La Tunisie et la France sont créées à la migration ; un magasin existant est rattaché à la Tunisie. **Taux de TVA et timbre à faire confirmer par le comptable** avant la mise en service.

## Cloisonnement par magasin

Chaque utilisateur reçoit des **affectations** : un rôle (groupe Django) sur une portée, un magasin, une région ou tout le réseau, avec des dates de début et de fin. À chaque requête, `PerimetreMagasinMiddleware` calcule les magasins autorisés, et le manager `ParMagasinManager` filtre automatiquement les requêtes des modèles de magasin. Les tâches Celery et les commandes d'administration ne sont pas filtrées. Pour lire volontairement hors périmètre, utiliser le manager `tous`.

PostgreSQL applique le même cloisonnement de son côté (Row-Level Security, `core/rls.py`) sur les magasins, les ventes, leurs lignes et paiements, les compteurs de factures et les mouvements de stock. Le middleware pose le périmètre dans la session PostgreSQL (`app.perimetre`) au début de chaque requête et l'efface à la fin ; une requête SQL qui oublierait le filtre, ou passerait par le manager `tous`, ne voit et n'écrit donc que les magasins autorisés. Hors requête HTTP (Celery, migrations, commandes), la variable est vide et la base ne filtre pas. La RLS ne s'applique pas à un super-utilisateur PostgreSQL : l'application doit se connecter avec un compte `NOSUPERUSER NOBYPASSRLS`, et `migrate` affiche l'avertissement `optilink.W001` si ce n'est pas le cas.

## Sécurité

- **Rôles et permissions (RBAC).** Les droits viennent uniquement des rôles des affectations en cours (`PermissionsParAffectationBackend`). Les neuf rôles de départ du document d'architecture sont créés au premier `migrate` ; le siège les ajuste ensuite dans l'administration. Sur un objet rattaché à un magasin, seuls les rôles dont le périmètre couvre ce magasin comptent. Côté API, `PermissionsParAction` exige la permission de chaque action (déclarée dans `permissions_requises`, sinon la permission standard du modèle) et refuse tout ce qui n'est pas déclaré.
- **Double authentification (MFA).** Connexion en deux temps : mot de passe, puis code d'une application d'authentification (TOTP) ou un des 10 codes de secours remis à l'activation. Sans MFA validée, l'API ne répond qu'aux routes `/api/v1/auth/`. L'administration Django exige aussi le code. Tentatives limitées par Nginx, par l'API (`THROTTLE_CONNEXION`, `THROTTLE_MFA`) et par django-otp (délai croissant après chaque code faux).
- **Journal d'audit.** django-auditlog enregistre auteur, date, adresse IP, ancienne et nouvelle valeur pour les magasins, régions, comptes (hors mot de passe), affectations et rôles. Les connexions, déconnexions, codes MFA et désactivations sont dans `EvenementSecurite`, qui ne peut être ni modifié ni supprimé. Pour ces deux journaux, le verrou est aussi posé dans PostgreSQL : un déclencheur refuse tout `UPDATE` ou `DELETE`, quelle que soit la requête. Un compte qui a un historique ne se supprime donc pas : on le désactive. Les deux journaux se consultent dans l'administration.
- **Comptes inactifs.** Une tâche Celery quotidienne désactive les comptes sans connexion depuis 90 jours (`COMPTES_INACTIFS_JOURS`), hors super-utilisateurs.

## Prototype caisse et stock

- **Stock** (`apps.stock`) : `Article` (catalogue commun au réseau) et `MouvementStock` ; le stock d'un article dans un magasin est la somme de ses mouvements, jamais modifiés.
- **Ventes** (`apps.ventes`) : `enregistrer_vente` écrit dans une seule transaction la vente, ses lignes, les sorties de stock, les paiements et le numéro de facture. Numérotation sans trou par magasin et par année (`M01-2026-000001`) : le compteur est verrouillé pendant la transaction et un échec annule aussi l'incrément.
- Contrôles : stock suffisant, paiements égaux au total, droit de vente sur le magasin choisi, remise réservée aux rôles qui ont `ventes.appliquer_remise`.
- API : `/api/v1/articles/?magasin=…&recherche=…`, `/api/v1/ventes/`, `/api/v1/mouvements-stock/` (réceptions et ajustements).
- Essai rapide : `python manage.py charger_demo` crée quelques articles avec un prix en Tunisie (TND) et en France, et 10 unités de chacun dans chaque magasin actif qui n'en a pas encore.

La caisse suppose une liaison permanente avec le serveur (lien de secours 4G recommandé) ; un mode hors ligne changerait la numérotation et la gestion du stock.

## Clients et ordonnances

- **Clients** (`apps.crm`) : fiche commune à tout le réseau (un client achète partout), magasin d'origine conservé, consentement aux relances. Pas de suppression : on désactive. API `/api/v1/clients/?recherche=…` (nom, prénom, téléphone, e-mail).
- **Ordonnances** (`apps.optique`) : `Prescription` datée, avec prescripteur et n° RPPS, mesures œil droit / œil gauche (sphère, cylindre, axe, addition ; rayon et diamètre pour les lentilles) et écart pupillaire. Une ordonnance ne se modifie pas : une correction est une nouvelle saisie. Elle suit le client dans tout le réseau.
- **Données de santé.** Les mesures sont chiffrées par l'application avant d'arriver en base (`core/chiffrement.py`, clés `PRESCRIPTIONS_CLES` hors de la base) : une copie de la base ou d'une sauvegarde ne les révèle pas. Seuls les rôles Opticien et Responsable magasin les voient. Chaque consultation et chaque saisie est inscrite dans `AccesPrescription`, verrouillé en ajout seul dans PostgreSQL ; la direction peut consulter ce journal. L'API ne liste les ordonnances que client par client (`/api/v1/prescriptions/?client=…`).
- **Clé de chiffrement.** À générer une fois (voir `.env.example`) et à sauvegarder hors du serveur : sans elle, les ordonnances sont illisibles, y compris depuis une sauvegarde. Rotation : mettre la nouvelle clé en premier, garder l'ancienne derrière.

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

La base de développement tourne dans le conteneur `postgres`, sur le port 5432 de la machine locale uniquement. Au premier démarrage, `docker/postgres/01-compte-applicatif.sh` y crée le compte applicatif `DB_USER` (non super-utilisateur, pour que la Row-Level Security s'applique). Ce script ne tourne que sur un volume vide : une base de développement créée avant ce changement se recrée avec `docker compose -f docker-compose.yml -f docker-compose.dev.yml down -v`.

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

1. PostgreSQL 17 sur son serveur dédié, avec une base `optilink` et un compte applicatif propriétaire de cette base, créé `NOSUPERUSER NOBYPASSRLS` (le script `docker/postgres/01-compte-applicatif.sh` montre les commandes). Avec le super-utilisateur `postgres`, la Row-Level Security serait ignorée.
2. `.env` avec une vraie `DJANGO_SECRET_KEY`, `DB_HOST` pointant vers le serveur PostgreSQL, `DB_USER`/`DB_PASSWORD` du compte applicatif.
3. Certificat TLS dans `certs/optilink.crt` et `certs/optilink.key`.
4. `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`

Nginx redirige HTTP vers HTTPS (TLS 1.2 minimum, HSTS). La connexion Django vers PostgreSQL exige TLS (`DB_SSLMODE=require` par défaut) ; en production, utiliser `DB_SSLMODE=verify-full` avec `DB_SSLROOTCERT` (certificat de l'autorité, monté dans le conteneur) pour vérifier aussi le certificat du serveur.

## Suite

- Reprise rapide par code PIN sur le poste de caisse
- Notification de la direction à chaque changement de rôle ou d'affectation
- Interface en arabe (écriture de droite à gauche) et en anglais
- Lot Vendre, suite : client sur la vente, devis, avoirs et retours, tables spécialisées par famille d'article, export et anonymisation RGPD d'un client
