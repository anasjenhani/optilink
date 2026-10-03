from datetime import date, timedelta

import pytest
from django.contrib.auth.models import Group
from django.test import override_settings

from apps.crm.models import Client
from apps.optique.models import AccesPrescription, Prescription
from core import chiffrement

CLIENTS = ("crm.view_client", "crm.add_client", "crm.change_client")
ORDONNANCES = CLIENTS + ("optique.view_prescription", "optique.add_prescription")


@pytest.fixture
def dupont(reseau):
    return Client.objects.create(
        nom="Dupont", prenom="Marie", telephone="0601020304", magasin_origine=reseau["lille"]
    )


def corps_ordonnance(client, magasin, **mesures):
    od = {"sphere": "-2.25", "cylindre": "-0.50", "axe": 90}
    og = {"sphere": "-1.75"}
    return {
        "client": str(client.public_id),
        "magasin_saisie": str(magasin.public_id),
        "type": "lunettes",
        "date_prescription": str(date.today() - timedelta(days=10)),
        "prescripteur": "Dr Martin",
        "prescripteur_identifiant": "10001234567",
        "mesures": {"od": od, "og": og, "ecart_pupillaire": "63.0", **mesures},
    }


# Clients


def test_creation_client_dans_son_magasin(affecter, client_de, reseau):
    vendeur = affecter("vendeur", *CLIENTS, portee="magasin", magasin=reseau["lille"])
    api = client_de(vendeur)
    corps = {"nom": "Durand", "prenom": "Paul", "telephone": "0612345678"}

    reponse = api.post(
        "/api/v1/clients/", {**corps, "magasin_origine": str(reseau["lille"].public_id)}
    )
    assert reponse.status_code == 201, reponse.json()

    # Arras est hors de son périmètre : le magasin n'est même pas trouvé.
    reponse = api.post(
        "/api/v1/clients/", {**corps, "magasin_origine": str(reseau["arras"].public_id)}
    )
    assert reponse.status_code == 400


def test_client_partage_par_le_reseau_et_recherche(affecter, client_de, reseau, dupont):
    vendeur_nice = affecter("vnice", *CLIENTS, portee="magasin", magasin=reseau["nice"])
    api = client_de(vendeur_nice)
    reponse = api.get("/api/v1/clients/", {"recherche": "dupont marie"})
    assert [c["nom"] for c in reponse.json()["results"]] == ["Dupont"]
    assert api.get("/api/v1/clients/", {"recherche": "0601"}).json()["count"] == 1
    assert api.get("/api/v1/clients/", {"recherche": "inconnu"}).json()["count"] == 0


def test_magasin_d_origine_ne_change_pas(affecter, client_de, reseau, dupont):
    vendeur = affecter("vendeur", *CLIENTS, portee="reseau")
    reponse = client_de(vendeur).patch(
        f"/api/v1/clients/{dupont.public_id}/",
        {"telephone": "0700000000", "magasin_origine": str(reseau["nice"].public_id)},
        format="json",
    )
    assert reponse.status_code == 200
    dupont.refresh_from_db()
    assert (dupont.telephone, dupont.magasin_origine) == ("0700000000", reseau["lille"])


def test_fiche_complete_et_client_professionnel(affecter, client_de, reseau):
    vendeur = affecter("vendeur", *CLIENTS, portee="magasin", magasin=reseau["lille"])
    api = client_de(vendeur)
    fiche = {
        "civilite": "m",
        "nom": "Ben Salah",
        "prenom": "Karim",
        "date_naissance": "1980-04-12",
        "telephone": "71000000",
        "telephone_2": "98123456",
        "email": "karim@exemple.tn",
        "adresse": "12 rue de Marseille",
        "code_postal": "1000",
        "ville": "Tunis",
        "magasin_origine": str(reseau["lille"].public_id),
    }
    # Un matricule fiscal va avec la société.
    sans_societe = api.post(
        "/api/v1/clients/", {**fiche, "matricule_fiscal": "1234567/a/m/000"}, format="json"
    )
    assert sans_societe.status_code == 400
    assert "societe" in sans_societe.json()

    cree = api.post(
        "/api/v1/clients/",
        {**fiche, "societe": "Optique Services SARL", "matricule_fiscal": " 1234567/a/m/000 "},
        format="json",
    )
    assert cree.status_code == 201, cree.json()
    assert {k: cree.json()[k] for k in ("telephone_2", "societe", "matricule_fiscal")} == {
        "telephone_2": "98123456",
        "societe": "Optique Services SARL",
        "matricule_fiscal": "1234567/A/M/000",
    }
    for recherche in ("98123", "optique services", "1234567"):
        trouves = api.get("/api/v1/clients/", {"recherche": recherche}).json()["results"]
        assert [c["nom"] for c in trouves] == ["Ben Salah"], recherche


def test_pas_de_suppression_de_client(affecter, client_de, dupont):
    vendeur = affecter("vendeur", *CLIENTS, "crm.delete_client", portee="reseau")
    assert client_de(vendeur).delete(f"/api/v1/clients/{dupont.public_id}/").status_code == 405


# Ordonnances


def test_vendeur_ne_voit_pas_les_ordonnances(affecter, client_de, reseau, dupont):
    vendeur = affecter("vendeur", *CLIENTS, portee="magasin", magasin=reseau["lille"])
    api = client_de(vendeur)
    assert api.get("/api/v1/prescriptions/", {"client": str(dupont.public_id)}).status_code == 403
    reponse = api.post(
        "/api/v1/prescriptions/", corps_ordonnance(dupont, reseau["lille"]), format="json"
    )
    assert reponse.status_code == 403


def test_saisie_chiffree_et_journalisee(affecter, client_de, reseau, dupont):
    opticien = affecter("opticien", *ORDONNANCES, portee="magasin", magasin=reseau["lille"])
    api = client_de(opticien)

    reponse = api.post(
        "/api/v1/prescriptions/", corps_ordonnance(dupont, reseau["lille"]), format="json"
    )
    assert reponse.status_code == 201, reponse.json()
    assert reponse.json()["mesures"]["od"]["sphere"] == "-2.25"

    prescription = Prescription.objects.get()
    assert "-2.25" not in prescription.mesures_chiffrees
    assert prescription.mesures["od"]["axe"] == 90
    assert prescription.saisie_par == opticien

    lues = api.get("/api/v1/prescriptions/", {"client": str(dupont.public_id)}).json()["results"]
    assert [p["prescripteur"] for p in lues] == ["Dr Martin"]
    api.get(f"/api/v1/prescriptions/{prescription.public_id}/")
    assert list(AccesPrescription.objects.order_by("id").values_list("action", "utilisateur")) == [
        ("saisie", opticien.pk),
        ("consultation", opticien.pk),
        ("consultation", opticien.pk),
    ]


def test_ordonnance_suit_le_client_dans_le_reseau(affecter, client_de, reseau, dupont):
    lille = affecter("opticien", *ORDONNANCES, portee="magasin", magasin=reseau["lille"])
    client_de(lille).post(
        "/api/v1/prescriptions/", corps_ordonnance(dupont, reseau["lille"]), format="json"
    )
    nice = affecter("opticien_nice", *ORDONNANCES, portee="magasin", magasin=reseau["nice"])
    lues = client_de(nice).get("/api/v1/prescriptions/", {"client": str(dupont.public_id)})
    assert lues.json()["count"] == 1
    # Mais il ne peut pas en saisir une au nom de Lille.
    reponse = client_de(nice).post(
        "/api/v1/prescriptions/", corps_ordonnance(dupont, reseau["lille"]), format="json"
    )
    assert reponse.status_code == 400


def test_liste_exige_un_client(affecter, client_de, reseau):
    opticien = affecter("opticien", *ORDONNANCES, portee="reseau")
    assert client_de(opticien).get("/api/v1/prescriptions/").status_code == 400


@pytest.mark.parametrize(
    "modification, champ",
    [
        ({"od": {"sphere": "-2.10"}}, "od"),
        ({"od": {"sphere": "-2.00", "cylindre": "-1.00"}}, "od"),
        ({"og": {"sphere": "45"}}, "og"),
    ],
)
def test_mesures_validees(affecter, client_de, reseau, dupont, modification, champ):
    opticien = affecter("opticien", *ORDONNANCES, portee="reseau")
    corps = corps_ordonnance(dupont, reseau["lille"])
    corps["mesures"].update(modification)
    reponse = client_de(opticien).post("/api/v1/prescriptions/", corps, format="json")
    assert reponse.status_code == 400
    assert champ in reponse.json()["mesures"]


def test_ordonnance_datee_du_futur_refusee(affecter, client_de, reseau, dupont):
    opticien = affecter("opticien", *ORDONNANCES, portee="reseau")
    corps = corps_ordonnance(dupont, reseau["lille"])
    corps["date_prescription"] = str(date.today() + timedelta(days=1))
    reponse = client_de(opticien).post("/api/v1/prescriptions/", corps, format="json")
    assert reponse.status_code == 400


def test_rotation_de_cle():
    ancienne, nouvelle = chiffrement.nouvelle_cle(), chiffrement.nouvelle_cle()
    with override_settings(PRESCRIPTIONS_CLES=[ancienne]):
        jeton = chiffrement.chiffrer({"od": 1})
    with override_settings(PRESCRIPTIONS_CLES=[nouvelle, ancienne]):
        assert chiffrement.dechiffrer(jeton) == {"od": 1}


def test_qui_voit_les_ordonnances(db):
    roles = {role.name for role in Group.objects.filter(permissions__codename="view_prescription")}
    # L'atelier monte les verres et le service commandes les commande : ils lisent l'ordonnance.
    assert roles == {
        "Administrateur Global",
        "Opticien",
        "Responsable de magasin",
        "Atelier",
        "Commande",
    }
    saisie = {r.name for r in Group.objects.filter(permissions__codename="add_prescription")}
    assert saisie == {"Administrateur Global", "Opticien", "Responsable de magasin"}


def test_numero_de_fiche_attribue_et_recherche(affecter, client_de, reseau, dupont):
    vendeur = affecter("vendeur", *CLIENTS, portee="magasin", magasin=reseau["lille"])
    api = client_de(vendeur)
    reponse = api.post(
        "/api/v1/clients/",
        {
            "nom": "Durand",
            "prenom": "Paul",
            "magasin_origine": str(reseau["lille"].public_id),
            "numero": 999,
        },
    )
    assert reponse.status_code == 201, reponse.json()
    # Le numéro suit le dernier attribué ; celui envoyé par le poste est ignoré.
    assert reponse.json()["numero"] == dupont.numero + 1

    trouves = api.get("/api/v1/clients/", {"recherche": str(dupont.numero)}).json()["results"]
    assert [c["nom"] for c in trouves] == ["Dupont"]
    trouves = api.get("/api/v1/clients/", {"recherche": "0601020304"}).json()["results"]
    assert [c["nom"] for c in trouves] == ["Dupont"]
