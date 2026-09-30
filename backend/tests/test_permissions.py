import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from apps.securite.models import Affectation
from apps.securite.roles import ROLES_DE_DEPART
from core.permissions import PermissionsParAction


def test_roles_de_depart_crees(db):
    assert set(ROLES_DE_DEPART) <= set(Group.objects.values_list("name", flat=True))
    admin = Group.objects.get(name="Administrateur système")
    vendeur = Group.objects.get(name="Vendeur")
    assert admin.permissions.filter(codename="add_affectation").exists()
    assert {"view_magasin", "view_region"} <= set(
        vendeur.permissions.values_list("codename", flat=True)
    )
    assert not vendeur.permissions.filter(codename="add_affectation").exists()


def test_role_sans_la_permission_refuse(reseau, creer_role, creer_utilisateur, client_de):
    utilisateur = creer_utilisateur("sans_droit")
    Affectation.objects.create(
        utilisateur=utilisateur,
        role=creer_role("Sans lecture"),
        portee="magasin",
        magasin=reseau["lille"],
    )
    assert client_de(utilisateur).get("/api/v1/magasins/").status_code == 403


def test_les_droits_dependent_du_magasin(reseau, creer_role, creer_utilisateur):
    utilisateur = creer_utilisateur("double")
    responsable = creer_role("Resp test", "reseau.view_magasin", "reseau.change_magasin")
    lecteur = creer_role("Lecteur test", "reseau.view_magasin")
    Affectation.objects.create(
        utilisateur=utilisateur, role=responsable, portee="magasin", magasin=reseau["lille"]
    )
    Affectation.objects.create(
        utilisateur=utilisateur, role=lecteur, portee="region", region=reseau["sud"]
    )

    assert utilisateur.has_perm("reseau.change_magasin")
    assert utilisateur.has_perm("reseau.change_magasin", reseau["lille"])
    assert not utilisateur.has_perm("reseau.change_magasin", reseau["nice"])
    assert utilisateur.has_perm("reseau.view_magasin", reseau["nice"])
    assert not utilisateur.has_perm("reseau.view_magasin", reseau["arras"])


def test_affectation_reseau_couvre_tous_les_magasins(reseau, creer_role, creer_utilisateur):
    utilisateur = creer_utilisateur("siege")
    Affectation.objects.create(
        utilisateur=utilisateur, role=creer_role("Siège", "reseau.view_magasin"), portee="reseau"
    )
    assert all(
        utilisateur.has_perm("reseau.view_magasin", m)
        for m in reseau.values()
        if hasattr(m, "region_id")
    )


def test_appartenance_directe_a_un_groupe_ne_donne_rien(reseau, creer_role, creer_utilisateur):
    utilisateur = creer_utilisateur("groupe")
    utilisateur.groups.add(creer_role("Direct", "reseau.view_magasin"))
    assert not utilisateur.has_perm("reseau.view_magasin")


class VueSansDeclaration(APIView):
    permission_classes = [PermissionsParAction]

    def get(self, request):
        return None


class VueDeclaree(APIView):
    permission_classes = [PermissionsParAction]
    permissions_requises = {"get": "reseau.view_region"}

    def get(self, request):
        from rest_framework.response import Response

        return Response({})

    def post(self, request):
        return None


@pytest.fixture
def lecteur_regions(creer_role, creer_utilisateur):
    utilisateur = creer_utilisateur("lecteur")
    Affectation.objects.create(
        utilisateur=utilisateur, role=creer_role("Régions", "reseau.view_region"), portee="reseau"
    )
    return utilisateur


def appeler(vue, methode, utilisateur):
    requete = getattr(APIRequestFactory(), methode)("/")
    force_authenticate(requete, user=utilisateur)
    return vue.as_view()(requete).status_code


def test_refus_par_defaut_sans_permission_declaree(lecteur_regions):
    assert appeler(VueSansDeclaration, "get", lecteur_regions) == 403


def test_permission_declaree_par_methode(lecteur_regions):
    assert appeler(VueDeclaree, "get", lecteur_regions) == 200
    assert appeler(VueDeclaree, "post", lecteur_regions) == 403
