"""Facturation groupée des visites et ventes comptoir ; clôture du mois."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from apps.crm.models import Client
from apps.ventes.models import ClotureMois, FactureGroupee, Vente

from .test_credit_impayes import vendre

VENDRE = ("ventes.view_vente", "ventes.add_vente", "crm.view_client", "ventes.add_facture")
GROUPEES = "/api/v1/factures-groupees/"
CLOTURES = "/api/v1/clotures-mois/"
PAYE = [{"mode": "especes", "montant": "289.500"}]


@pytest.fixture
def responsable(affecter, tunis):
    return affecter(
        "responsable",
        *VENDRE,
        "ventes.vendre_a_credit",
        "ventes.view_facturegroupee",
        "ventes.add_facturegroupee",
        "ventes.view_cloturemois",
        "ventes.add_cloturemois",
        portee="magasin",
        magasin=tunis,
    )


@pytest.fixture
def amel(tunis):
    return Client.objects.create(magasin_origine=tunis, nom="Ben Salah", prenom="Amel")


def _vente(api, tunis, monture, client, paiements=PAYE, **autres):
    reponse = vendre(api, tunis, monture, client, paiements, **autres)
    assert reponse.status_code == 201, reponse.json()
    return Vente.tous.get(numero=reponse.json()["numero"])


def test_facture_groupee_des_ventes_comptoir(client_de, responsable, tunis, monture, amel):
    api = client_de(responsable)
    premiere = _vente(api, tunis, monture, amel)
    seconde = _vente(api, tunis, monture, amel)
    a_credit = _vente(
        api, tunis, monture, amel, [{"mode": "especes", "montant": "100"}], a_credit=True
    )

    params = {"magasin": str(tunis.public_id), "client": str(amel.public_id), "comptoir": "true"}
    a_facturer = api.get(GROUPEES + "a-facturer/", params).json()
    # La vente à crédit n'est pas soldée : elle attend.
    assert [v["numero"] for v in a_facturer] == [premiere.numero, seconde.numero]
    assert api.get(GROUPEES + "a-facturer/", {**params, "comptoir": "false"}).json() == []

    saisie = {
        "magasin": str(tunis.public_id),
        "client": str(amel.public_id),
        "ventes": [str(premiere.public_id), str(seconde.public_id)],
        "mode_paiement_timbre": "especes",
    }
    refus = api.post(
        GROUPEES, {**saisie, "ventes": [str(a_credit.public_id)]}, format="json"
    ).json()
    assert "reste 189.500" in refus["detail"]
    sans_timbre = api.post(GROUPEES, {**saisie, "mode_paiement_timbre": ""}, format="json")
    assert "timbre" in sans_timbre.json()["detail"]

    reponse = api.post(GROUPEES, saisie, format="json")
    assert reponse.status_code == 201, reponse.json()
    facture = reponse.json()
    assert facture["numero"].startswith("T01-F")
    assert (facture["type"], facture["client_nom"], facture["nombre_ventes"]) == (
        "client",
        "BEN SALAH Amel",
        2,
    )
    assert (facture["total_ttc"], facture["timbre_fiscal"], facture["net_a_payer"]) == (
        "579.000",
        "1.000",
        "580.000",
    )
    assert [(d["taux"], d["total_ttc"]) for d in facture["detail_tva"]] == [("19.00", "579.000")]
    assert [ligne["vente"] for ligne in facture["lignes"]] == [premiere.numero, seconde.numero]

    # Facturées : elles ne se facturent plus, ni ensemble ni une à une.
    assert api.get(GROUPEES + "a-facturer/", params).json() == []
    assert api.post(GROUPEES, saisie, format="json").status_code == 400
    une = api.post(
        "/api/v1/factures/",
        {"vente": str(premiere.public_id), "mode_paiement_timbre": "especes"},
        format="json",
    )
    assert une.status_code == 400 and "déjà facturée" in une.json()["detail"]
    detail = api.get(f"{GROUPEES}{facture['id']}/").json()
    assert [v["numero"] for v in detail["ventes"]] == [premiere.numero, seconde.numero]


def test_vente_comptoir_sans_fiche_au_nom_d_une_societe(client_de, responsable, tunis, monture):
    api = client_de(responsable)
    vente = _vente(api, tunis, monture, None)
    saisie = {
        "magasin": str(tunis.public_id),
        "ventes": [str(vente.public_id)],
        "mode_paiement_timbre": "especes",
    }
    assert "au nom de qui" in api.post(GROUPEES, saisie, format="json").json()["detail"]
    reponse = api.post(
        GROUPEES,
        {**saisie, "client_nom": "Société Lumière", "client_matricule_fiscal": "1234567A"},
        format="json",
    )
    assert reponse.status_code == 201, reponse.json()
    assert reponse.json()["client_matricule_fiscal"] == "1234567A"


def _mois_dernier():
    premier = date.today().replace(day=1)
    precedent = premier - timedelta(days=1)
    return precedent.year, precedent.month


def test_cloture_du_mois(affecter, client_de, responsable, tunis, monture, amel):
    api = client_de(responsable)
    annee, mois = _mois_dernier()
    comptoir = _vente(api, tunis, monture, None)
    visite = _vente(api, tunis, monture, amel)
    deja = _vente(api, tunis, monture, amel)
    assert (
        api.post(
            "/api/v1/factures/",
            {"vente": str(deja.public_id), "mode_paiement_timbre": "especes"},
            format="json",
        ).status_code
        == 201
    )
    le_15 = datetime(annee, mois, 15, 10, tzinfo=ZoneInfo("Africa/Tunis"))
    Vente.tous.filter(pk__in=[comptoir.pk, visite.pk, deja.pk]).update(livree_le=le_15)

    mois_params = {"magasin": str(tunis.public_id), "annee": annee, "mois": mois}
    preparation = api.get(CLOTURES + "preparation/", mois_params).json()
    assert preparation["cloture"] is None
    assert [v["numero"] for v in preparation["ventes"]] == [comptoir.numero, visite.numero]
    assert (preparation["total_ht"], preparation["total_ttc"]) == ("486.554", "579.000")

    # Le mois en cours ne se clôture pas.
    aujourdhui = date.today()
    en_cours = {**mois_params, "annee": aujourdhui.year, "mois": aujourdhui.month}
    assert "pas terminé" in api.post(CLOTURES, en_cours, format="json").json()["detail"]

    vendeur = affecter("vendeur", *VENDRE, portee="magasin", magasin=tunis)
    assert client_de(vendeur).post(CLOTURES, mois_params, format="json").status_code == 403

    reponse = api.post(CLOTURES, mois_params, format="json")
    assert reponse.status_code == 201, reponse.json()
    assert reponse.json()["total_ttc"] == "579.000"
    recap = FactureGroupee.tous.get(numero=reponse.json()["facture_numero"])
    assert (recap.type, recap.client_nom, recap.timbre_fiscal) == (
        "mensuelle",
        "Clients divers",
        Decimal("0"),
    )
    assert set(recap.ventes.all()) == {comptoir, visite}
    assert api.get(f"{GROUPEES}{recap.public_id}/").json()["lignes"] == []

    # Le mois est figé.
    assert "déjà clôturé" in api.post(CLOTURES, mois_params, format="json").json()["detail"]
    assert ClotureMois.tous.count() == 1
    assert api.get(CLOTURES + "preparation/", mois_params).json()["cloture"]["mois"] == mois
    assert api.get(GROUPEES + "a-facturer/", {"magasin": str(tunis.public_id)}).json() == []
    refus = api.post(
        "/api/v1/factures/",
        {"vente": str(visite.public_id), "mode_paiement_timbre": "especes"},
        format="json",
    )
    assert refus.status_code == 400
