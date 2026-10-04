"""Prise en charge (PEC) d'une commande par la CNAM, une assurance ou une mutuelle."""

from decimal import Decimal

import pytest

from apps.crm.models import Client, Organisme
from apps.ventes.services import livrer_commande

from .conftest import recevoir_verres
from .test_commandes import commander, especes, verre  # noqa: F401  (fixture)

DROITS = (
    "ventes.view_vente",
    "ventes.add_vente",
    "crm.view_client",
    "ventes.view_priseencharge",
    "ventes.add_priseencharge",
    "ventes.change_priseencharge",
    "crm.view_organisme",
)


@pytest.fixture
def opticien(affecter, tunis):
    return affecter("opticien", *DROITS, portee="magasin", magasin=tunis)


@pytest.fixture
def cnam(db):
    # Créée d'office pour la Tunisie par la migration.
    return Organisme.objects.get(pays__code="TN", nom="CNAM")


def saisir(api, vente, organisme, montant, **extra):
    return api.post(
        "/api/v1/prises-en-charge/",
        {"vente": vente.public_id, "organisme": organisme.public_id, "montant": montant, **extra},
    )


def test_la_pec_reduit_le_reste_du_client(opticien, client_de, tunis, monture, verre, cnam):  # noqa: F811
    api = client_de(opticien)
    vente = commander(tunis, monture, verre, opticien)  # 649,500 dont 200 d'acompte
    assert api.get("/api/v1/organismes/").json()[0]["nom"] == "CNAM"

    reponse = saisir(api, vente, cnam, "150.000", numero_dossier="BS-2026-118")
    assert reponse.status_code == 201, reponse.json()
    assert reponse.json()["statut"] == "demandee"
    vente.refresh_from_db()
    assert vente.reste_a_payer == Decimal("299.500")
    detail = api.get(f"/api/v1/ventes/{vente.public_id}/").json()
    assert (detail["pris_en_charge"], detail["reste_a_payer"]) == ("150.000", "299.500")

    # Pas plus que ce qui reste dû.
    assert saisir(api, vente, cnam, "300.000").status_code == 400

    # Le client solde sa part : la commande se livre.
    recevoir_verres(vente, opticien)
    livrer_commande(vente=vente, utilisateur=opticien, paiements=especes("299.500"))
    vente.refresh_from_db()
    assert vente.reste_a_payer == 0


def test_refus_de_l_organisme_rend_la_part_au_client(
    opticien,
    client_de,
    tunis,
    monture,
    verre,  # noqa: F811
    cnam,
):
    api = client_de(opticien)
    vente = commander(tunis, monture, verre, opticien)
    pec = saisir(api, vente, cnam, "150.000").json()
    url = f"/api/v1/prises-en-charge/{pec['id']}/"

    assert api.patch(url, {"statut": "accordee"}).json()["statut_libelle"] == "Accordée"
    assert api.patch(url, {"statut": "refusee"}).status_code == 200
    vente.refresh_from_db()
    assert vente.reste_a_payer == Decimal("449.500")
    assert [p["statut"] for p in api.get("/api/v1/prises-en-charge/").json()["results"]] == [
        "refusee"
    ]

    # Le client a tout payé : revenir sur le refus compterait cette part deux fois.
    recevoir_verres(vente, opticien)
    livrer_commande(vente=vente, utilisateur=opticien, paiements=especes("449.500"))
    assert api.patch(url, {"statut": "accordee"}).status_code == 400


def test_journee_et_fiche_client_portent_la_pec(opticien, client_de, tunis, monture, verre, cnam):  # noqa: F811
    api = client_de(opticien)
    client = Client.objects.create(
        magasin_origine=tunis,
        nom="Ben Salah",
        prenom="Amel",
        organisme=cnam,
        numero_affilie="12345678",
    )
    vente = commander(tunis, monture, verre, opticien, client=client)
    saisir(api, vente, cnam, "150.000")

    fiche = api.get(f"/api/v1/clients/{client.public_id}/").json()
    assert (fiche["organisme_nom"], fiche["numero_affilie"]) == ("CNAM", "12345678")

    journee = api.get("/api/v1/ventes/journee/", {"magasin": tunis.public_id}).json()
    ligne = journee["ventes"][0]
    assert (ligne["pec_client"], ligne["pec_visite"], ligne["reste"]) == (
        "CNAM",
        "150.000",
        "299.500",
    )
    assert (journee["pris_en_charge"], journee["reste_sur_ventes"]) == ("150.000", "299.500")


def test_pec_seulement_sur_commande_en_cours_et_avec_le_droit(
    affecter,
    client_de,
    tunis,
    monture,
    verre,  # noqa: F811
    cnam,
):
    sans_droit = affecter("vendeur", "ventes.view_vente", portee="magasin", magasin=tunis)
    vente = commander(tunis, monture, verre, sans_droit)
    assert saisir(client_de(sans_droit), vente, cnam, "100.000").status_code == 403

    opticien = affecter("opticien", *DROITS, portee="magasin", magasin=tunis)
    recevoir_verres(vente, opticien)
    livrer_commande(vente=vente, utilisateur=opticien, paiements=especes("449.500"))
    refus = saisir(client_de(opticien), vente, cnam, "100.000")
    assert refus.status_code == 400
    assert "commande en cours" in refus.json()["detail"]
