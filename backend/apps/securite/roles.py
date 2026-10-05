"""Rôles de départ (section 13 du document d'architecture).

Ils sont créés une seule fois, avec leurs permissions initiales ; le siège les ajuste ensuite
dans l'administration. Chaque lot ajoutera les permissions de ses modules à ces rôles.
"""

from django.contrib.auth.management import create_permissions
from django.contrib.auth.models import Group, Permission

from .privileges import CODES

LECTURE_RESEAU = ["reseau.view_magasin", "reseau.view_societe"]

LECTURE_ADMINISTRATION = LECTURE_RESEAU + [
    "securite.view_utilisateur",
    "securite.view_affectation",
    "securite.view_evenementsecurite",
    "auth.view_group",
    "auditlog.view_logentry",
]

ROLES_DE_DEPART = {
    # Gère comptes, rôles et magasins, sans accès aux données métier.
    "Administrateur": LECTURE_ADMINISTRATION
    + [
        "reseau.add_magasin",
        "reseau.change_magasin",
        "reseau.add_societe",
        "reseau.change_societe",
        "securite.add_utilisateur",
        "securite.change_utilisateur",
        "securite.add_affectation",
        "securite.change_affectation",
        "securite.delete_affectation",
        "auth.add_group",
        "auth.change_group",
    ],
    "Administrateur Global": [],  # Tous les privilèges : complété plus bas.
    "Responsable de magasin": LECTURE_RESEAU,
    "Opticien": LECTURE_RESEAU,
    "Vendeur": LECTURE_RESEAU,
    "Achats & Gestionnaire de Stock": LECTURE_RESEAU,
    "Comptabilité & Finance": LECTURE_RESEAU,
    "Ressources Humaines": LECTURE_RESEAU + ["securite.view_utilisateur"],
    "Caissier": LECTURE_RESEAU,
    "Atelier": LECTURE_RESEAU,
    "Commande": LECTURE_RESEAU,
}

# Prototype caisse et stock : colonnes Ventes et Stock de la matrice.
VENTES_COMPLET = ["ventes.view_vente", "ventes.add_vente", "ventes.appliquer_remise"]
VENTES_LIMITE = ["ventes.view_vente", "ventes.add_vente"]
VENTES_LECTURE = ["ventes.view_vente"]
STOCK_COMPLET = [
    "stock.view_article",
    "stock.add_article",
    "stock.change_article",
    "stock.view_mouvementstock",
    "stock.add_mouvementstock",
]
STOCK_LIMITE = ["stock.view_article", "stock.view_mouvementstock", "stock.add_mouvementstock"]
STOCK_LECTURE = ["stock.view_article", "stock.view_mouvementstock"]

PERMISSIONS_CAISSE_STOCK = {
    "Responsable de magasin": VENTES_COMPLET + STOCK_COMPLET,
    "Opticien": VENTES_COMPLET + STOCK_LIMITE,
    "Vendeur": VENTES_LIMITE + STOCK_LECTURE,
    "Achats & Gestionnaire de Stock": STOCK_COMPLET,
    "Comptabilité & Finance": VENTES_LECTURE + STOCK_LECTURE,
    # Le caissier encaisse sans accorder de remise ; atelier et commandes consultent.
    "Caissier": VENTES_LIMITE + STOCK_LECTURE,
    "Atelier": VENTES_LECTURE + STOCK_LECTURE,
    "Commande": VENTES_LECTURE + STOCK_LECTURE,
}

# Lot Vendre : colonne « Clients & optique ». Seuls opticiens et responsables de magasin
# voient les ordonnances (données de santé) ; la direction voit qui les a consultées.
CLIENTS_COMPLET = ["crm.view_client", "crm.add_client", "crm.change_client"]
CLIENTS_LECTURE = ["crm.view_client"]
ORDONNANCES = ["optique.view_prescription", "optique.add_prescription"]

PERMISSIONS_CLIENTS_OPTIQUE = {
    "Responsable de magasin": CLIENTS_COMPLET + ORDONNANCES,
    "Opticien": CLIENTS_COMPLET + ORDONNANCES,
    "Vendeur": CLIENTS_COMPLET,
    # L'atelier monte les verres et le service commandes les commande : ils lisent l'ordonnance.
    "Caissier": CLIENTS_LECTURE,
    "Atelier": CLIENTS_LECTURE + ["optique.view_prescription"],
    "Commande": CLIENTS_LECTURE + ["optique.view_prescription"],
}

# Paramétrage par pays (taux de TVA, timbre, monnaie) : réglé par l'administrateur, consulté
# par la direction. Les prix de vente suivent la colonne Stock « Complet ».
PRIX_COMPLET = ["stock.view_prixarticle", "stock.add_prixarticle", "stock.change_prixarticle"]
PERMISSIONS_PARAMETRAGE = {
    "Administrateur": [
        "reseau.view_pays",
        "reseau.add_pays",
        "reseau.change_pays",
        "reseau.view_tauxtva",
        "reseau.add_tauxtva",
        "reseau.change_tauxtva",
        "reseau.delete_tauxtva",
    ],
    "Responsable de magasin": PRIX_COMPLET,
    "Achats & Gestionnaire de Stock": PRIX_COMPLET,
    "Comptabilité & Finance": ["reseau.view_pays", "reseau.view_tauxtva", "stock.view_prixarticle"],
}

# Factures : générées à part, une fois la vente entièrement payée.
FACTURES_COMPLET = ["ventes.view_facture", "ventes.add_facture"]
PERMISSIONS_FACTURES = {
    "Responsable de magasin": FACTURES_COMPLET,
    "Opticien": FACTURES_COMPLET,
    "Comptabilité & Finance": ["ventes.view_facture"],
}

# Devis d'équipement : établis par toute l'équipe de vente ; l'encaissement suit le droit de
# vente, une remise le droit de remise.
DEVIS_COMPLET = ["ventes.view_devis", "ventes.add_devis", "ventes.change_devis"]
PERMISSIONS_DEVIS = {
    "Responsable de magasin": DEVIS_COMPLET,
    "Opticien": DEVIS_COMPLET,
    "Vendeur": DEVIS_COMPLET,
    "Comptabilité & Finance": ["ventes.view_devis"],
    "Caissier": ["ventes.view_devis"],
}

# Avoirs et annulations : remboursent le client, donc réservés aux responsables.
AVOIRS_COMPLET = ["ventes.view_avoir", "ventes.add_avoir"]
PERMISSIONS_AVOIRS = {
    "Responsable de magasin": AVOIRS_COMPLET,
    "Comptabilité & Finance": ["ventes.view_avoir"],
}

# Commandes de verres aux fournisseurs : passées et réceptionnées par l'opticien, les
# responsables et le logisticien ; la liste des fournisseurs est tenue par les responsables.
COMMANDES_FOURNISSEURS = [
    "achats.view_fournisseur",
    "achats.view_commandefournisseur",
    "achats.add_commandefournisseur",
    "achats.change_commandefournisseur",
]
FOURNISSEURS_COMPLET = ["achats.add_fournisseur", "achats.change_fournisseur"]
PERMISSIONS_ACHATS = {
    "Responsable de magasin": COMMANDES_FOURNISSEURS + FOURNISSEURS_COMPLET,
    "Opticien": COMMANDES_FOURNISSEURS,
    "Achats & Gestionnaire de Stock": COMMANDES_FOURNISSEURS + FOURNISSEURS_COMPLET,
    "Comptabilité & Finance": ["achats.view_fournisseur", "achats.view_commandefournisseur"],
    "Atelier": [
        "achats.view_fournisseur",
        "achats.view_commandefournisseur",
        "achats.change_commandefournisseur",
    ],
    "Commande": COMMANDES_FOURNISSEURS,
}

# Bons de réception : saisis à l'arrivée de la marchandise par ceux qui réceptionnent les
# commandes fournisseurs ; vus par la finance (factures fournisseurs à rapprocher).
RECEPTIONS = ["achats.view_bonreception", "achats.add_bonreception"]
PERMISSIONS_RECEPTIONS = {
    "Administrateur Global": RECEPTIONS,
    "Responsable de magasin": RECEPTIONS,
    "Opticien": RECEPTIONS,
    "Achats & Gestionnaire de Stock": RECEPTIONS,
    "Atelier": RECEPTIONS,
    "Commande": RECEPTIONS,
    "Comptabilité & Finance": ["achats.view_bonreception"],
}

# Casses de verres : déclarées par l'atelier, l'opticien et les responsables, qui
# recommandent ensuite le verre ; vues par les achats et la finance (coût des casses).
CASSES = ["achats.view_casseverre", "achats.add_casseverre"]
PERMISSIONS_CASSES = {
    "Administrateur Global": CASSES,
    "Responsable de magasin": CASSES,
    "Opticien": CASSES,
    "Atelier": CASSES,
    "Commande": CASSES,
    "Achats & Gestionnaire de Stock": ["achats.view_casseverre"],
    "Comptabilité & Finance": ["achats.view_casseverre"],
}

# Trésorerie : le caissier clôture sa caisse chaque jour, la finance vérifie et valide.
CLOTURE = ["tresorerie.view_cloturecaisse", "tresorerie.add_cloturecaisse"]
DEPENSES = ["tresorerie.view_depensecaisse", "tresorerie.add_depensecaisse"]
# Banque et versements : le responsable dépose l'argent des clôtures, la finance suit la banque.
BANQUE_FINANCE = [
    "tresorerie.view_comptetresorerie",
    "tresorerie.add_comptetresorerie",
    "tresorerie.change_comptetresorerie",
    "tresorerie.view_operationtresorerie",
    "tresorerie.add_operationtresorerie",
    "tresorerie.rapprocher_operationtresorerie",
]
PERMISSIONS_BANQUE = {
    "Administrateur Global": BANQUE_FINANCE,
    "Responsable de magasin": [
        "tresorerie.view_comptetresorerie",
        "tresorerie.view_operationtresorerie",
        "tresorerie.add_operationtresorerie",
    ],
    "Comptabilité & Finance": BANQUE_FINANCE,
}

# Ressources humaines : le responsable pointe et décide des congés de son magasin ;
# chaque employé relié à un compte demande ses propres congés sans privilège.
RH_COMPLET = [
    "rh.view_employe",
    "rh.add_employe",
    "rh.change_employe",
    "rh.view_pointage",
    "rh.add_pointage",
    "rh.view_demandeconge",
    "rh.add_demandeconge",
    "rh.decider_demandeconge",
]
PERMISSIONS_RH = {
    "Administrateur Global": RH_COMPLET,
    "Ressources Humaines": RH_COMPLET,
    "Responsable de magasin": [
        "rh.view_employe",
        "rh.view_pointage",
        "rh.add_pointage",
        "rh.view_demandeconge",
        "rh.add_demandeconge",
        "rh.decider_demandeconge",
    ],
}

# Acomptes et primes : le responsable demande et propose, les RH décident.
REMUNERATIONS_RH = [
    "rh.view_acompte",
    "rh.add_acompte",
    "rh.decider_acompte",
    "rh.view_prime",
    "rh.add_prime",
    "rh.valider_prime",
]
PERMISSIONS_REMUNERATIONS = {
    "Administrateur Global": REMUNERATIONS_RH,
    "Ressources Humaines": REMUNERATIONS_RH,
    "Responsable de magasin": [
        "rh.view_acompte",
        "rh.add_acompte",
        "rh.view_prime",
        "rh.add_prime",
    ],
    "Comptabilité & Finance": ["rh.view_acompte", "rh.view_prime"],
}

PERMISSIONS_TRESORERIE = {
    "Administrateur Global": CLOTURE + DEPENSES + ["tresorerie.valider_cloturecaisse"],
    "Responsable de magasin": CLOTURE + DEPENSES,
    "Caissier": CLOTURE + DEPENSES,
    "Comptabilité & Finance": [
        "tresorerie.view_cloturecaisse",
        "tresorerie.valider_cloturecaisse",
        "tresorerie.view_depensecaisse",
    ],
}

# Reporting des ventes : direction, responsables et finance.
PERMISSIONS_PILOTAGE = {
    "Administrateur Global": ["ventes.consulter_reporting"],
    "Responsable de magasin": ["ventes.consulter_reporting"],
    "Comptabilité & Finance": ["ventes.consulter_reporting"],
}

# Prises en charge (CNAM, assurances, mutuelles) : saisies à la vente, suivies par les
# responsables et la finance ; les organismes se créent dans l'administration du serveur.
PEC_SAISIE = ["ventes.view_priseencharge", "ventes.add_priseencharge"]
PEC_SUIVI = PEC_SAISIE + ["ventes.change_priseencharge"]
ORGANISMES = ["crm.view_organisme", "crm.add_organisme", "crm.change_organisme"]
PERMISSIONS_PRISES_EN_CHARGE = {
    "Administrateur Global": PEC_SUIVI + ORGANISMES,
    "Responsable de magasin": PEC_SUIVI + ORGANISMES,
    "Opticien": PEC_SAISIE,
    "Vendeur": PEC_SAISIE,
    "Caissier": PEC_SAISIE,
    "Comptabilité & Finance": PEC_SUIVI + ["crm.view_organisme"],
}

for _par_role in (
    PERMISSIONS_CAISSE_STOCK,
    PERMISSIONS_CLIENTS_OPTIQUE,
    PERMISSIONS_PARAMETRAGE,
    PERMISSIONS_FACTURES,
    PERMISSIONS_DEVIS,
    PERMISSIONS_AVOIRS,
    PERMISSIONS_ACHATS,
    PERMISSIONS_RECEPTIONS,
    PERMISSIONS_TRESORERIE,
    PERMISSIONS_BANQUE,
    PERMISSIONS_RH,
    PERMISSIONS_REMUNERATIONS,
    PERMISSIONS_PILOTAGE,
    PERMISSIONS_PRISES_EN_CHARGE,
    PERMISSIONS_CASSES,
):
    for _nom, _permissions in _par_role.items():
        ROLES_DE_DEPART[_nom] = ROLES_DE_DEPART[_nom] + _permissions

ROLES_DE_DEPART["Administrateur Global"] = sorted(CODES)


def _permission(nom):
    app_label, codename = nom.split(".")
    return Permission.objects.get(content_type__app_label=app_label, codename=codename)


def initialiser_roles(sender, apps=None, using="default", **kwargs):
    """Crée les rôles manquants ; ne touche jamais un rôle existant."""
    from django.apps import apps as registre

    if sender.label != "securite":
        return
    # Les permissions des autres applications peuvent ne pas encore exister à ce stade.
    for app_config in registre.get_app_configs():
        create_permissions(app_config, verbosity=0, using=using)
    for nom, permissions in ROLES_DE_DEPART.items():
        role, cree = Group.objects.using(using).get_or_create(name=nom)
        if cree:
            role.permissions.set([_permission(p) for p in permissions])


def ajouter_aux_roles_existants(apps, permissions_par_role):
    """Pour une migration de données : ajoute des permissions aux rôles déjà en place.

    Sur une base neuve, les rôles n'existent pas encore et seront créés complets par
    ``initialiser_roles`` ; il n'y a alors rien à faire.
    """
    from django.contrib.auth.management import create_permissions as creer

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    labels = {nom.split(".")[0] for noms in permissions_par_role.values() for nom in noms}
    for label in labels:
        app_config = apps.get_app_config(label)
        app_config.models_module = True
        creer(app_config, apps=apps, verbosity=0)
        app_config.models_module = None
    for nom_role, noms in permissions_par_role.items():
        role = Group.objects.filter(name=nom_role).first()
        if role is None:
            continue
        for nom in noms:
            app_label, codename = nom.split(".")
            role.permissions.add(
                Permission.objects.get(content_type__app_label=app_label, codename=codename)
            )
