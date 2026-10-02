import datetime

import pytest
from auditlog.context import set_actor
from auditlog.models import LogEntry
from django.utils import timezone

from apps.reseau.models import Magasin
from apps.securite.models import Affectation, EvenementSecurite, Utilisateur
from apps.securite.tasks import desactiver_comptes_inactifs


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
