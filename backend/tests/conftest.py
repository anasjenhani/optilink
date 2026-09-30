import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from apps.reseau.models import Magasin, Region
from apps.securite.models import Affectation, Utilisateur


@pytest.fixture
def reseau(db):
    nord = Region.objects.create(code="NORD", nom="Nord")
    sud = Region.objects.create(code="SUD", nom="Sud")
    return {
        "nord": nord,
        "sud": sud,
        "lille": Magasin.tous.create(code="M01", nom="Lille", region=nord),
        "arras": Magasin.tous.create(code="M02", nom="Arras", region=nord),
        "nice": Magasin.tous.create(code="M03", nom="Nice", region=sud),
    }


@pytest.fixture
def role(db):
    return Group.objects.create(name="Vendeur")


@pytest.fixture
def creer_utilisateur(db, role):
    def _creer(nom, **affectation):
        utilisateur = Utilisateur.objects.create_user(nom, password="x")
        if affectation:
            Affectation.objects.create(utilisateur=utilisateur, role=role, **affectation)
        return utilisateur

    return _creer


@pytest.fixture
def client_de():
    def _client(utilisateur):
        client = APIClient()
        client.force_login(utilisateur)
        return client

    return _client
