import pytest
from django_otp.oath import totp
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework.test import APIClient

from apps.securite.models import EvenementSecurite, Utilisateur

MOT_DE_PASSE = "Un-mot-de-passe-solide-2026"


@pytest.fixture
def opticien(db, reseau, role, settings):
    from apps.securite.models import Affectation

    settings.MFA_PROFILS = [role.name]  # Profil soumis au code OTP dans ces tests.
    utilisateur = Utilisateur.objects.create_user("opticien", password=MOT_DE_PASSE)
    Affectation.objects.create(
        utilisateur=utilisateur, role=role, portee="magasin", magasin=reseau["lille"]
    )
    return utilisateur


def connecter(client, identifiant="opticien", mot_de_passe=MOT_DE_PASSE):
    return client.post(
        "/api/v1/auth/connexion/",
        {"identifiant": identifiant, "mot_de_passe": mot_de_passe},
        format="json",
    )


def activer_mfa(client):
    client.post("/api/v1/auth/mfa/activation/")
    device = TOTPDevice.objects.get(confirmed=False)
    return client.post(
        "/api/v1/auth/mfa/activation/confirmation/",
        {"code": f"{totp(device.bin_key):06d}"},
        format="json",
    )


def types_evenements():
    return list(EvenementSecurite.objects.order_by("id").values_list("type", flat=True))


def test_session_anonyme_pose_le_cookie_csrf(client, db):  # le middleware pose la RLS
    reponse = client.get("/api/v1/auth/session/")
    assert reponse.json() == {"authentifie": False, "mfa": None, "utilisateur": None}
    assert "csrftoken" in reponse.cookies


def test_connexion_exige_le_jeton_csrf(opticien):
    client = APIClient(enforce_csrf_checks=True)
    assert connecter(client).status_code == 403


def test_mauvais_mot_de_passe_refuse_et_journalise(opticien):
    reponse = connecter(APIClient(), mot_de_passe="faux")
    assert reponse.status_code == 400
    evenement = EvenementSecurite.objects.get()
    assert (evenement.type, evenement.identifiant) == ("connexion_echouee", "opticien")


def test_premiere_connexion_impose_l_activation_mfa(opticien):
    client = APIClient()
    session = connecter(client).json()

    assert session["mfa"] == "a_activer"
    assert session["utilisateur"]["permissions"] == []
    assert client.get("/api/v1/magasins/").status_code == 403


def test_profil_hors_mfa_profils_se_connecte_avec_le_mot_de_passe(opticien, settings):
    settings.MFA_PROFILS = ["Administrateur Global"]
    client = APIClient()
    session = connecter(client).json()

    assert session["mfa"] == "non_requise"
    assert "reseau.view_magasin" in session["utilisateur"]["permissions"]
    assert client.get("/api/v1/magasins/").status_code == 200


def test_compte_d_administration_doit_toujours_activer_le_code(opticien, settings):
    settings.MFA_PROFILS = []
    opticien.is_staff = True
    opticien.save()
    client = APIClient()

    assert connecter(client).json()["mfa"] == "a_activer"
    assert client.get("/api/v1/magasins/").status_code == 403
    assert client.get("/admin/").status_code == 302  # /admin/ exige toujours le code.


def test_activation_mfa_ouvre_l_acces_et_donne_des_codes_de_secours(opticien):
    client = APIClient()
    connecter(client)
    activation = client.post("/api/v1/auth/mfa/activation/").json()
    assert activation["uri"].startswith("otpauth://totp/OptiLink")
    assert activation["qr_svg"].lstrip().startswith("<?xml")

    reponse = activer_mfa(client)

    assert reponse.status_code == 200
    assert len(set(reponse.json()["codes_secours"])) == 10
    assert reponse.json()["session"]["mfa"] == "verifiee"
    assert "reseau.view_magasin" in reponse.json()["session"]["utilisateur"]["permissions"]
    assert client.get("/api/v1/magasins/").status_code == 200
    assert "mfa_activee" in types_evenements()


def test_code_d_activation_faux_refuse(opticien):
    client = APIClient()
    connecter(client)
    client.post("/api/v1/auth/mfa/activation/")
    reponse = client.post(
        "/api/v1/auth/mfa/activation/confirmation/", {"code": "000000"}, format="json"
    )
    assert reponse.status_code == 400
    assert not TOTPDevice.objects.filter(confirmed=True).exists()


def test_connexion_suivante_demande_le_code(opticien):
    premier = APIClient()
    connecter(premier)
    codes_secours = activer_mfa(premier).json()["codes_secours"]

    client = APIClient()
    assert connecter(client).json()["mfa"] == "a_verifier"
    assert client.get("/api/v1/magasins/").status_code == 403
    # Impossible d'enregistrer un autre téléphone sans avoir validé le code actuel.
    assert client.post("/api/v1/auth/mfa/activation/").status_code == 403

    bon = client.post("/api/v1/auth/mfa/verification/", {"code": codes_secours[0]}, format="json")
    assert bon.json()["mfa"] == "verifiee"
    assert client.get("/api/v1/magasins/").status_code == 200
    assert types_evenements()[-1] == "mfa_reussie"


def test_code_mfa_faux_refuse_et_journalise(opticien):
    premier = APIClient()
    connecter(premier)
    activer_mfa(premier)

    client = APIClient()
    connecter(client)
    faux = client.post("/api/v1/auth/mfa/verification/", {"code": "000000"}, format="json")
    assert faux.status_code == 400
    assert client.get("/api/v1/magasins/").status_code == 403
    assert types_evenements()[-1] == "mfa_echouee"


def test_un_code_de_secours_ne_sert_qu_une_fois(opticien):
    premier = APIClient()
    connecter(premier)
    code = activer_mfa(premier).json()["codes_secours"][0]

    for attendu in (200, 400):
        client = APIClient()
        connecter(client)
        reponse = client.post("/api/v1/auth/mfa/verification/", {"code": code}, format="json")
        assert reponse.status_code == attendu


def test_deconnexion(opticien):
    client = APIClient()
    connecter(client)
    assert client.post("/api/v1/auth/deconnexion/").status_code == 204
    assert client.get("/api/v1/auth/session/").json()["authentifie"] is False
    assert types_evenements() == ["connexion_reussie", "deconnexion"]


def test_compte_desactive_ne_peut_pas_se_connecter(opticien):
    opticien.is_active = False
    opticien.save()
    assert connecter(APIClient()).status_code == 400
