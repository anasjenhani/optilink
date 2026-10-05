"""Privilèges qu'un administrateur peut donner à un profil, avec leur libellé en français.

Chaque privilège est une permission Django. Les permissions absentes de ce catalogue ne sont
pas proposées dans l'écran des profils, et n'y sont jamais retirées.
"""

PRIVILEGES = {
    "Caisse et ventes": {
        "ventes.view_vente": "Voir les ventes et les commandes",
        "ventes.add_vente": "Encaisser (caisse, acomptes, livraisons)",
        "ventes.appliquer_remise": "Accorder une remise",
    },
    "Prises en charge": {
        "ventes.view_priseencharge": "Voir les prises en charge (CNAM, assurances, mutuelles)",
        "ventes.add_priseencharge": "Saisir une prise en charge sur une commande",
        "ventes.change_priseencharge": "Suivre une prise en charge (accordée, réglée, refusée)",
        "crm.view_organisme": "Voir les organismes de prise en charge",
        "crm.add_organisme": "Créer un organisme de prise en charge",
        "crm.change_organisme": "Modifier un organisme de prise en charge",
    },
    "Pilotage": {
        "ventes.consulter_reporting": "Consulter le reporting (chiffre d'affaires, ventes)",
    },
    "Devis": {
        "ventes.view_devis": "Voir les devis",
        "ventes.add_devis": "Établir un devis",
        "ventes.change_devis": "Changer le statut d'un devis",
    },
    "Factures et avoirs": {
        "ventes.view_facture": "Voir les factures",
        "ventes.add_facture": "Établir une facture",
        "ventes.view_avoir": "Voir les avoirs",
        "ventes.add_avoir": "Établir un avoir ou annuler une vente",
    },
    "Clients et ordonnances": {
        "crm.view_client": "Voir les clients",
        "crm.add_client": "Créer un client",
        "crm.change_client": "Modifier un client",
        "optique.view_prescription": "Voir les ordonnances",
        "optique.add_prescription": "Saisir une ordonnance",
        "optique.view_accesprescription": "Voir qui a consulté les ordonnances",
    },
    "Trésorerie": {
        "tresorerie.view_cloturecaisse": "Voir les clôtures de caisse",
        "tresorerie.add_cloturecaisse": "Clôturer la caisse",
        "tresorerie.valider_cloturecaisse": "Valider ou rejeter une clôture de caisse",
        "tresorerie.view_depensecaisse": "Voir les dépenses de caisse",
        "tresorerie.add_depensecaisse": "Saisir une dépense de caisse",
        "tresorerie.view_comptetresorerie": "Voir les comptes bancaires et coffres",
        "tresorerie.add_comptetresorerie": "Créer un compte bancaire ou un coffre",
        "tresorerie.change_comptetresorerie": "Modifier un compte bancaire ou un coffre",
        "tresorerie.view_operationtresorerie": "Voir les versements et opérations bancaires",
        "tresorerie.add_operationtresorerie": "Déposer l'argent des clôtures, prévoir un versement",
        "tresorerie.rapprocher_operationtresorerie": "Rapprocher les opérations avec la banque",
    },
    "Ressources humaines": {
        "rh.view_employe": "Voir les fiches du personnel",
        "rh.add_employe": "Créer une fiche employé",
        "rh.change_employe": "Modifier une fiche employé",
        "rh.view_pointage": "Voir la présence",
        "rh.add_pointage": "Saisir la présence du jour",
        "rh.view_demandeconge": "Voir les congés",
        "rh.add_demandeconge": "Saisir une demande de congé pour un employé",
        "rh.decider_demandeconge": "Accepter ou refuser une demande de congé",
        "rh.view_acompte": "Voir les acomptes",
        "rh.add_acompte": "Demander un acompte pour un employé",
        "rh.decider_acompte": "Accorder, refuser et verser un acompte",
        "rh.view_prime": "Voir les primes",
        "rh.add_prime": "Proposer une prime",
        "rh.valider_prime": "Valider ou refuser une prime",
    },
    "Stock et prix": {
        "stock.view_article": "Voir le catalogue et le stock",
        "stock.add_article": "Créer un article",
        "stock.change_article": "Modifier un article",
        "stock.view_mouvementstock": "Voir les mouvements de stock",
        "stock.add_mouvementstock": "Entrer ou sortir du stock",
        "stock.view_prixarticle": "Voir les prix de vente",
        "stock.add_prixarticle": "Fixer un prix de vente",
        "stock.change_prixarticle": "Modifier un prix de vente",
        "stock.view_transfertstock": "Voir les transferts de stock",
        "stock.add_transfertstock": "Envoyer un transfert de stock (du dépôt vers un magasin)",
        "stock.change_transfertstock": "Réceptionner un transfert de stock arrivé au magasin",
        "stock.view_inventaire": "Voir les inventaires",
        "stock.add_inventaire": "Ouvrir un inventaire",
        "stock.change_inventaire": "Compter les articles d'un inventaire en cours",
        "stock.valider_inventaire": (
            "Vérifier, corriger et valider un inventaire (corrige le stock selon le comptage)"
        ),
    },
    "Achats": {
        "achats.view_fournisseur": "Voir les fournisseurs",
        "achats.add_fournisseur": "Créer un fournisseur",
        "achats.change_fournisseur": "Modifier un fournisseur",
        "achats.view_commandefournisseur": "Voir les commandes fournisseurs",
        "achats.add_commandefournisseur": "Passer une commande fournisseur",
        "achats.change_commandefournisseur": "Réceptionner une commande fournisseur",
        "achats.view_bonreception": "Voir les bons de réception",
        "achats.add_bonreception": "Saisir un bon de réception (entrée de la marchandise)",
        "achats.view_factureachat": "Voir les factures achat (factures fournisseurs)",
        "achats.add_factureachat": "Saisir une facture achat (regroupe les bons de réception)",
        "achats.view_bonretour": "Voir les bons retour fournisseur",
        "achats.add_bonretour": "Saisir un bon retour fournisseur (marchandise renvoyée)",
        "achats.view_casseverre": "Voir les casses de verres",
        "achats.add_casseverre": "Déclarer une casse de verre (verre à recommander)",
    },
    "Sociétés, magasins et pays": {
        "reseau.view_societe": "Voir les sociétés",
        "reseau.add_societe": "Créer une société",
        "reseau.change_societe": "Modifier une société",
        "reseau.view_magasin": "Voir les magasins",
        "reseau.add_magasin": "Créer un magasin",
        "reseau.change_magasin": "Modifier un magasin",
        "reseau.view_pays": "Voir les pays",
        "reseau.add_pays": "Ajouter un pays",
        "reseau.change_pays": "Modifier un pays (devise, timbre)",
        "reseau.view_tauxtva": "Voir les taux de TVA",
        "reseau.add_tauxtva": "Ajouter un taux de TVA",
        "reseau.change_tauxtva": "Modifier un taux de TVA",
        "reseau.delete_tauxtva": "Supprimer un taux de TVA",
    },
    "Accès et sécurité": {
        "securite.view_utilisateur": "Voir les utilisateurs",
        "securite.add_utilisateur": "Créer un utilisateur",
        "securite.change_utilisateur": "Modifier un utilisateur et ses profils",
        "securite.view_affectation": "Voir les profils donnés aux utilisateurs",
        "securite.add_affectation": "Donner un profil à un utilisateur",
        "securite.change_affectation": "Modifier le profil d'un utilisateur",
        "securite.delete_affectation": "Retirer un profil à un utilisateur",
        "auth.view_group": "Voir les profils et leurs privilèges",
        "auth.add_group": "Créer un profil",
        "auth.change_group": "Modifier les privilèges d'un profil",
        "auth.delete_group": "Supprimer un profil",
        "securite.view_evenementsecurite": "Voir le journal des connexions",
        "auditlog.view_logentry": "Voir l'historique des modifications",
    },
}

CODES = frozenset(code for module in PRIVILEGES.values() for code in module)

# Privilèges d'administration : on ne les transmet, ne les retire ou ne les ajoute à un profil
# que si on les détient soi-même. Les privilèges métier se donnent librement.
ADMINISTRATION = frozenset(
    PRIVILEGES["Accès et sécurité"].keys() | PRIVILEGES["Sociétés, magasins et pays"].keys()
)
