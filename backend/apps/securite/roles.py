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
