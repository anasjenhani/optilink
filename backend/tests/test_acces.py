"""Accès et sécurité : profils, privilèges et utilisateurs gérés depuis l'application."""

import pytest
from django.contrib.auth.models import Group, Permission
from django_otp.plugins.otp_totp.models import TOTPDevice

from apps.securite.models import Affectation, Utilisateur
from apps.securite.privileges import CODES
from apps.securite.roles import ROLES_DE_DEPART

PROFILS = [
    "Administrateur Global",
    "Administrateur",
    "Responsable de magasin",
    "Opticien",
    "Vendeur",
    "Caissier",
    "Atelier",
    "Commande",
    "Ressources Humaines",
    "Comptabilité & Finance",
    "Achats & Gestionnaire de Stock",
]


def profil(nom):
    return Group.objects.get(name=nom)


def codes(nom):
    return {
        f"{p.content_type.app_label}.{p.codename}"
        for p in profil(nom).permissions.select_related("content_type")
    }


@pytest.fixture
def donner(db):
    def _donner(utilisateur, nom, **perimetre):
        perimetre = perimetre or {"portee": "reseau"}
        Affectation.objects.create(utilisateur=utilisateur, role=profil(nom), **perimetre)
        return utilisateur

    return _donner


@pytest.fixture
def admin_global(donner):
    return donner(Utilisateur.objects.create_user("global"), "Administrateur Global")


@pytest.fixture
def administrateur(donner):
    return donner(Utilisateur.objects.create_user("admin"), "Administrateur")


def nouvel_utilisateur(**affectation):
    return {
        "identifiant": "sami",
        "prenom": "Sami",
        "nom": "Ben Ali",
        "mot_de_passe": "Provisoire-2026!",
        "affectations": [affectation] if affectation else [],
    }


def test_profils_de_depart(db):
    assert set(ROLES_DE_DEPART) == set(PROFILS)
    assert set(PROFILS) <= set(Group.objects.values_list("name", flat=True))
    assert codes("Administrateur Global") >= CODES
    assert "ventes.appliquer_remise" not in codes("Caissier")
    assert "ventes.add_vente" in codes("Caissier")
    assert not any(c.startswith(("ventes.", "crm.", "optique.")) for c in codes("Administrateur"))


def test_tous_les_privileges_existent(db):
    existants = {
        f"{p.content_type.app_label}.{p.codename}"
        for p in Permission.objects.select_related("content_type")
    }
    assert CODES <= existants


def test_catalogue_des_privileges(admin_global, client_de):
    reponse = client_de(admin_global).get("/api/v1/securite/privileges/")
    assert reponse.status_code == 200
    modules = {m["module"]: m["privileges"] for m in reponse.json()}
    assert {"code": "ventes.appliquer_remise", "libelle": "Accorder une remise"} in modules[
        "Caisse et ventes"
    ]


def test_creer_un_utilisateur(reseau, administrateur, client_de):
    lille = reseau["lille"]
    corps = nouvel_utilisateur(
        profil=profil("Vendeur").pk, portee="magasin", magasin=str(lille.public_id)
    )
    reponse = client_de(administrateur).post("/api/v1/securite/utilisateurs/", corps, format="json")
    assert reponse.status_code == 201, reponse.json()
    sami = Utilisateur.objects.get(username="sami")
    assert sami.check_password("Provisoire-2026!") and not sami.is_staff
    assert reponse.json()["affectations"][0]["perimetre"] == str(lille)
    assert sami.magasins_autorises() == {lille.pk}


def test_mot_de_passe_trop_faible(administrateur, client_de):
    corps = nouvel_utilisateur() | {"mot_de_passe": "1234"}
    reponse = client_de(administrateur).post("/api/v1/securite/utilisateurs/", corps, format="json")
    assert reponse.status_code == 400 and "mot_de_passe" in reponse.json()


def test_on_ne_donne_pas_plus_que_ce_qu_on_a(administrateur, client_de):
    corps = nouvel_utilisateur(profil=profil("Administrateur Global").pk, portee="reseau")
    reponse = client_de(administrateur).post("/api/v1/securite/utilisateurs/", corps, format="json")
    assert reponse.status_code == 403
    assert not Utilisateur.objects.filter(username="sami").exists()


def test_perimetre_limite_a_ses_magasins(reseau, donner, client_de):
    admin_lille = donner(
        Utilisateur.objects.create_user("admin_lille"),
        "Administrateur",
        portee="magasin",
        magasin=reseau["lille"],
    )
    client = client_de(admin_lille)
    for affectation in (
        {"portee": "magasin", "magasin": str(reseau["arras"].public_id)},
        {"portee": "reseau"},
    ):
        corps = nouvel_utilisateur(profil=profil("Vendeur").pk, **affectation)
        reponse = client.post("/api/v1/securite/utilisateurs/", corps, format="json")
        assert reponse.status_code == 403
    autre = donner(
        Utilisateur.objects.create_user("vendeur_nice"),
        "Vendeur",
        portee="magasin",
        magasin=reseau["nice"],
    )
    identifiants = [u["identifiant"] for u in client.get("/api/v1/securite/utilisateurs/").json()]
    assert "admin_lille" in identifiants and autre.username not in identifiants


def test_pas_de_changement_de_ses_propres_profils(admin_global, client_de):
    reponse = client_de(admin_global).patch(
        f"/api/v1/securite/utilisateurs/{admin_global.pk}/", {"affectations": []}, format="json"
    )
    assert reponse.status_code == 403
    assert admin_global.affectations.count() == 1


def test_modifier_et_retirer_une_affectation(reseau, admin_global, donner, client_de):
    sami = donner(
        Utilisateur.objects.create_user("sami"),
        "Vendeur",
        portee="magasin",
        magasin=reseau["lille"],
    )
    affectation = sami.affectations.get()
    client = client_de(admin_global)
    url = f"/api/v1/securite/utilisateurs/{sami.pk}/"
    corps = {
        "affectations": [
            {"id": affectation.pk, "profil": profil("Caissier").pk, "portee": "reseau"},
        ]
    }
    assert client.patch(url, corps, format="json").status_code == 200
    affectation.refresh_from_db()
    assert (affectation.role.name, affectation.portee, affectation.magasin) == (
        "Caissier",
        "reseau",
        None,
    )
    assert client.patch(url, {"affectations": [], "actif": False}, format="json").status_code == 200
    sami.refresh_from_db()
    assert not sami.is_active and not sami.affectations.exists()


def test_retirer_un_profil_plus_eleve_est_refuse(administrateur, admin_global, client_de):
    url = f"/api/v1/securite/utilisateurs/{admin_global.pk}/"
    reponse = client_de(administrateur).patch(url, {"affectations": []}, format="json")
    assert reponse.status_code == 403
    assert admin_global.affectations.exists()


def test_modifier_les_privileges_d_un_profil(admin_global, client_de):
    vendeur = profil("Vendeur")
    hors_catalogue = Permission.objects.get(codename="view_tauxtva")
    vendeur.permissions.remove(hors_catalogue)
    autre = Permission.objects.get(codename="view_totpdevice")
    vendeur.permissions.add(autre)
    privileges = sorted(codes("Vendeur") & CODES | {"ventes.appliquer_remise"})
    reponse = client_de(admin_global).patch(
        f"/api/v1/securite/profils/{vendeur.pk}/", {"privileges": privileges}, format="json"
    )
    assert reponse.status_code == 200, reponse.json()
    assert "ventes.appliquer_remise" in reponse.json()["privileges"]
    assert "ventes.appliquer_remise" in codes("Vendeur")
    assert "otp_totp.view_totpdevice" in codes("Vendeur")  # hors catalogue : gardé


def test_privileges_d_administration_reserves(administrateur, client_de):
    client = client_de(administrateur)
    vendeur = profil("Vendeur")
    url = f"/api/v1/securite/profils/{vendeur.pk}/"
    metier = sorted(codes("Vendeur") & CODES | {"ventes.appliquer_remise"})
    assert client.patch(url, {"privileges": metier}, format="json").status_code == 200
    reponse = client.patch(url, {"privileges": [*metier, "auth.delete_group"]}, format="json")
    assert reponse.status_code == 403
    assert "Supprimer un profil" in reponse.json()["detail"]
    assert "auth.delete_group" not in codes("Vendeur")


def test_pas_de_modification_de_son_propre_profil(administrateur, client_de):
    admin = profil("Administrateur")
    reponse = client_de(administrateur).patch(
        f"/api/v1/securite/profils/{admin.pk}/",
        {"privileges": sorted(codes("Administrateur") & CODES | {"ventes.add_vente"})},
        format="json",
    )
    assert reponse.status_code == 403
    assert "ventes.add_vente" not in codes("Administrateur")


def test_creer_et_supprimer_un_profil(admin_global, donner, client_de):
    client = client_de(admin_global)
    reponse = client.post(
        "/api/v1/securite/profils/",
        {"nom": "Stagiaire", "privileges": ["stock.view_article"]},
        format="json",
    )
    assert reponse.status_code == 201
    assert reponse.json() | {"id": 0} == {
        "id": 0,
        "nom": "Stagiaire",
        "privileges": ["stock.view_article"],
        "utilisateurs": 0,
    }
    doublon = client.post("/api/v1/securite/profils/", {"nom": "stagiaire"}, format="json")
    assert doublon.status_code == 400
    occupe = profil("Vendeur")
    donner(Utilisateur.objects.create_user("v"), "Vendeur")
    assert client.delete(f"/api/v1/securite/profils/{occupe.pk}/").status_code == 400
    url = f"/api/v1/securite/profils/{reponse.json()['id']}/"
    assert client.delete(url).status_code == 204


def test_reinitialiser_la_double_authentification(admin_global, client_de):
    sami = Utilisateur.objects.create_user("sami")
    TOTPDevice.objects.create(user=sami, name="tel", confirmed=True)
    client = client_de(admin_global)
    liste = client.get("/api/v1/securite/utilisateurs/").json()
    assert next(u for u in liste if u["identifiant"] == "sami")["mfa_active"]
    reponse = client.post(f"/api/v1/securite/utilisateurs/{sami.pk}/reinitialiser-mfa/")
    assert reponse.status_code == 204
    assert not TOTPDevice.objects.filter(user=sami).exists()


def test_vendeur_sans_acces(reseau, donner, client_de):
    vendeur = donner(
        Utilisateur.objects.create_user("v"), "Vendeur", portee="magasin", magasin=reseau["lille"]
    )
    client = client_de(vendeur)
    assert client.get("/api/v1/securite/utilisateurs/").status_code == 403
    assert client.get("/api/v1/securite/profils/").status_code == 403
