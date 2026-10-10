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
docs/
  base-de-donnees.md  schéma de la base, généré depuis les modèles
CHANGELOG.md     historique des changements, une ligne par modification
```

Après toute modification d'un modèle, `python manage.py schema_bd` régénère le schéma de
la base ; la CI échoue s'il n'est plus à jour, et si une modification proposée n'ajoute pas
sa ligne à `CHANGELOG.md`.

## Pays : Tunisie d'abord, puis d'autres pays

OptiLink est conçu pour la Tunisie en premier lieu et s'ouvrira à d'autres pays. Rien de propre à un pays n'est écrit dans le code : chaque magasin est rattaché à un **pays** (`reseau.Pays`, modifiable dans l'administration) qui porte :

- la monnaie et son nombre de décimales : dinar tunisien (TND) à 3 décimales, les millimes. Tous les montants sont stockés avec 3 décimales et arrondis à l'unité de la monnaie du magasin ;
- les taux de TVA (Tunisie : 19 %, 13 %, 7 %), réglés par l'administrateur dans l'administration (rôle Administrateur système) : chaque prix d'article pointe vers un de ces taux, donc modifier un taux s'applique à tous les articles qui l'utilisent ; une vente déjà faite garde le taux appliqué ; chaque modification est tracée dans le journal d'audit ;
- le droit de timbre (Tunisie : 1,000 TND), ajouté **aux factures seulement** et payé par le client : `net_a_payer = total_ttc + timbre_fiscal`. Un ticket de caisse n'en a pas ;
- le fuseau horaire (année de numérotation des factures), l'indicatif téléphonique, et l'identifiant du prescripteur sur une ordonnance (Tunisie : n° d'inscription à l'Ordre des médecins ; France : n° RPPS à 11 chiffres).

Un article a un prix et un taux de TVA par pays (`PrixArticle`) ; sans prix dans le pays du magasin, il n'y est pas vendable. Une vente garde la devise de son magasin. La Tunisie et la France sont créées à la migration ; un magasin existant est rattaché à la Tunisie.

**Ticket, puis facture à part.** La caisse émet un ticket (`M01-T2026-000001`), sans timbre, avec un client facultatif. La facture n'est pas faite en caisse : c'est une étape à part (écran Factures, `POST /api/v1/factures/`), possible seulement quand la vente est **entièrement payée**. Elle est établie au nom d'un client (avec son matricule fiscal s'il s'agit d'une entreprise), numérotée dans sa propre suite (`M01-F2026-000001`) et porte le droit de timbre, payé par le client au moment de la facture. Une vente n'a qu'une facture. Droit `ventes.add_facture` : opticien, responsable de magasin et responsable régional ; le vendeur encaisse mais ne facture pas.

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
- **Familles d'articles** : monture, verre, lentille et divers. Les trois premières ont leur fiche (`Monture` : marque, modèle, couleur, matière, type, genre, calibre □ pont - branche, solaire ; `Verre` : marque, gamme, géométrie, indice, matière, traitements, photochromique, teinte, diamètre ; `Lentille` : marque, modèle, renouvellement, type, rayon, diamètre, puissance, cylindre, axe, addition, nombre par boîte). Les articles divers (étuis, produits d'entretien…) n'ont que leur libellé. Les articles se créent dans l'administration Django, où la fiche de la famille se remplit avec l'article. Chaque article est lié à un fournisseur (obligatoire) et peut porter sa référence chez lui ; l'écran Verres propose ce fournisseur d'office. Le code-barres est unique : la douchette en caisse (code puis Entrée) ajoute l'article au panier. Un verre est « à commander » (`sur_commande`, commandé pour chaque client) ou « de stock » (case décochée : il se vend sur le stock du magasin comme une monture). L'écran Catalogue les liste par famille avec prix et stock du magasin, et la caisse et les devis affichent leurs caractéristiques. API `/api/v1/articles/?famille=…&marque=…&recherche=…` (recherche aussi sur marque, modèle et gamme).
- **Ventes** (`apps.ventes`) : `enregistrer_vente` écrit dans une seule transaction la vente, ses lignes, les sorties de stock, les paiements et le numéro de facture. Numérotation sans trou par magasin et par année (`M01-2026-000001`) : tickets et factures ont chacun leur compteur, verrouillé pendant la transaction et un échec annule aussi l'incrément.
- Contrôles : stock suffisant, paiements égaux au total, droit de vente sur le magasin choisi, remise réservée aux rôles qui ont `ventes.appliquer_remise`.
- API : `/api/v1/articles/?magasin=…&recherche=…`, `/api/v1/ventes/`, `/api/v1/mouvements-stock/` (réceptions et ajustements).
- Essai rapide : `python manage.py charger_demo` crée quelques articles avec un prix en Tunisie (TND) et en France, et 10 unités de chacun dans chaque magasin actif qui n'en a pas encore.

La caisse suppose une liaison permanente avec le serveur (lien de secours 4G recommandé) ; un mode hors ligne changerait la numérotation et la gestion du stock.

## Clients et ordonnances

- **Clients** (`apps.crm`) : fiche commune à tout le réseau (un client achète partout) : civilité, nom, prénom, date de naissance, deux téléphones, e-mail, adresse, magasin d'origine conservé, consentement aux relances. Un client professionnel a en plus le nom de sa société et son matricule fiscal : la facture est alors au nom de la société. La facture recopie nom, adresse et matricule à l'émission, si bien que modifier la fiche ensuite ne la change pas. Pas de suppression : on désactive. API `/api/v1/clients/?recherche=…` (nom, prénom, téléphones, e-mail, société, matricule fiscal).
- **Ordonnances** (`apps.optique`) : `Prescription` datée, avec prescripteur et n° RPPS, mesures œil droit / œil gauche (sphère, cylindre, axe, addition ; rayon et diamètre pour les lentilles) et écart pupillaire. Une ordonnance ne se modifie pas : une correction est une nouvelle saisie. Elle suit le client dans tout le réseau.
- **Données de santé.** Les mesures sont chiffrées par l'application avant d'arriver en base (`core/chiffrement.py`, clés `PRESCRIPTIONS_CLES` hors de la base) : une copie de la base ou d'une sauvegarde ne les révèle pas. Seuls les rôles Opticien et Responsable magasin les voient. Chaque consultation et chaque saisie est inscrite dans `AccesPrescription`, verrouillé en ajout seul dans PostgreSQL ; la direction peut consulter ce journal. L'API ne liste les ordonnances que client par client (`/api/v1/prescriptions/?client=…`).
- **Clé de chiffrement.** À générer une fois (voir `.env.example`) et à sauvegarder hors du serveur : sans elle, les ordonnances sont illisibles, y compris depuis une sauvegarde. Rotation : mettre la nouvelle clé en premier, garder l'ancienne derrière.

## Devis d'équipement

- **Devis** (`ventes.Devis`, écran Devis, `/api/v1/devis/`) : établi au nom d'un client, éventuellement sur une de ses ordonnances, avec monture, verres œil par œil (OD / OG), lentilles ou accessoires. Numéroté dans sa propre suite (`M01-D2026-000001`). Les prix du jour sont figés jusqu'à la date de validité (`DEVIS_VALIDITE_JOURS`, 30 jours par défaut, modifiable devis par devis). Le stock n'est pas vérifié : un devis peut porter sur des verres à commander.
- **Suite du devis.** En cours, puis accepté ou refusé (`/accepter/`, `/refuser/`), puis encaissé (`/encaisser/`) : l'encaissement crée le ticket au **prix du devis**, même si le tarif a changé entre-temps, avec le client du devis ; la facture se génère ensuite comme pour toute vente. Un devis expiré, refusé ou déjà encaissé ne s'encaisse plus.
- **Droits.** Toute l'équipe de vente établit des devis (`ventes.add_devis`) ; une remise exige `ventes.appliquer_remise`, l'encaissement `ventes.add_vente`, le rattachement d'une ordonnance l'accès aux ordonnances. Le vendeur voit qu'un devis existe, pas l'ordonnance associée. Direction et comptable : lecture. Devis et lignes sont cloisonnés par magasin dans PostgreSQL ; les changements de statut sont dans le journal d'audit.

## Commandes avec acompte

- **Commande** : une vente enregistrée en caisse avec `commande: true` (case « Commande » de la caisse, ou « En commande » sur un devis). Le client verse un acompte, éventuellement nul ; la vente reste « en commande » avec son reste à payer et une date de livraison prévue.
- **Articles sur commande** (`Article.sur_commande`, les verres par défaut) : commandés au fournisseur pour chaque client, ils n'ont pas de stock. Une vente qui en contient est forcément une commande. Les autres articles (monture…) sortent du stock dès la commande.
- **Règlements et livraison** (écran Commandes) : `POST /api/v1/ventes/{id}/reglement/` encaisse un règlement sans dépasser le reste ; `POST /api/v1/ventes/{id}/livrer/` remet l'équipement et exige le solde, encaissé au plus tard à ce moment-là. Chaque paiement garde sa date et la personne qui l'a reçu. La facture reste possible seulement une fois la vente soldée.

## Avoirs et annulations

- **Avoir** (`ventes.Avoir`, écran Avoirs, `POST /api/v1/avoirs/`) : une vente et sa facture ne sont jamais modifiées ; l'avoir les corrige, avec sa propre suite de numéros (`M01-A2026-000001`). Il reprend des articles d'une vente livrée, ligne par ligne et quantité par quantité, avec un motif obligatoire. Le client est remboursé de leur prix (mode de remboursement exigé). Chaque article repris revient en stock, sauf s'il est défectueux (case décochée) ou fait sur commande.
- **Annulation** (`annulation: true`) : avoir sur tout ce qui n'a pas encore été repris ; la vente passe à « annulée ». Une commande non livrée ne peut qu'être annulée en entier : le client récupère ses acomptes (jamais plus que ce qu'il a versé) et la monture revient en stock.
- **Règles.** Une vente qui a un avoir ne se facture plus ; si elle était déjà facturée, l'avoir porte le n° de la facture. Une commande annulée n'accepte plus de règlement. Droit `ventes.add_avoir` : responsables de magasin et régionaux ; direction et comptable en lecture. Avoirs et lignes cloisonnés par magasin dans PostgreSQL.

## Imports Excel et CSV

L'écran Imports charge un fichier Excel (`.xlsx`) ou CSV (séparateur `;` ou `,`). La première ligne nomme les colonnes ; casse, accents et espaces ne comptent pas. Un bouton télécharge le modèle de chaque import. La vérification est obligatoire : « 1. Vérifier » contrôle le fichier sans rien enregistrer et signale en alerte les articles déjà au catalogue (avec leur stock par magasin) ou déjà en stock dans le magasin (stock avant et après l'entrée). « 2. Importer » n'est possible qu'ensuite : l'API exige le jeton rendu par la vérification de ce même fichier (signature du contenu, du magasin et du bon). L'import est tout ou rien : à la moindre ligne en erreur, rien n'est enregistré et chaque ligne fautive est signalée avec son numéro.

- **Catalogue** (`POST /api/v1/imports/catalogue/`, droits article et prix) : une ligne par article, créé ou mis à jour par `reference`. Colonnes obligatoires : `reference`, `libelle`, `famille` (monture, verre, lentille, divers), `fournisseur` (nom d'un fournisseur déjà créé). Facultatives : `reference_fournisseur`, `code_barres`, `sur_commande` (oui/non ; un verre est à commander par défaut), `prix_ttc` et `tva` (taux du pays, Tunisie par défaut), et les caractéristiques de la famille sous le nom de leur champ (`marque`, `modele`, `calibre`, `geometrie`, `indice`, `renouvellement`…). Les valeurs à choix acceptent le libellé (« Progressif », « Cerclée »).
- **Entrées de stock** (`POST /api/v1/imports/stock/`, droit `stock.add_mouvementstock` sur le magasin) : une ligne par article reçu, `code_barres` ou `reference`, et `quantite`. Le n° du bon de livraison est recopié sur chaque entrée. Un verre à commander n'a pas de stock et est refusé.

## Péniches

Chaque commande est rangée dans une **péniche**, un bac numéroté de 1 à `Magasin.nombre_peniches` (200 par défaut, réglable par magasin dans l'administration). Le vendeur saisit le numéro de la péniche à chaque commande (caisse ou devis) ; une péniche inexistante ou déjà occupée est refusée. Une vente remise tout de suite n'en prend pas. Une péniche ne contient qu'une commande en cours, ce que la base garantit par une contrainte. Elle se libère à la livraison ou à l'annulation, et la vente garde son numéro dans l'historique. L'écran Commandes retrouve une commande par sa péniche (`/api/v1/ventes/?peniche=17`), et l'écran Verres l'affiche à côté de chaque verre à commander.

## Commandes de verres aux fournisseurs

- **Fournisseurs** (`apps.achats`, saisis dans l'administration) : communs au réseau, rattachés à un pays.
- **Verres à commander** (écran du même nom, `GET /api/v1/commandes-fournisseurs/a-commander/?magasin=…`) : les lignes « sur commande » des commandes clients du magasin qui ne sont pas encore commandées.
- **Commande fournisseur** (`POST /api/v1/commandes-fournisseurs/`) : un fournisseur, une référence, et pour chaque verre les détails à transmettre (œil, correction, traitement). Numérotée `M01-C2026-000001`. Elle se réceptionne (`/receptionner/`) ou s'annule (`/annuler/`) ; annulée, ses verres repassent à commander.
- **Livraison client.** Une commande client ne se livre qu'une fois tous ses verres reçus ; l'API et l'écran Commandes indiquent où ils en sont (`verres` : à commander, commandés, reçus).
- **Droits.** Opticien, responsables et logisticien commandent et réceptionnent ; responsables et logisticien tiennent la liste des fournisseurs ; direction et comptable consultent. Commandes et lignes cloisonnées par magasin dans PostgreSQL.

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

## Qualification

Environnement d'essai sur **un seul serveur** (2 cœurs, 4 Go de mémoire, 80 Go SSD ; 8 Go conseillés pour les gros imports), PostgreSQL compris. Mêmes images et même sécurité que la production (HTTPS, MFA, Row-Level Security), ressources réduites :

| Conteneur | Réglage qualification | Mémoire max |
|---|---|---|
| postgres | `shared_buffers` 256 Mo, 40 connexions, non exposé hors de Docker | 1 Go |
| backend | 2 processus Gunicorn (`WEB_CONCURRENCY`) | 768 Mo |
| worker | 1 processus Celery qui porte aussi le planificateur (`-B`) ; pas de conteneur `beat` | 512 Mo |
| redis | 64 Mo de données | 128 Mo |
| web | Nginx HTTPS | 128 Mo |
| sauvegarde | `pg_dump` chaque nuit à 2 h dans `./sauvegardes`, gardé 7 jours | 128 Mo |

1. `.env` comme en production, avec en plus `POSTGRES_ADMIN_PASSWORD` (super-utilisateur réservé à l'administration et aux sauvegardes). Utiliser des secrets différents de la production.
2. Certificat : pour un réseau interne, un certificat auto-signé suffit :
   `openssl req -x509 -newkey rsa:2048 -nodes -days 825 -subj "/CN=optilink-qualif" -addext "subjectAltName=DNS:optilink-qualif" -keyout certs/optilink.key -out certs/optilink.crt`
3. `docker compose -f docker-compose.yml -f docker-compose.qualif.yml up -d --build`
4. `docker compose -f docker-compose.yml -f docker-compose.qualif.yml exec backend python manage.py createsuperuser`, puis créer pays, magasin, fournisseurs et comptes dans l'administration (`charger_demo` ajoute des articles d'essai).

### Avec Vagrant (VirtualBox ou VMware Workstation)

Le `Vagrantfile` crée la machine virtuelle dans VirtualBox, ou dans VMware Workstation avec `--provider vmware_desktop` (Ubuntu 24.04, 2 cœurs, 4 Go, carte « Bridged » à adresse fixe) et y lance `scripts/provision-qualification.sh`, qui installe Docker depuis son dépôt officiel, génère les secrets (`.env`) et un certificat auto-signé, ouvre le pare-feu (SSH, 80, 443) et démarre OptiLink. Le script se relance sans risque (`vagrant provision`) : secrets et certificat sont gardés. Il sert aussi sur un Ubuntu installé à la main : `sudo OPTILINK_SOURCE=. OPTILINK_IP=192.168.1.50 bash scripts/provision-qualification.sh`.

1. Sur le PC Windows : `winget install --id Oracle.VirtualBox -e` et `winget install --id Hashicorp.Vagrant -e`, puis redémarrage. Avec VMware Workstation à la place de VirtualBox : `winget install --id Hashicorp.VagrantVMwareUtility -e` et `vagrant plugin install vagrant-vmware-desktop`.
2. Dans le dossier d'OptiLink : `$env:OPTILINK_IP = "192.168.1.50"` (une adresse libre du réseau du magasin), puis `vagrant up --provider virtualbox`. Vagrant demande sur quelle carte réseau du PC faire le pont.
3. `vagrant ssh`, puis `cd /opt/optilink && sudo docker compose -f docker-compose.yml -f docker-compose.qualif.yml exec backend python manage.py createsuperuser`.
4. OptiLink répond sur `https://<adresse>` ; le navigateur signale le certificat auto-signé, à accepter (ou à installer sur les postes).

Restaurer une sauvegarde : `docker compose -f docker-compose.yml -f docker-compose.qualif.yml exec -T postgres pg_restore -U postgres -d optilink --clean --if-exists < sauvegardes/optilink-AAAA-MM-JJ.dump`. Copier régulièrement `./sauvegardes` sur un autre support, et garder `PRESCRIPTIONS_CLES` hors du serveur.

### États de la base pour les essais

Tous les scripts à lancer à la main sont rangés dans `scripts/`, chacun expliqué dans `scripts/README.md`.

`./scripts/etats-base.sh` photographie la base sous un nom et la remet dans n'importe quel état enregistré, pour rejouer un essai à partir des mêmes données :

```bash
./scripts/etats-base.sh sauver avant-essai-caisse "catalogue et 3 clients"
./scripts/etats-base.sh lister
./scripts/etats-base.sh restaurer avant-essai-caisse
./scripts/etats-base.sh supprimer avant-essai-caisse
```

Les états vont dans `./sauvegardes/etats`. Une restauration arrête l'application quelques secondes et photographie d'abord l'état courant (`avant-restauration-<date>`), ce qui permet de l'annuler. Les comptes, mots de passe et MFA reviennent eux aussi à l'état restauré.

## Suite

- Reprise rapide par code PIN sur le poste de caisse
- Notification de la direction à chaque changement de rôle ou d'affectation
- Interface en arabe (écriture de droite à gauche) et en anglais
- Lot Vendre, suite : export et anonymisation RGPD d'un client
