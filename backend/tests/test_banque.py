"""Banque et versements : de la clôture validée jusqu'au relevé bancaire."""

from decimal import Decimal

import pytest
from django.contrib.auth.models import Group

from apps.reseau.models import Magasin
from apps.securite.models import Affectation, Utilisateur
from apps.tresorerie.models import ClotureCaisse, CompteTresorerie

from .test_tresorerie import cloturer, encaisser, journee, situation  # noqa: F401

D = Decimal
OPERATIONS = "/api/v1/tresorerie/operations/"


@pytest.fixture
def equipe(tunis):
    def membre(nom, profil, **perimetre):
        utilisateur = Utilisateur.objects.create_user(nom)
        Affectation.objects.create(
            utilisateur=utilisateur,
            role=Group.objects.get(name=profil),
            **(perimetre or {"portee": "magasin", "magasin": tunis}),
        )
        return utilisateur

    return {
        "caissier": membre("caissier", "Caissier"),
        "finance": membre("finance", "Comptabilité & Finance", portee="reseau"),
        "responsable": membre("responsable", "Responsable de magasin"),
    }


@pytest.fixture
def comptes(tunis):
    societe = tunis.societe
    return {
        "biat": CompteTresorerie.objects.create(
            societe=societe, type="banque", nom="BIAT Aouina", banque="BIAT"
        ),
        "coffre": CompteTresorerie.objects.create(
            societe=societe,
            type="coffre",
            nom="Coffre T01",
            magasin=tunis,
            solde_initial=D("500.000"),
        ),
    }


@pytest.fixture
def validee(tunis, equipe, journee, client_de):  # noqa: F811
    """La clôture de la journée, validée : 200 en espèces, 180 en chèque, 320,500 en carte."""
    numero = cloturer(client_de(equipe["caissier"]), tunis).json()["id"]
    finance = client_de(equipe["finance"])
    finance.post(f"/api/v1/tresorerie/clotures/{numero}/valider/", {}, format="json")
    return numero


def deposer(client, type_, clotures, destination, **extra):
    corps = {
        "type": type_,
        "clotures": clotures,
        "destination": str(destination.public_id),
    } | extra
    return client.post(OPERATIONS + "deposer/", corps, format="json")


def comptes_de(client):
    return {c["nom"]: c for c in client.get("/api/v1/tresorerie/comptes/").json()}


def test_de_la_cloture_a_la_banque(validee, equipe, comptes, client_de):
    responsable = client_de(equipe["responsable"])
    a_remettre = responsable.get(OPERATIONS + "a-remettre/").json()
    assert [(c["id"], c["especes"], c["cheques"], c["cartes"]) for c in a_remettre] == [
        (validee, "200.000", "180.000", "320.500")
    ]

    # Sans bordereau, pas de versement en banque.
    assert deposer(responsable, "depot_especes", [validee], comptes["biat"]).status_code == 400
    especes = deposer(responsable, "depot_especes", [validee], comptes["biat"], reference="B-77")
    assert especes.status_code == 201, especes.json()
    assert (especes.json()["statut"], especes.json()["montant"]) == ("effectuee", "200.000")
    assert especes.json()["numero"].endswith("-OP2026-000001")
    deux_fois = deposer(responsable, "depot_especes", [validee], comptes["biat"], reference="B")
    assert deux_fois.status_code == 400

    # Les chèques : d'abord prévus, puis remis.
    cheques = deposer(responsable, "depot_cheques", [validee], comptes["biat"], prevue=True)
    assert cheques.json()["statut"] == "prevue"
    url = f"{OPERATIONS}{cheques.json()['id']}/"
    remis = responsable.post(url + "effectuer/", {"reference": "RC-12"}, format="json")
    assert remis.json()["statut"] == "effectuee"

    cartes = deposer(
        responsable, "encaissement_cartes", [validee], comptes["biat"], reference="TPE"
    )
    assert cartes.status_code == 201
    assert responsable.get(OPERATIONS + "a-remettre/").json() == []

    # La finance retrouve les cartes sur le relevé, commission déduite.
    finance = client_de(equipe["finance"])
    url = f"{OPERATIONS}{cartes.json()['id']}/rapprocher/"
    assert responsable.post(url, {"date_valeur": "2026-10-05"}, format="json").status_code == 403
    assert finance.post(url, {"date_valeur": "2026-10-05"}, format="json").status_code == 400
    rapprochee = finance.post(
        url, {"date_valeur": "2026-10-05", "montant_credite": "315.000"}, format="json"
    )
    assert rapprochee.status_code == 200, rapprochee.json()
    assert (rapprochee.json()["statut"], rapprochee.json()["commission"]) == (
        "rapprochee",
        "5.500",
    )

    biat = comptes_de(finance)["BIAT Aouina"]
    assert (biat["solde_comptable"], biat["solde_banque"]) == ("695.000", "315.000")
    # Le responsable voit le compte pour y déposer, pas son solde.
    assert comptes_de(responsable)["BIAT Aouina"]["solde_comptable"] is None

    cloture = ClotureCaisse.tous.get(public_id=validee)
    assert cloture.depot_especes.reference == "B-77"


def test_cloture_non_validee(tunis, equipe, journee, comptes, client_de):  # noqa: F811
    numero = cloturer(client_de(equipe["caissier"]), tunis).json()["id"]
    reponse = deposer(client_de(equipe["finance"]), "depot_especes", [numero], comptes["coffre"])
    assert reponse.status_code == 400
    assert "pas encore validée" in reponse.json()["detail"]


def test_les_cheques_vont_en_banque(validee, equipe, comptes, client_de):
    reponse = deposer(
        client_de(equipe["responsable"]), "depot_cheques", [validee], comptes["coffre"]
    )
    assert reponse.status_code == 400


def test_annuler_une_prevision(validee, equipe, comptes, client_de):
    client = client_de(equipe["responsable"])
    prevue = deposer(client, "depot_especes", [validee], comptes["biat"], prevue=True).json()
    assert client.get(OPERATIONS + "a-remettre/").json()[0]["especes"] is None
    assert client.post(f"{OPERATIONS}{prevue['id']}/annuler/").status_code == 204
    assert client.get(OPERATIONS + "a-remettre/").json()[0]["especes"] == "200.000"
    # Le numéro de l'opération suivante ne réutilise pas un numéro existant.
    nouvelle = deposer(client, "depot_especes", [validee], comptes["coffre"]).json()
    assert nouvelle["statut"] == "effectuee" and nouvelle["numero"].endswith("000001")


def test_alimentation_du_fond(tunis, equipe, comptes, client_de):
    finance = client_de(equipe["finance"])
    corps = {
        "type": "alimentation_fond",
        "societe": str(tunis.societe.public_id),
        "source": str(comptes["coffre"].public_id),
        "magasin": str(tunis.public_id),
        "montant": "100.000",
    }
    reponse = finance.post(OPERATIONS, corps, format="json")
    assert reponse.status_code == 201, reponse.json()
    s = situation(client_de(equipe["caissier"]), tunis).json()
    assert (s["alimentations"], s["especes_attendues"]) == ("100.000", "100.000")
    assert comptes_de(finance)["Coffre T01"]["solde_comptable"] == "400.000"

    trop = finance.post(OPERATIONS, corps | {"montant": "450.000"}, format="json")
    assert trop.status_code == 400 and "ne contient que" in trop.json()["detail"]

    # La clôture fige l'alimentation ; la suivante repart de zéro.
    cloture = cloturer(
        client_de(equipe["caissier"]),
        tunis,
        especes_comptees="100.000",
        cheques_comptes="0",
        nombre_cheques_comptes=0,
        cartes_comptees="0",
        fond_conserve="100.000",
    ).json()
    assert (cloture["alimentations"], cloture["ecart_especes"]) == ("100.000", "0.000")
    assert situation(client_de(equipe["caissier"]), tunis).json()["alimentations"] == "0.000"


def test_transfert_et_frais_reserves_a_la_finance(tunis, equipe, comptes, client_de):
    corps = {
        "type": "transfert",
        "societe": str(tunis.societe.public_id),
        "source": str(comptes["coffre"].public_id),
        "destination": str(comptes["biat"].public_id),
        "montant": "300.000",
        "reference": "VRS-1",
    }
    assert (
        client_de(equipe["responsable"]).post(OPERATIONS, corps, format="json").status_code == 403
    )
    finance = client_de(equipe["finance"])
    assert finance.post(OPERATIONS, corps, format="json").status_code == 201
    frais = {
        "type": "operation_bancaire",
        "societe": str(tunis.societe.public_id),
        "source": str(comptes["biat"].public_id),
        "montant": "12.000",
        "libelle": "Frais de tenue de compte",
    }
    assert finance.post(OPERATIONS, frais, format="json").status_code == 201
    soldes = comptes_de(finance)
    assert soldes["Coffre T01"]["solde_comptable"] == "200.000"
    assert soldes["BIAT Aouina"]["solde_comptable"] == "288.000"


def test_creer_un_compte(tunis, equipe, client_de):
    finance = client_de(equipe["finance"])
    corps = {"societe": str(tunis.societe.public_id), "type": "coffre", "nom": "Coffre"}
    assert finance.post("/api/v1/tresorerie/comptes/", corps, format="json").status_code == 400
    corps["magasin"] = str(tunis.public_id)
    reponse = finance.post("/api/v1/tresorerie/comptes/", corps, format="json")
    assert reponse.status_code == 201, reponse.json()
    assert reponse.json()["solde_comptable"] == "0.000"
    responsable = client_de(equipe["responsable"])
    assert responsable.post("/api/v1/tresorerie/comptes/", corps, format="json").status_code == 403


def test_caissier_et_autre_societe(reseau, tunis, equipe, validee, comptes, client_de):
    assert client_de(equipe["caissier"]).get(OPERATIONS).status_code == 403
    lille = Magasin.tous.get(code="M01")
    ailleurs = CompteTresorerie.objects.create(societe=lille.societe, type="banque", nom="BNP")
    reponse = deposer(
        client_de(equipe["finance"]), "depot_especes", [validee], ailleurs, reference="X"
    )
    assert reponse.status_code == 400 and "autre société" in reponse.json()["detail"]
    assert "BNP" not in comptes_de(client_de(equipe["responsable"]))
