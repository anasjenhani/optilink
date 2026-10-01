import pytest
from django.contrib.auth.models import Group, Permission
from django_otp import DEVICE_ID_SESSION_KEY
from django_otp.plugins.otp_totp.models import TOTPDevice
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


def permission(nom):
    app_label, codename = nom.split(".")
    return Permission.objects.get(content_type__app_label=app_label, codename=codename)


@pytest.fixture
def creer_role(db):
    def _creer(nom, *permissions):
        role = Group.objects.create(name=nom)
        role.permissions.set([permission(p) for p in permissions])
        return role

    return _creer


@pytest.fixture
def role(creer_role):
    return creer_role("Rôle de test", "reseau.view_magasin")


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
    """Client connecté, second facteur déjà validé pour la session."""

    def _client(utilisateur):
        device = TOTPDevice.objects.create(user=utilisateur, name="test", confirmed=True)
        client = APIClient()
        client.force_login(utilisateur)
        session = client.session
        session[DEVICE_ID_SESSION_KEY] = device.persistent_id
        session.save()
        return client

    return _client


@pytest.fixture(autouse=True)
def cache_vide():
    """Les limites de débit sont comptées dans le cache : chaque test repart de zéro."""
    from django.core.cache import cache

    cache.clear()


@pytest.fixture
def affecter(creer_role, creer_utilisateur):
    roles = {}

    def _affecter(nom, *permissions, **perimetre):
        cle = tuple(sorted(permissions))
        if cle not in roles:
            roles[cle] = creer_role(f"Rôle {len(roles)}", *permissions)
        utilisateur = creer_utilisateur(nom)
        Affectation.objects.create(utilisateur=utilisateur, role=roles[cle], **perimetre)
        return utilisateur

    return _affecter
