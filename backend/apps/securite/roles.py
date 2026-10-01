"""Rôles de départ (section 13 du document d'architecture).

Ils sont créés une seule fois, avec leurs permissions initiales ; le siège les ajuste ensuite
dans l'administration. Chaque lot ajoutera les permissions de ses modules à ces rôles.
"""

from django.contrib.auth.management import create_permissions
from django.contrib.auth.models import Group, Permission

LECTURE_RESEAU = ["reseau.view_magasin", "reseau.view_region"]

LECTURE_ADMINISTRATION = LECTURE_RESEAU + [
    "securite.view_utilisateur",
    "securite.view_affectation",
    "securite.view_evenementsecurite",
    "auth.view_group",
    "auditlog.view_logentry",
]

ROLES_DE_DEPART = {
    # Gère comptes, rôles et magasins, sans accès aux données métier.
    "Administrateur système": LECTURE_ADMINISTRATION
    + [
        "reseau.add_magasin",
        "reseau.change_magasin",
        "reseau.add_region",
        "reseau.change_region",
        "securite.add_utilisateur",
        "securite.change_utilisateur",
        "securite.add_affectation",
        "securite.change_affectation",
        "securite.delete_affectation",
        "auth.add_group",
        "auth.change_group",
    ],
    "Direction": LECTURE_ADMINISTRATION,
    "Responsable régional": LECTURE_RESEAU,
    "Responsable magasin": LECTURE_RESEAU,
    "Opticien": LECTURE_RESEAU,
    "Vendeur": LECTURE_RESEAU,
    "Logisticien": LECTURE_RESEAU,
    "Comptable": LECTURE_RESEAU,
    "Gestionnaire RH": LECTURE_RESEAU,
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
    "Direction": VENTES_LECTURE + STOCK_LECTURE,
    "Responsable régional": VENTES_COMPLET + STOCK_COMPLET,
    "Responsable magasin": VENTES_COMPLET + STOCK_COMPLET,
    "Opticien": VENTES_COMPLET + STOCK_LIMITE,
    "Vendeur": VENTES_LIMITE + STOCK_LECTURE,
    "Logisticien": STOCK_COMPLET,
    "Comptable": VENTES_LECTURE + STOCK_LECTURE,
}

# Lot Vendre : colonne « Clients & optique ». Seuls opticiens et responsables de magasin
# voient les ordonnances (données de santé) ; la direction voit qui les a consultées.
CLIENTS_COMPLET = ["crm.view_client", "crm.add_client", "crm.change_client"]
CLIENTS_LECTURE = ["crm.view_client"]
ORDONNANCES = ["optique.view_prescription", "optique.add_prescription"]

PERMISSIONS_CLIENTS_OPTIQUE = {
    "Direction": CLIENTS_LECTURE + ["optique.view_accesprescription"],
    "Responsable régional": CLIENTS_LECTURE,
    "Responsable magasin": CLIENTS_COMPLET + ORDONNANCES,
    "Opticien": CLIENTS_COMPLET + ORDONNANCES,
    "Vendeur": CLIENTS_COMPLET,
}

# Paramétrage par pays (taux de TVA, timbre, monnaie) : réglé par l'administrateur, consulté
# par la direction. Les prix de vente suivent la colonne Stock « Complet ».
PRIX_COMPLET = ["stock.view_prixarticle", "stock.add_prixarticle", "stock.change_prixarticle"]
PERMISSIONS_PARAMETRAGE = {
    "Administrateur système": [
        "reseau.view_pays",
        "reseau.add_pays",
        "reseau.change_pays",
        "reseau.view_tauxtva",
        "reseau.add_tauxtva",
        "reseau.change_tauxtva",
        "reseau.delete_tauxtva",
    ],
    "Direction": ["reseau.view_pays", "reseau.view_tauxtva", "stock.view_prixarticle"],
    "Responsable régional": PRIX_COMPLET,
    "Responsable magasin": PRIX_COMPLET,
    "Logisticien": PRIX_COMPLET,
    "Comptable": ["reseau.view_pays", "reseau.view_tauxtva", "stock.view_prixarticle"],
}

for _par_role in (PERMISSIONS_CAISSE_STOCK, PERMISSIONS_CLIENTS_OPTIQUE, PERMISSIONS_PARAMETRAGE):
    for _nom, _permissions in _par_role.items():
        ROLES_DE_DEPART[_nom] = ROLES_DE_DEPART[_nom] + _permissions


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
