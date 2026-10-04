import datetime

import pytest
from auditlog.context import set_actor
from auditlog.models import LogEntry
from django.contrib.auth.models import Group
from django.utils import timezone

from apps.reseau.models import Magasin
from apps.securite.models import Affectation, EvenementSecurite, Utilisateur
from apps.securite.privileges import CODES
from apps.securite.tasks import desactiver_comptes_inactifs
from tests.test_acces import codes


def test_modification_d_un_magasin_journalisee_avec_son_auteur(reseau, creer_utilisateur):
    auteur = creer_utilisateur("auteur")
    lille = Magasin.tous.get(code="M01")
    with set_actor(auteur):
        lille.telephone = "0320000000"
        lille.save()

    entree = LogEntry.objects.get_for_object(lille).filter(action=LogEntry.Action.UPDATE).get()
    assert entree.actor == auteur
    assert entree.changes_dict["telephone"] == ["", "0320000000"]


def test_affectation_journalisee(reseau, role, creer_utilisateur):
    affectation = Affectation.objects.create(
        utilisateur=creer_utilisateur("x"), role=role, portee="reseau"
    )
    assert LogEntry.objects.get_for_object(affectation).count() == 1


def test_mot_de_passe_jamais_journalise(db):
    utilisateur = Utilisateur.objects.create_user("secret", password="ancien")
    utilisateur.set_password("nouveau-mot-de-passe")
    utilisateur.save()
    for entree in LogEntry.objects.get_for_object(utilisateur):
        assert "password" not in entree.changes_dict


def test_evenement_de_securite_non_modifiable(db):
    evenement = EvenementSecurite.objects.create(type="connexion_echouee", identifiant="x")
    with pytest.raises(ValueError):
        evenement.save()
    with pytest.raises(ValueError):
        evenement.delete()


def test_comptes_inactifs_desactives(db):
    ancien = timezone.now() - datetime.timedelta(days=91)
    dormant = Utilisateur.objects.create_user("dormant", last_login=ancien)
    jamais = Utilisateur.objects.create_user("jamais")
    Utilisateur.objects.filter(pk=jamais.pk).update(date_joined=ancien)
    actif = Utilisateur.objects.create_user("actif", last_login=timezone.now())
    admin = Utilisateur.objects.create_superuser("admin", last_login=ancien)

    assert sorted(desactiver_comptes_inactifs()) == ["dormant", "jamais"]

    etats = dict(Utilisateur.objects.values_list("username", "is_active"))
    assert etats == {"dormant": False, "jamais": False, "actif": True, "admin": True}
    assert EvenementSecurite.objects.filter(type="compte_desactive").count() == 2
    del dormant, actif, admin


def test_journal_des_droits_lisible(reseau, client_de):
    """Profils donnés, modifiés, retirés et privilèges changés : lisibles dans l'admin."""
    anas = Utilisateur.objects.create_superuser("anas")
    Affectation.objects.create(
        utilisateur=anas, role=Group.objects.get(name="Administrateur Global"), portee="reseau"
    )
    navigateur = client_de(anas)
    sami = Utilisateur.objects.create_user("sami")
    vendeur, caissier = Group.objects.get(name="Vendeur"), Group.objects.get(name="Caissier")
    affectation = Affectation.objects.create(
        utilisateur=sami, role=vendeur, portee="magasin", magasin=reseau["lille"]
    )
    url = f"/api/v1/securite/utilisateurs/{sami.pk}/"
    corps = {"affectations": [{"id": affectation.pk, "profil": caissier.pk, "portee": "reseau"}]}
    assert navigateur.patch(url, corps, format="json").status_code == 200
    privileges = sorted(codes("Vendeur") & CODES | {"ventes.appliquer_remise"})
    reponse = navigateur.patch(
        f"/api/v1/securite/profils/{vendeur.pk}/", {"privileges": privileges}, format="json"
    )
    assert reponse.status_code == 200

    modification = LogEntry.objects.get_for_object(affectation).get(action=LogEntry.Action.UPDATE)
    assert modification.actor == anas

    page = navigateur.get("/admin/securite/modificationdroits/").content.decode()
    assert "Profil : Vendeur → Caissier" in page
    assert "Portée : Magasin → Tout le réseau" in page
    assert "Magasin : M01 Lille → (vide)" in page
    assert "Privilèges ajoutés : Accorder une remise" in page
    # Les autres modifications (magasins, clients…) restent dans l'historique général.
    assert "Optique du Nord" not in page


def test_reinitialisation_mfa_journalisee(admin_global_securite):
    navigateur, cible = admin_global_securite
    url = f"/api/v1/securite/utilisateurs/{cible.pk}/reinitialiser-mfa/"
    assert navigateur.post(url).status_code == 204
    evenement = EvenementSecurite.objects.get(type="mfa_reinitialisee")
    assert (evenement.utilisateur, evenement.details) == (cible, "par anas")


@pytest.fixture
def admin_global_securite(db, client_de):
    anas = Utilisateur.objects.create_user("anas")
    Affectation.objects.create(
        utilisateur=anas, role=Group.objects.get(name="Administrateur Global"), portee="reseau"
    )
    return client_de(anas), Utilisateur.objects.create_user("sami")
