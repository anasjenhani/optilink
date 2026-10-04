# Historique des changements

Chaque modification d'OptiLink, de la plus récente à la plus ancienne. Une ligne par
modification fusionnée dans `main`, avec le lien vers son détail sur GitHub (#N).
Toute nouvelle modification ajoute sa ligne sous « En cours » ; la CI le vérifie.

Le détail ligne à ligne de chaque changement reste dans l'historique Git
(`git log`), et les modifications de données faites dans l'application sont
tracées dans le journal d'audit (`auditlog_logentry`).

## En cours

- Schéma de la base de données généré depuis le code (`docs/base-de-donnees.md`, tenu à jour par la CI) et cet historique des changements.

## 2026-10-04

- Suivi des lunettes (étapes de l'atelier), journée de vente, boutons fixes sous le menu, et prise en charge CNAM, assurance ou mutuelle ([#29](https://github.com/anasjenhani/optilink/pull/29)).
- Import des clients depuis un autre logiciel, en Excel ou CSV, avec l'ancien n° de fiche ([#28](https://github.com/anasjenhani/optilink/pull/28)).

## 2026-10-03

- Administration du serveur : tableaux en bleu lapis-lazuli ([#27](https://github.com/anasjenhani/optilink/pull/27)).
- Administration du serveur : onglets horizontaux ([#26](https://github.com/anasjenhani/optilink/pull/26)).
- Navigation par onglets, vente au comptoir en étapes, alertes et reporting dans /admin/ ([#25](https://github.com/anasjenhani/optilink/pull/25)).
- Correctif : erreur 500 sur /admin/ ([#24](https://github.com/anasjenhani/optilink/pull/24)).
- RH : acomptes et primes ([#23](https://github.com/anasjenhani/optilink/pull/23)).
- RH : présence et congés ([#22](https://github.com/anasjenhani/optilink/pull/22)).
- Trésorerie : banque et versements ([#21](https://github.com/anasjenhani/optilink/pull/21)).
- Trésorerie : clôture de caisse quotidienne vérifiée par la finance ([#20](https://github.com/anasjenhani/optilink/pull/20)).
- Accès et sécurité : utilisateurs, profils et privilèges ([#19](https://github.com/anasjenhani/optilink/pull/19)).
- Sociétés à la place des régions ([#18](https://github.com/anasjenhani/optilink/pull/18)).
- Pays : liste de tous les pays du monde ([#17](https://github.com/anasjenhani/optilink/pull/17)).

## 2026-10-02

- Imports Excel et CSV du catalogue et des entrées de stock ; péniche saisie, fournisseur obligatoire ([#15](https://github.com/anasjenhani/optilink/pull/15)).
- Péniches des commandes, fournisseur des articles et douchette en caisse ([#14](https://github.com/anasjenhani/optilink/pull/14)).
- Familles d'articles : fiches monture, verre et lentille, écran Catalogue ([#13](https://github.com/anasjenhani/optilink/pull/13)).
- Fiche client complète : deux téléphones, adresse, société et matricule fiscal ([#12](https://github.com/anasjenhani/optilink/pull/12)).
- Commandes de verres aux fournisseurs : à commander, réception, livraison bloquée ([#11](https://github.com/anasjenhani/optilink/pull/11)).
- Avoirs et annulations : retour d'articles, remboursement, annulation de commande ([#10](https://github.com/anasjenhani/optilink/pull/10)).
- Commandes avec acompte : règlements, livraison contre le solde, verres hors stock ([#9](https://github.com/anasjenhani/optilink/pull/9)).
- Devis d'équipement : prix figés, ordonnance, encaissement au prix du devis ([#8](https://github.com/anasjenhani/optilink/pull/8)).
- Tunisie d'abord, puis multi-pays : monnaie, TVA, ticket et facture à part ([#7](https://github.com/anasjenhani/optilink/pull/7)).
- Fiches clients et ordonnances chiffrées ([#6](https://github.com/anasjenhani/optilink/pull/6)).
- Cloisonnement par magasin dans PostgreSQL et journaux verrouillés en base ([#5](https://github.com/anasjenhani/optilink/pull/5)).
- Base de données : PostgreSQL 17 à la place de SQL Server ([#4](https://github.com/anasjenhani/optilink/pull/4)).
- Prototype caisse et stock : une vente de bout en bout ([#3](https://github.com/anasjenhani/optilink/pull/3)).
- Sécurité du socle : rôles et permissions, MFA, journal d'audit ([#2](https://github.com/anasjenhani/optilink/pull/2)).

## 2026-09-30

- Socle du projet : Django et DRF, React et MUI, Docker, CI ([#1](https://github.com/anasjenhani/optilink/pull/1)).
