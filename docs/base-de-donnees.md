# Schéma de la base de données

<!-- Fichier généré par `python manage.py schema_bd` : ne pas modifier à la main. -->

Base PostgreSQL d'OptiLink, une section par module. Chaque table a en général
`public_id` (identifiant exposé par l'API), `cree_le` et `modifie_le`. Une table
d'un autre module apparaît dans un diagramme par ses seuls liens, sans ses colonnes.

Les modifications de données (qui, quand, avant et après) sont conservées dans
`auditlog_logentry` ; l'historique des versions du logiciel est dans `CHANGELOG.md`.

## Sommaire

- [Sécurité](#securite) (3 tables)
- [Réseau de magasins](#reseau) (4 tables)
- [Stock](#stock) (6 tables)
- [Ventes](#ventes) (11 tables)
- [Clients](#crm) (2 tables)
- [Dossiers optiques](#optique) (2 tables)
- [Achats](#achats) (3 tables)
- [Trésorerie](#tresorerie) (4 tables)
- [Ressources humaines](#rh) (5 tables)
- [Alertes et reporting](#pilotage) (2 tables)

<a id="securite"></a>

## Sécurité

| Table | Contenu | Colonnes |
| --- | --- | --- |
| `securite_affectation` | Affectation : Un rôle donné à un utilisateur sur un périmètre, pour une période. | 8 |
| `securite_evenementsecurite` | Événement de sécurité : Journal des connexions et opérations MFA, en ajout seul. | 8 |
| `securite_utilisateur` | Utilisateur : Compte OptiLink. Les droits viennent des affectations (rôle + périmètre). | 11 |

```mermaid
erDiagram
    securite_Affectation {
        bigint id PK "ID"
        bigint utilisateur_id FK "utilisateur"
        int role_id FK "role"
        varchar portee "portee"
        bigint magasin_id FK "magasin"
        bigint societe_id FK "société"
        date debut "debut"
        date fin "fin"
    }
    securite_EvenementSecurite {
        bigint id PK "ID"
        timestamptz horodatage "horodatage"
        varchar type "type"
        bigint utilisateur_id FK "utilisateur"
        varchar identifiant "identifiant"
        inet adresse_ip "adresse ip"
        varchar agent_utilisateur "agent utilisateur"
        varchar details "details"
    }
    securite_Utilisateur {
        bigint id PK "ID"
        varchar password "mot de passe"
        timestamptz last_login "dernière connexion"
        bool is_superuser "statut super-utilisateur"
        varchar username UK "nom d’utilisateur"
        varchar first_name "prénom"
        varchar last_name "nom"
        varchar email "adresse électronique"
        bool is_staff "statut équipe"
        bool is_active "actif"
        timestamptz date_joined "date d’inscription"
    }
    securite_Utilisateur ||--o{ securite_Affectation : "utilisateur"
    auth_Group ||--o{ securite_Affectation : "role"
    reseau_Magasin |o--o{ securite_Affectation : "magasin"
    reseau_Societe |o--o{ securite_Affectation : "societe"
    securite_Utilisateur |o--o{ securite_EvenementSecurite : "utilisateur"
    securite_Utilisateur }o--o{ auth_Group : "groups"
    securite_Utilisateur }o--o{ auth_Permission : "user_permissions"
```

<a id="reseau"></a>

## Réseau de magasins

| Table | Contenu | Colonnes |
| --- | --- | --- |
| `reseau_magasin` | Magasin | 14 |
| `reseau_pays` | Pays : Paramètres propres à un pays : monnaie, fiscalité, formats. | 11 |
| `reseau_societe` | Société : Société qui exploite un ou plusieurs magasins : identité légale, coordonnées, logo. | 28 |
| `reseau_tauxtva` | Taux de tva | 4 |

```mermaid
erDiagram
    reseau_Magasin {
        bigint id PK "ID"
        uuid public_id UK "public id"
        timestamptz cree_le "cree le"
        timestamptz modifie_le "modifie le"
        varchar code UK "code"
        varchar nom "nom"
        bigint societe_id FK "société"
        bigint pays_id FK "pays"
        varchar adresse "adresse"
        varchar code_postal "code postal"
        varchar ville "ville"
        varchar telephone "telephone"
        smallint nombre_peniches "nombre de péniches"
        bool est_actif "est actif"
    }
    reseau_Pays {
        bigint id PK "ID"
        varchar code_numerique UK "code ISO"
        varchar code UK "code alpha-2"
        varchar nom "nom"
        varchar devise "devise"
        smallint decimales "decimales"
        varchar fuseau_horaire "fuseau horaire"
        varchar indicatif_telephonique "indicatif telephonique"
        numeric timbre_fiscal "timbre fiscal"
        varchar libelle_identifiant_prescripteur "libelle identifiant prescripteur"
        varchar format_identifiant_prescripteur "format identifiant prescripteur"
    }
    reseau_Societe {
        bigint id PK "ID"
        uuid public_id UK "public id"
        timestamptz cree_le "cree le"
        timestamptz modifie_le "modifie le"
        varchar code UK "code"
        varchar raison_sociale "raison sociale"
        varchar responsable "responsable"
        varchar forme_juridique "forme juridique"
        varchar matricule_fiscal "matricule fiscal"
        varchar registre_commerce "registre de commerce"
        varchar numero_cnss "n° CNSS"
        varchar banque "banque"
        varchar rib "RIB bancaire"
        text adresse "adresse"
        varchar code_postal "code postal"
        varchar ville "ville"
        bigint pays_id FK "pays"
        varchar telephone_1 "téléphone 1"
        varchar telephone_2 "téléphone 2"
        varchar fax "fax"
        varchar email "e-mail"
        varchar site_web "site web"
        varchar facebook "facebook"
        text observation "observation"
        varchar code_douane "code douane"
        varchar carte_sejour "carte de séjour"
        bytea logo "logo"
        varchar logo_type "logo type"
    }
    reseau_TauxTva {
        bigint id PK "ID"
        bigint pays_id FK "pays"
        numeric taux "taux"
        varchar libelle "libelle"
    }
    reseau_Societe ||--o{ reseau_Magasin : "societe"
    reseau_Pays ||--o{ reseau_Magasin : "pays"
    reseau_Pays |o--o{ reseau_Societe : "pays"
    reseau_Pays ||--o{ reseau_TauxTva : "pays"
```

<a id="stock"></a>

## Stock

| Table | Contenu | Colonnes |
| --- | --- | --- |
| `stock_article` | Article : Article du catalogue, commun à tout le réseau ; son prix dépend du pays (``PrixArticle``). | 12 |
| `stock_lentille` | Caractéristiques de la lentille | 12 |
| `stock_monture` | Caractéristiques de la monture | 11 |
| `stock_mouvementstock` | Mouvement de stock : Entrée ou sortie d'un article dans un magasin. Le stock est la somme des mouvements. | 8 |
| `stock_prixarticle` | Prix de vente : Prix de vente d'un article dans un pays, dans la monnaie de ce pays, et son taux de TVA. | 5 |
| `stock_verre` | Caractéristiques du verre | 10 |

```mermaid
erDiagram
    stock_Article {
        bigint id PK "ID"
        uuid public_id UK "public id"
        timestamptz cree_le "cree le"
        timestamptz modifie_le "modifie le"
        varchar reference UK "reference"
        varchar libelle "libelle"
        varchar famille "famille"
        varchar code_barres "code barres"
        bigint fournisseur_id FK "fournisseur"
        varchar reference_fournisseur "reference fournisseur"
        bool sur_commande "sur commande"
        bool est_actif "est actif"
    }
    stock_Lentille {
        varchar marque "marque"
        bigint article_id PK,FK "article"
        varchar modele "modèle"
        varchar renouvellement "renouvellement"
        varchar type "type"
        numeric rayon "rayon"
        numeric diametre "diamètre"
        numeric puissance "puissance"
        numeric cylindre "cylindre"
        smallint axe "axe"
        numeric addition "addition"
        smallint lentilles_par_boite "lentilles par boite"
    }
    stock_Monture {
        varchar marque "marque"
        bigint article_id PK,FK "article"
        varchar modele "modèle"
        varchar couleur "couleur"
        varchar matiere "matière"
        varchar type "type"
        varchar genre "genre"
        smallint calibre "calibre"
        smallint pont "pont"
        smallint branche "branche"
        bool solaire "solaire"
    }
    stock_MouvementStock {
        bigint id PK "ID"
        bigint magasin_id FK "magasin"
        bigint article_id FK "article"
        int quantite "quantite"
        varchar type "type"
        timestamptz horodatage "horodatage"
        bigint utilisateur_id FK "utilisateur"
        varchar reference "reference"
    }
    stock_PrixArticle {
        bigint id PK "ID"
        bigint article_id FK "article"
        bigint pays_id FK "pays"
        numeric prix_vente_ttc "prix vente ttc"
        bigint tva_id FK "TVA"
    }
    stock_Verre {
        varchar marque "marque"
        bigint article_id PK,FK "article"
        varchar gamme "gamme"
        varchar geometrie "géométrie"
        numeric indice "indice"
        varchar matiere "matière"
        varchar traitements "traitements"
        bool photochromique "photochromique"
        varchar teinte "teinte"
        smallint diametre "diamètre"
    }
    achats_Fournisseur |o--o{ stock_Article : "fournisseur"
    stock_Article ||--|| stock_Lentille : "article"
    stock_Article ||--|| stock_Monture : "article"
    reseau_Magasin ||--o{ stock_MouvementStock : "magasin"
    stock_Article ||--o{ stock_MouvementStock : "article"
    securite_Utilisateur |o--o{ stock_MouvementStock : "utilisateur"
    stock_Article ||--o{ stock_PrixArticle : "article"
    reseau_Pays ||--o{ stock_PrixArticle : "pays"
    reseau_TauxTva ||--o{ stock_PrixArticle : "tva"
    stock_Article ||--|| stock_Verre : "article"
```

<a id="ventes"></a>

## Ventes

| Table | Contenu | Colonnes |
| --- | --- | --- |
| `ventes_avoir` | Avoir : Avoir : crédit rendu au client sur une vente (retour d'articles, ou annulation). | 20 |
| `ventes_compteurfacture` | Compteur de factures : Dernier numéro attribué par magasin, année et type de document (numérotation sans trou). | 5 |
| `ventes_devis` | Devis : Devis d'équipement remis à un client, avec ses prix figés jusqu'à la date de validité. | 19 |
| `ventes_etapecommande` | Étape de commande : Passage d'une commande à une étape du suivi qualité, avec qui et quand (traçabilité). | 6 |
| `ventes_facture` | Facture : Facture émise à part, au nom d'un client, pour une vente entièrement payée. | 21 |
| `ventes_ligneavoir` | Ligne d'avoir | 8 |
| `ventes_lignedevis` | Ligne de devis | 10 |
| `ventes_lignevente` | Ligne de vente | 9 |
| `ventes_paiement` | Paiement : Règlement reçu : tout le prix en caisse, ou acompte puis solde pour une commande. | 6 |
| `ventes_priseencharge` | Prise en charge : Part d'une vente payée par un organisme (CNAM, assurance, mutuelle) et non par le client. | 10 |
| `ventes_vente` | Vente : Vente enregistrée en caisse, avec son ticket. Jamais modifiée : une correction passera par un avoir. | 20 |

```mermaid
erDiagram
    ventes_Avoir {
        bigint id PK "ID"
        uuid public_id UK "public id"
        timestamptz cree_le "cree le"
        timestamptz modifie_le "modifie le"
        bigint magasin_id FK "magasin"
        varchar numero UK "numero"
        smallint annee "annee"
        int sequence "sequence"
        bigint vente_id FK "vente"
        bigint facture_id FK "facture"
        bigint client_id FK "client"
        bool annulation "annulation"
        varchar motif "motif"
        varchar devise "devise"
        numeric total_ht "total ht"
        numeric total_tva "total tva"
        numeric total_ttc "total ttc"
        numeric montant_rembourse "montant rembourse"
        varchar mode_remboursement "mode remboursement"
        bigint emis_par_id FK "emis par"
    }
    ventes_CompteurFacture {
        bigint id PK "ID"
        bigint magasin_id FK "magasin"
        smallint annee "annee"
        varchar type_document "type document"
        int dernier "dernier"
    }
    ventes_Devis {
        bigint id PK "ID"
        uuid public_id UK "public id"
        timestamptz cree_le "cree le"
        timestamptz modifie_le "modifie le"
        bigint magasin_id FK "magasin"
        varchar numero UK "numero"
        smallint annee "annee"
        int sequence "sequence"
        bigint client_id FK "client"
        bigint prescription_id FK "prescription"
        bigint etabli_par_id FK "etabli par"
        varchar devise "devise"
        numeric total_ht "total ht"
        numeric total_tva "total tva"
        numeric total_ttc "total ttc"
        date valable_jusqu_au "valable jusqu au"
        varchar statut "statut"
        bigint vente_id FK "vente"
        text remarques "remarques"
    }
    ventes_EtapeCommande {
        bigint id PK "ID"
        bigint vente_id FK "vente"
        varchar etape "etape"
        varchar observation "observation"
        timestamptz le "le"
        bigint par_id FK "par"
    }
    ventes_Facture {
        bigint id PK "ID"
        uuid public_id UK "public id"
        timestamptz cree_le "cree le"
        timestamptz modifie_le "modifie le"
        bigint magasin_id FK "magasin"
        bigint vente_id FK "vente"
        bigint client_id FK "client"
        varchar client_nom "client nom"
        varchar client_adresse "client adresse"
        varchar client_matricule_fiscal "client matricule fiscal"
        varchar numero UK "numero"
        smallint annee "annee"
        int sequence "sequence"
        varchar devise "devise"
        numeric total_ht "total ht"
        numeric total_tva "total tva"
        numeric total_ttc "total ttc"
        numeric timbre_fiscal "timbre fiscal"
        numeric net_a_payer "net a payer"
        varchar mode_paiement_timbre "mode paiement timbre"
        bigint emise_par_id FK "emise par"
    }
    ventes_LigneAvoir {
        bigint id PK "ID"
        bigint avoir_id FK "avoir"
        bigint ligne_vente_id FK "ligne vente"
        varchar libelle "libelle"
        int quantite "quantite"
        numeric taux_tva "taux tva"
        numeric total_ttc "total ttc"
        bool remis_en_stock "remis en stock"
    }
    ventes_LigneDevis {
        bigint id PK "ID"
        bigint devis_id FK "devis"
        bigint article_id FK "article"
        varchar libelle "libelle"
        varchar oeil "oeil"
        int quantite "quantite"
        numeric prix_unitaire_ttc "prix unitaire ttc"
        numeric remise_pct "remise pct"
        numeric taux_tva "taux tva"
        numeric total_ttc "total ttc"
    }
    ventes_LigneVente {
        bigint id PK "ID"
        bigint vente_id FK "vente"
        bigint article_id FK "article"
        varchar libelle "libelle"
        int quantite "quantite"
        numeric prix_unitaire_ttc "prix unitaire ttc"
        numeric remise_pct "remise pct"
        numeric taux_tva "taux tva"
        numeric total_ttc "total ttc"
    }
    ventes_Paiement {
        bigint id PK "ID"
        bigint vente_id FK "vente"
        varchar mode "mode"
        numeric montant "montant"
        timestamptz recu_le "recu le"
        bigint recu_par_id FK "recu par"
    }
    ventes_PriseEnCharge {
        bigint id PK "ID"
        uuid public_id UK "public id"
        timestamptz cree_le "cree le"
        timestamptz modifie_le "modifie le"
        bigint vente_id FK "vente"
        bigint organisme_id FK "organisme"
        numeric montant "montant"
        varchar numero_dossier "n° de dossier"
        varchar statut "statut"
        bigint saisie_par_id FK "saisie par"
    }
    ventes_Vente {
        bigint id PK "ID"
        uuid public_id UK "public id"
        timestamptz cree_le "cree le"
        timestamptz modifie_le "modifie le"
        bigint magasin_id FK "magasin"
        varchar numero UK "numero"
        smallint annee "annee"
        int sequence "sequence"
        bigint client_id FK "client"
        bigint vendeur_id FK "vendeur"
        varchar devise "devise"
        numeric total_ht "total ht"
        numeric total_tva "total tva"
        numeric total_ttc "total ttc"
        varchar statut "statut"
        date livraison_prevue_le "livraison prevue le"
        smallint peniche "péniche"
        timestamptz livree_le "livree le"
        bigint livree_par_id FK "livree par"
        varchar etape "étape de l'atelier"
    }
    reseau_Magasin ||--o{ ventes_Avoir : "magasin"
    ventes_Vente ||--o{ ventes_Avoir : "vente"
    ventes_Facture |o--o{ ventes_Avoir : "facture"
    crm_Client |o--o{ ventes_Avoir : "client"
    securite_Utilisateur ||--o{ ventes_Avoir : "emis_par"
    reseau_Magasin ||--o{ ventes_CompteurFacture : "magasin"
    reseau_Magasin ||--o{ ventes_Devis : "magasin"
    crm_Client ||--o{ ventes_Devis : "client"
    optique_Prescription |o--o{ ventes_Devis : "prescription"
    securite_Utilisateur ||--o{ ventes_Devis : "etabli_par"
    ventes_Vente |o--|| ventes_Devis : "vente"
    ventes_Vente ||--o{ ventes_EtapeCommande : "vente"
    securite_Utilisateur ||--o{ ventes_EtapeCommande : "par"
    reseau_Magasin ||--o{ ventes_Facture : "magasin"
    ventes_Vente ||--|| ventes_Facture : "vente"
    crm_Client ||--o{ ventes_Facture : "client"
    securite_Utilisateur ||--o{ ventes_Facture : "emise_par"
    ventes_Avoir ||--o{ ventes_LigneAvoir : "avoir"
    ventes_LigneVente ||--o{ ventes_LigneAvoir : "ligne_vente"
    ventes_Devis ||--o{ ventes_LigneDevis : "devis"
    stock_Article ||--o{ ventes_LigneDevis : "article"
    ventes_Vente ||--o{ ventes_LigneVente : "vente"
    stock_Article ||--o{ ventes_LigneVente : "article"
    ventes_Vente ||--o{ ventes_Paiement : "vente"
    securite_Utilisateur |o--o{ ventes_Paiement : "recu_par"
    ventes_Vente ||--o{ ventes_PriseEnCharge : "vente"
    crm_Organisme ||--o{ ventes_PriseEnCharge : "organisme"
    securite_Utilisateur ||--o{ ventes_PriseEnCharge : "saisie_par"
    reseau_Magasin ||--o{ ventes_Vente : "magasin"
    crm_Client |o--o{ ventes_Vente : "client"
    securite_Utilisateur ||--o{ ventes_Vente : "vendeur"
    securite_Utilisateur |o--o{ ventes_Vente : "livree_par"
```

<a id="crm"></a>

## Clients

| Table | Contenu | Colonnes |
| --- | --- | --- |
| `crm_client` | Client : Client partagé par tout le réseau : il peut acheter dans n'importe quel magasin. | 24 |
| `crm_organisme` | Organisme de prise en charge : Organisme qui prend en charge une partie des lunettes : CNAM, assurance ou mutuelle. | 8 |

```mermaid
erDiagram
    crm_Client {
        bigint id PK "ID"
        uuid public_id UK "public id"
        timestamptz cree_le "cree le"
        timestamptz modifie_le "modifie le"
        int numero UK "n° de fiche"
        varchar civilite "civilite"
        varchar nom "nom"
        varchar prenom "prenom"
        date date_naissance "date naissance"
        varchar telephone "telephone"
        varchar telephone_2 "téléphone 2"
        varchar email "email"
        varchar adresse "adresse"
        varchar code_postal "code postal"
        varchar ville "ville"
        varchar societe "société"
        varchar matricule_fiscal "matricule fiscal"
        bigint magasin_origine_id FK "magasin origine"
        bool accepte_relances "accepte relances"
        varchar reference_externe "ancien n° de fiche"
        bigint organisme_id FK "prise en charge"
        varchar numero_affilie "n° d'affilié"
        text notes "notes"
        bool est_actif "est actif"
    }
    crm_Organisme {
        bigint id PK "ID"
        uuid public_id UK "public id"
        timestamptz cree_le "cree le"
        timestamptz modifie_le "modifie le"
        varchar nom "nom"
        varchar type "type"
        bigint pays_id FK "pays"
        bool est_actif "est actif"
    }
    reseau_Magasin ||--o{ crm_Client : "magasin_origine"
    crm_Organisme |o--o{ crm_Client : "organisme"
    reseau_Pays ||--o{ crm_Organisme : "pays"
```

<a id="optique"></a>

## Dossiers optiques

| Table | Contenu | Colonnes |
| --- | --- | --- |
| `optique_accesprescription` | Accès à une prescription : Journal de chaque consultation ou saisie d'ordonnance, en ajout seul (verrou en base). | 6 |
| `optique_prescription` | Prescription : Ordonnance d'un client : donnée de santé au sens du RGPD. | 12 |

```mermaid
erDiagram
    optique_AccesPrescription {
        bigint id PK "ID"
        timestamptz horodatage "horodatage"
        bigint utilisateur_id FK "utilisateur"
        bigint prescription_id FK "prescription"
        varchar action "action"
        inet adresse_ip "adresse ip"
    }
    optique_Prescription {
        bigint id PK "ID"
        uuid public_id UK "public id"
        timestamptz cree_le "cree le"
        timestamptz modifie_le "modifie le"
        bigint client_id FK "client"
        varchar type "type"
        date date_prescription "date prescription"
        varchar prescripteur "prescripteur"
        varchar prescripteur_identifiant "prescripteur identifiant"
        text mesures_chiffrees "mesures chiffrees"
        bigint magasin_saisie_id FK "magasin saisie"
        bigint saisie_par_id FK "saisie par"
    }
    securite_Utilisateur ||--o{ optique_AccesPrescription : "utilisateur"
    optique_Prescription ||--o{ optique_AccesPrescription : "prescription"
    crm_Client ||--o{ optique_Prescription : "client"
    reseau_Magasin ||--o{ optique_Prescription : "magasin_saisie"
    securite_Utilisateur ||--o{ optique_Prescription : "saisie_par"
```

<a id="achats"></a>

## Achats

| Table | Contenu | Colonnes |
| --- | --- | --- |
| `achats_commandefournisseur` | Commande fournisseur : Commande passée par un magasin à un fournisseur pour les verres de ses clients. | 14 |
| `achats_fournisseur` | Fournisseur : Fournisseur (laboratoire de verres…), commun à tout le réseau. | 10 |
| `achats_lignecommandefournisseur` | Ligne de commande fournisseur | 6 |

```mermaid
erDiagram
    achats_CommandeFournisseur {
        bigint id PK "ID"
        uuid public_id UK "public id"
        timestamptz cree_le "cree le"
        timestamptz modifie_le "modifie le"
        bigint magasin_id FK "magasin"
        varchar numero UK "numero"
        smallint annee "annee"
        int sequence "sequence"
        bigint fournisseur_id FK "fournisseur"
        varchar reference_fournisseur "reference fournisseur"
        varchar statut "statut"
        bigint passee_par_id FK "passee par"
        timestamptz recue_le "recue le"
        bigint recue_par_id FK "recue par"
    }
    achats_Fournisseur {
        bigint id PK "ID"
        uuid public_id UK "public id"
        timestamptz cree_le "cree le"
        timestamptz modifie_le "modifie le"
        varchar nom UK "nom"
        bigint pays_id FK "pays"
        varchar telephone "telephone"
        varchar email "email"
        text adresse "adresse"
        bool est_actif "est actif"
    }
    achats_LigneCommandeFournisseur {
        bigint id PK "ID"
        bigint commande_id FK "commande"
        bigint ligne_vente_id FK "ligne vente"
        bigint article_id FK "article"
        int quantite "quantite"
        varchar details "details"
    }
    reseau_Magasin ||--o{ achats_CommandeFournisseur : "magasin"
    achats_Fournisseur ||--o{ achats_CommandeFournisseur : "fournisseur"
    securite_Utilisateur ||--o{ achats_CommandeFournisseur : "passee_par"
    securite_Utilisateur |o--o{ achats_CommandeFournisseur : "recue_par"
    reseau_Pays ||--o{ achats_Fournisseur : "pays"
    achats_CommandeFournisseur ||--o{ achats_LigneCommandeFournisseur : "commande"
    ventes_LigneVente ||--o{ achats_LigneCommandeFournisseur : "ligne_vente"
    stock_Article ||--o{ achats_LigneCommandeFournisseur : "article"
```

<a id="tresorerie"></a>

## Trésorerie

| Table | Contenu | Colonnes |
| --- | --- | --- |
| `tresorerie_cloturecaisse` | Clôture de caisse : Clôture de la caisse d'un magasin, envoyée à la finance pour vérification. | 33 |
| `tresorerie_comptetresorerie` | Compte de trésorerie : Où se trouve l'argent d'une société : banque, coffre d'un magasin, caisse centrale. | 13 |
| `tresorerie_depensecaisse` | Dépense de caisse : Petite dépense payée en espèces depuis la caisse du magasin, déduite à la clôture. | 12 |
| `tresorerie_operationtresorerie` | Opération de trésorerie : Mouvement d'argent : dépôt des clôtures, versement en banque, alimentation, frais… | 21 |

```mermaid
erDiagram
    tresorerie_ClotureCaisse {
        bigint id PK "ID"
        uuid public_id UK "public id"
        timestamptz cree_le "cree le"
        timestamptz modifie_le "modifie le"
        bigint magasin_id FK "magasin"
        varchar numero UK "numero"
        timestamptz debut "debut"
        timestamptz fin "fin"
        varchar devise "devise"
        varchar statut "statut"
        numeric fond_initial "fond initial"
        numeric encaisse_especes "encaisse especes"
        numeric encaisse_cheques "encaisse cheques"
        int nombre_cheques "nombre cheques"
        numeric encaisse_cartes "encaisse cartes"
        numeric rembourse_especes "rembourse especes"
        numeric rembourse_cheques "rembourse cheques"
        numeric rembourse_cartes "rembourse cartes"
        numeric depenses "depenses"
        numeric alimentations "alimentations"
        numeric especes_comptees "especes comptees"
        numeric cheques_comptes "cheques comptes"
        int nombre_cheques_comptes "nombre cheques comptes"
        numeric cartes_comptees "cartes comptees"
        numeric fond_conserve "fond conserve"
        text commentaire_caissier "commentaire caissier"
        bigint cloturee_par_id FK "cloturee par"
        bigint verifiee_par_id FK "verifiee par"
        timestamptz verifiee_le "verifiee le"
        text commentaire_finance "commentaire finance"
        bigint depot_especes_id FK "depot especes"
        bigint depot_cheques_id FK "depot cheques"
        bigint encaissement_cartes_id FK "encaissement cartes"
    }
    tresorerie_CompteTresorerie {
        bigint id PK "ID"
        uuid public_id UK "public id"
        timestamptz cree_le "cree le"
        timestamptz modifie_le "modifie le"
        bigint societe_id FK "société"
        varchar type "type"
        varchar nom "nom"
        varchar banque "banque"
        varchar rib "RIB"
        bigint magasin_id FK "magasin"
        varchar devise "devise"
        numeric solde_initial "solde initial"
        bool est_actif "est actif"
    }
    tresorerie_DepenseCaisse {
        bigint id PK "ID"
        uuid public_id UK "public id"
        timestamptz cree_le "cree le"
        timestamptz modifie_le "modifie le"
        bigint magasin_id FK "magasin"
        varchar categorie "categorie"
        varchar motif "motif"
        varchar beneficiaire "bénéficiaire"
        numeric montant "montant"
        timestamptz payee_le "payee le"
        bigint saisie_par_id FK "saisie par"
        bigint cloture_id FK "cloture"
    }
    tresorerie_OperationTresorerie {
        bigint id PK "ID"
        uuid public_id UK "public id"
        timestamptz cree_le "cree le"
        timestamptz modifie_le "modifie le"
        bigint societe_id FK "société"
        varchar numero UK "numero"
        varchar type "type"
        varchar statut "statut"
        bigint source_id FK "source"
        bigint destination_id FK "destination"
        bigint magasin_id FK "magasin"
        numeric montant "montant"
        numeric montant_credite "montant credite"
        date date_prevue "date prevue"
        date date_operation "date operation"
        date date_valeur "date valeur"
        timestamptz effectuee_le "effectuee le"
        varchar reference "reference"
        varchar libelle "libelle"
        bigint cree_par_id FK "cree par"
        bigint rapprochee_par_id FK "rapprochee par"
    }
    reseau_Magasin ||--o{ tresorerie_ClotureCaisse : "magasin"
    securite_Utilisateur ||--o{ tresorerie_ClotureCaisse : "cloturee_par"
    securite_Utilisateur |o--o{ tresorerie_ClotureCaisse : "verifiee_par"
    tresorerie_OperationTresorerie |o--o{ tresorerie_ClotureCaisse : "depot_especes"
    tresorerie_OperationTresorerie |o--o{ tresorerie_ClotureCaisse : "depot_cheques"
    tresorerie_OperationTresorerie |o--o{ tresorerie_ClotureCaisse : "encaissement_cartes"
    reseau_Societe ||--o{ tresorerie_CompteTresorerie : "societe"
    reseau_Magasin |o--o{ tresorerie_CompteTresorerie : "magasin"
    reseau_Magasin ||--o{ tresorerie_DepenseCaisse : "magasin"
    securite_Utilisateur ||--o{ tresorerie_DepenseCaisse : "saisie_par"
    tresorerie_ClotureCaisse |o--o{ tresorerie_DepenseCaisse : "cloture"
    reseau_Societe ||--o{ tresorerie_OperationTresorerie : "societe"
    tresorerie_CompteTresorerie |o--o{ tresorerie_OperationTresorerie : "source"
    tresorerie_CompteTresorerie |o--o{ tresorerie_OperationTresorerie : "destination"
    reseau_Magasin |o--o{ tresorerie_OperationTresorerie : "magasin"
    securite_Utilisateur ||--o{ tresorerie_OperationTresorerie : "cree_par"
    securite_Utilisateur |o--o{ tresorerie_OperationTresorerie : "rapprochee_par"
```

<a id="rh"></a>

## Ressources humaines

| Table | Contenu | Colonnes |
| --- | --- | --- |
| `rh_acompte` | Acompte : Avance sur salaire, retenue sur la paie du mois indiqué. | 17 |
| `rh_demandeconge` | Demande de congé : Demande de congé : l'employé (ou son responsable) la saisit, un responsable décide. | 16 |
| `rh_employe` | Employé : Fiche d'un membre du personnel, rattachée au magasin où il travaille. | 17 |
| `rh_pointage` | Pointage : Présence d'un employé un jour donné, saisie par le responsable du magasin. | 12 |
| `rh_prime` | Prime : Prime proposée par le responsable, validée par les RH, payée avec la paie du mois. | 15 |

```mermaid
erDiagram
    rh_Acompte {
        bigint id PK "ID"
        uuid public_id UK "public id"
        timestamptz cree_le "cree le"
        timestamptz modifie_le "modifie le"
        bigint employe_id FK "employe"
        bigint magasin_id FK "magasin"
        numeric montant "montant"
        date mois "mois"
        varchar motif "motif"
        varchar statut "statut"
        bigint demande_par_id FK "demande par"
        bigint decide_par_id FK "decide par"
        timestamptz decide_le "decide le"
        varchar commentaire_decision "commentaire decision"
        varchar mode_versement "mode versement"
        date verse_le "verse le"
        varchar reference_versement "reference versement"
    }
    rh_DemandeConge {
        bigint id PK "ID"
        uuid public_id UK "public id"
        timestamptz cree_le "cree le"
        timestamptz modifie_le "modifie le"
        bigint employe_id FK "employe"
        bigint magasin_id FK "magasin"
        varchar type "type"
        date debut "du"
        date fin "au"
        numeric jours "jours"
        varchar motif "motif"
        varchar statut "statut"
        bigint demandee_par_id FK "demandee par"
        bigint decidee_par_id FK "decidee par"
        timestamptz decidee_le "decidee le"
        varchar commentaire_decision "commentaire decision"
    }
    rh_Employe {
        bigint id PK "ID"
        uuid public_id UK "public id"
        timestamptz cree_le "cree le"
        timestamptz modifie_le "modifie le"
        bigint magasin_id FK "magasin"
        bigint utilisateur_id FK "utilisateur"
        varchar matricule UK "matricule"
        varchar nom "nom"
        varchar prenom "prénom"
        varchar cin "CIN"
        varchar telephone "téléphone"
        varchar poste "poste"
        date date_embauche "date d'embauche"
        date date_sortie "date sortie"
        numeric conges_par_mois "jours de congé par mois"
        numeric salaire_base "salaire de base"
        numeric solde_conges_initial "solde de congés de départ"
    }
    rh_Pointage {
        bigint id PK "ID"
        uuid public_id UK "public id"
        timestamptz cree_le "cree le"
        timestamptz modifie_le "modifie le"
        bigint employe_id FK "employe"
        bigint magasin_id FK "magasin"
        date date "date"
        varchar statut "statut"
        time arrivee "arrivée"
        time depart "départ"
        varchar commentaire "commentaire"
        bigint saisi_par_id FK "saisi par"
    }
    rh_Prime {
        bigint id PK "ID"
        uuid public_id UK "public id"
        timestamptz cree_le "cree le"
        timestamptz modifie_le "modifie le"
        bigint employe_id FK "employe"
        bigint magasin_id FK "magasin"
        varchar type "type"
        numeric montant "montant"
        date mois "mois"
        varchar motif "motif"
        varchar statut "statut"
        bigint proposee_par_id FK "proposee par"
        bigint validee_par_id FK "validee par"
        timestamptz validee_le "validee le"
        varchar commentaire_decision "commentaire decision"
    }
    rh_Employe ||--o{ rh_Acompte : "employe"
    reseau_Magasin ||--o{ rh_Acompte : "magasin"
    securite_Utilisateur ||--o{ rh_Acompte : "demande_par"
    securite_Utilisateur |o--o{ rh_Acompte : "decide_par"
    rh_Employe ||--o{ rh_DemandeConge : "employe"
    reseau_Magasin ||--o{ rh_DemandeConge : "magasin"
    securite_Utilisateur ||--o{ rh_DemandeConge : "demandee_par"
    securite_Utilisateur |o--o{ rh_DemandeConge : "decidee_par"
    reseau_Magasin ||--o{ rh_Employe : "magasin"
    securite_Utilisateur |o--|| rh_Employe : "utilisateur"
    rh_Employe ||--o{ rh_Pointage : "employe"
    reseau_Magasin ||--o{ rh_Pointage : "magasin"
    securite_Utilisateur ||--o{ rh_Pointage : "saisi_par"
    rh_Employe ||--o{ rh_Prime : "employe"
    reseau_Magasin ||--o{ rh_Prime : "magasin"
    securite_Utilisateur ||--o{ rh_Prime : "proposee_par"
    securite_Utilisateur |o--o{ rh_Prime : "validee_par"
```

<a id="pilotage"></a>

## Alertes et reporting

| Table | Contenu | Colonnes |
| --- | --- | --- |
| `pilotage_alerte` | Alerte : Entrée « Alertes » de l'administration : rien n'est stocké, la page est calculée. | 1 |
| `pilotage_reporting` | Reporting des ventes : Entrée « Reporting » de l'administration : rien n'est stocké, la page est calculée. | 1 |

```mermaid
erDiagram
    pilotage_Alerte {
        bigint id PK "ID"
    }
    pilotage_Reporting {
        bigint id PK "ID"
    }
```
