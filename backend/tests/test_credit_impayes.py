"""Crédit client et impayés : vente à crédit, chèque impayé, changement de chèque, liste noire."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.crm.models import Client
from apps.ventes.models import Paiement, Vente

from .conftest import recevoir_verres
from .test_commandes import commander, verre  # noqa: F401  (fixture)

VENDRE = ("ventes.view_vente", "ventes.add_vente", "crm.view_client")
URL = "/api/v1/credit-clients/"


@pytest.fixture
def responsable(affecter, tunis):
    return affecter(
        "responsable",
        *VENDRE,
        "ventes.vendre_a_credit",
        "ventes.gerer_impayes",
        portee="magasin",
        magasin=tunis,
    )


@pytest.fixture
def amel(tunis):
    return Client.objects.create(magasin_origine=tunis, nom="Ben Salah", prenom="Amel")


def vendre(api, tunis, monture, client, paiements, **autres):
    return api.post(
        "/api/v1/ventes/",
        {
            "magasin": str(tunis.public_id),
            "client": str(client.public_id) if client else None,
            "lignes": [{"article": str(monture.public_id), "quantite": 1}],
            "paiements": paiements,
            **autres,
        },
        format="json",
    )


def test_vente_comptoir_a_credit(affecter, client_de, responsable, tunis, monture, amel):
    api = client_de(responsable)
    promis = (date.today() + timedelta(days=30)).isoformat()
    reponse = vendre(
        api,
        tunis,
        monture,
        amel,
        [{"mode": "especes", "montant": "100.000"}],
        a_credit=True,
        credit_echeance=promis,
    )
    assert reponse.status_code == 201, reponse.json()
    assert (reponse.json()["statut"], reponse.json()["reste_a_payer"]) == ("livree", "189.500")

    dues = api.get(URL + "ventes-dues/").json()
    assert [(d["numero"], d["reste_a_payer"], d["a_credit"]) for d in dues] == [
        (reponse.json()["numero"], "189.500", True)
    ]
    assert api.get(f"/api/v1/clients/{amel.public_id}/").json()["solde"] == "189.500"

    # Sans client, ou sans le droit, pas de crédit.
    assert vendre(api, tunis, monture, None, [], a_credit=True).status_code == 400
    vendeur = affecter("vendeur", *VENDRE, portee="magasin", magasin=tunis)
    assert vendre(client_de(vendeur), tunis, monture, amel, [], a_credit=True).status_code == 403

    # Le client règle son crédit plus tard.
    vente = Vente.tous.get(numero=reponse.json()["numero"])
    regle = api.post(
        f"/api/v1/ventes/{vente.public_id}/reglement/",
        {"paiements": [{"mode": "especes", "montant": "189.500"}]},
        format="json",
    )
    assert regle.status_code == 200, regle.json()
    assert api.get(URL + "ventes-dues/").json() == []


def test_cheque_impaye_puis_liste_noire(client_de, responsable, tunis, monture, amel):
    api = client_de(responsable)
    sans_numero = vendre(api, tunis, monture, amel, [{"mode": "cheque", "montant": "289.500"}])
    assert sans_numero.status_code == 400
    vente = vendre(
        api,
        tunis,
        monture,
        amel,
        [{"mode": "cheque", "montant": "289.500", "reference": "0042", "banque": "BIAT"}],
    ).json()
    cheque = api.get(URL + "paiements/").json()[0]
    assert (cheque["reference"], cheque["statut"]) == ("0042", "encaisse")

    assert (
        api.post(f"{URL}paiements/{cheque['id']}/impaye/", {"le": "2026-10-05"}).status_code == 400
    )
    impaye = api.post(
        f"{URL}paiements/{cheque['id']}/impaye/",
        {"le": "2026-10-05", "motif": "Sans provision"},
    )
    assert impaye.status_code == 200, impaye.json()
    assert (impaye.json()["statut"], impaye.json()["vente_reste"]) == ("impaye", "289.500")
    amel.refresh_from_db()
    assert amel.liste_noire and "0042" in amel.motif_liste_noire
    assert [d["impayes"] for d in api.get(URL + "ventes-dues/").json()] == [1]
    assert len(api.get(URL + "paiements/", {"vue": "impayes"}).json()) == 1

    # En liste noire : plus de chèque, ni de crédit.
    refus = vendre(
        api, tunis, monture, amel, [{"mode": "cheque", "montant": "289.500", "reference": "43"}]
    )
    assert refus.status_code == 400 and "liste noire" in refus.json()["detail"]
    assert vendre(api, tunis, monture, amel, [], a_credit=True).status_code == 400

    # Régularisé en espèces : la visite est soldée ; on retire le client de la liste noire.
    api.post(
        f"/api/v1/ventes/{vente['id']}/reglement/",
        {"paiements": [{"mode": "especes", "montant": "289.500"}]},
        format="json",
    )
    assert api.get(URL + "ventes-dues/").json() == []
    assert [c["nom"] for c in api.get(URL + "liste-noire/").json()] == ["BEN SALAH Amel"]
    assert api.delete(f"{URL}liste-noire/{amel.public_id}/").status_code == 204
    amel.refresh_from_db()
    assert not amel.liste_noire


def test_changement_de_cheque_et_portefeuille(client_de, responsable, tunis, monture, verre, amel):  # noqa: F811
    api = client_de(responsable)
    vente = commander(tunis, monture, verre, responsable, client=amel, acompte="0")
    plus_tard = date.today() + timedelta(days=20)
    api.post(
        f"/api/v1/ventes/{vente.public_id}/reglement/",
        {
            "paiements": [
                {
                    "mode": "traite",
                    "montant": "300.000",
                    "reference": "TR-7",
                    "echeance": plus_tard.isoformat(),
                }
            ]
        },
        format="json",
    )
    portefeuille = api.get(URL + "paiements/", {"vue": "portefeuille"}).json()
    assert [(p["reference"], p["echeance"]) for p in portefeuille] == [
        ("TR-7", plus_tard.isoformat())
    ]

    change = api.post(
        f"{URL}paiements/{portefeuille[0]['id']}/changer/", {"mode": "especes"}, format="json"
    )
    assert change.status_code == 200, change.json()
    assert (change.json()["mode"], change.json()["montant"]) == ("especes", "300.000")
    assert Paiement.objects.get(reference="TR-7").statut == "remplace"
    vente.refresh_from_db()
    assert vente.reste_a_payer == Decimal("349.500")
    assert api.get(URL + "paiements/", {"vue": "portefeuille"}).json() == []

    # Livrée à crédit : le reste attend.
    recevoir_verres(vente, responsable)
    livree = api.post(
        f"/api/v1/ventes/{vente.public_id}/livrer/", {"a_credit": True}, format="json"
    )
    assert livree.status_code == 200, livree.json()
    assert livree.json()["statut"] == "livree"


def test_impayes_reserves_au_droit(affecter, client_de, responsable, tunis, monture, amel):
    vendre(
        client_de(responsable),
        tunis,
        monture,
        amel,
        [{"mode": "cheque", "montant": "289.500", "reference": "1"}],
    )
    caissier = client_de(affecter("caissier", *VENDRE, portee="magasin", magasin=tunis))
    cheque = caissier.get(URL + "paiements/").json()[0]
    reponse = caissier.post(
        f"{URL}paiements/{cheque['id']}/impaye/", {"le": "2026-10-05", "motif": "x"}
    )
    assert reponse.status_code == 403
