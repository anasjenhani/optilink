from decimal import Decimal

import pytest
from django.contrib.auth.models import Group, Permission
from django_otp import DEVICE_ID_SESSION_KEY
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.reseau.models import Magasin, Pays, Region, TauxTva
from apps.securite.models import Affectation, Utilisateur
from apps.stock.models import Article, MouvementStock, PrixArticle


@pytest.fixture
def reseau(db):
    # Réseau de test en France (euro, 2 décimales, sans timbre) ; la Tunisie a ses propres tests.
    france = Pays.objects.get(code="FR")
    nord = Region.objects.create(code="NORD", nom="Nord")
    sud = Region.objects.create(code="SUD", nom="Sud")
    return {
        "nord": nord,
        "sud": sud,
        "lille": Magasin.tous.create(code="M01", nom="Lille", region=nord, pays=france),
        "arras": Magasin.tous.create(code="M02", nom="Arras", region=nord, pays=france),
        "nice": Magasin.tous.create(code="M03", nom="Nice", region=sud, pays=france),
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


def tva(pays, taux):
    """Taux de TVA d'un pays, tel que créé par la migration (ex. tva(tunisie, 19))."""
    return TauxTva.objects.get(pays=pays, taux=taux)


# Magasin tunisien de départ (dinar à 3 décimales, TVA 19 %, timbre sur facture).
@pytest.fixture
def tunis(db):
    tunisie = Pays.objects.get(code="TN")
    region = Region.objects.create(code="GT", nom="Grand Tunis")
    return Magasin.tous.create(code="T01", nom="Tunis Centre", region=region, pays=tunisie)


@pytest.fixture
def monture(tunis):
    article = Article.objects.create(reference="MON-T", libelle="Monture", famille="monture")
    PrixArticle.objects.create(
        article=article, pays=tunis.pays, prix_vente_ttc=Decimal("289.500"), tva=tva(tunis.pays, 19)
    )
    MouvementStock.tous.create(magasin=tunis, article=article, quantite=3, type="reception")
    return article


@pytest.fixture
def societe(tunis):
    return Client.objects.create(
        nom="Trabelsi",
        prenom="Karim",
        societe="Optique Services SARL",
        adresse="12 rue de Marseille",
        code_postal="1000",
        ville="Tunis",
        matricule_fiscal="1234567/A/M/000",
        magasin_origine=tunis,
    )


def recevoir_verres(vente, utilisateur):
    """Commande au fournisseur les verres d'une commande client, puis les réceptionne."""
    from apps.achats.models import Fournisseur
    from apps.achats.services import passer_commande, receptionner

    fournisseur, _ = Fournisseur.objects.get_or_create(
        nom="Labo Verres", defaults={"pays": vente.magasin.pays}
    )
    lignes = [
        {"ligne_vente": ligne.pk} for ligne in vente.lignes.all() if ligne.article.sur_commande
    ]
    commande = passer_commande(
        magasin=vente.magasin, fournisseur=fournisseur, lignes=lignes, auteur=utilisateur
    )
    return receptionner(commande=commande, utilisateur=utilisateur)
