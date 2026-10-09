"""Service après-vente : dossier ouvert à la réception, suivi par étapes jusqu'à la remise."""

import datetime

import pytest

from apps.achats.models import Fournisseur
from apps.crm.models import Client
from apps.pilotage.alertes import alertes
from apps.reseau.models import Magasin
from apps.ventes.models import DossierSav

from .test_commandes import commander, verre  # noqa: F401  (fixture)

DROITS = ("ventes.view_dossiersav", "ventes.add_dossiersav", "ventes.change_dossiersav")


@pytest.fixture
def atelier(affecter, tunis):
    return affecter("atelier", *DROITS, portee="magasin", magasin=tunis)


@pytest.fixture
def amel(tunis):
    return Client.objects.create(magasin_origine=tunis, nom="Ben Salah", prenom="Amel")


def ouvrir(api, magasin, client, **extra):
    return api.post(
        "/api/v1/sav/",
        {
            "magasin": magasin.public_id,
            "client": client.public_id,
            "designation": "Monture Ray-Ban, branche cassée",
            "motif": "casse",
            **extra,
        },
        format="json",
    )


def etape(api, dossier, **donnees):
    return api.post(f"/api/v1/sav/{dossier['id']}/etape/", donnees, format="json")


def test_du_depot_a_la_remise(atelier, client_de, tunis, amel, monture, verre):  # noqa: F811
    api = client_de(atelier)
    vente = commander(tunis, monture, verre, atelier, client=amel)
    reponse = ouvrir(api, tunis, amel, vente=str(vente.public_id), sous_garantie=True)
    assert reponse.status_code == 201, reponse.json()
    dossier = reponse.json()
    assert dossier["numero"].startswith("T01-S")
    assert (dossier["etape"], dossier["vente_numero"]) == ("recu", vente.numero)

    # Envoi au fournisseur : il faut savoir lequel.
    assert etape(api, dossier, etape="fournisseur").status_code == 400
    labo = Fournisseur.objects.create(nom="Labo Verres", pays=tunis.pays)
    assert (
        etape(api, dossier, etape="fournisseur", fournisseur=str(labo.public_id)).status_code == 200
    )
    assert etape(api, dossier, etape="pret", commentaire="Branche remplacée").status_code == 200
    rendu = etape(api, dossier, etape="rendu", solution="Branche changée sous garantie").json()
    assert (rendu["est_ouvert"], rendu["fournisseur_nom"]) == (False, "Labo Verres")
    assert [e["etape"] for e in rendu["evenements"]] == [
        "recu",
        "fournisseur",
        "pret",
        "rendu",
    ]

    # Clôturé : plus rien ne bouge.
    assert etape(api, dossier, etape="atelier").status_code == 400
    assert api.get("/api/v1/sav/", {"etape": "ouverts"}).json()["count"] == 0


def test_annulation_avec_motif(atelier, client_de, tunis, amel):
    api = client_de(atelier)
    dossier = ouvrir(api, tunis, amel).json()
    assert etape(api, dossier, etape="annule").status_code == 400
    assert etape(api, dossier, etape="annule", commentaire="Client a renoncé").status_code == 200


def test_retard_et_alertes(atelier, client_de, tunis, amel):
    api = client_de(atelier)
    hier = datetime.date.today() - datetime.timedelta(days=1)
    en_retard = ouvrir(api, tunis, amel, retour_prevu_le=hier.isoformat()).json()
    assert en_retard["en_retard"] is True
    pret = ouvrir(api, tunis, amel).json()
    etape(api, pret, etape="pret")

    assert [d["id"] for d in api.get("/api/v1/sav/", {"retard": "1"}).json()["results"]] == [
        en_retard["id"]
    ]
    codes = {a["code"]: a["nombre"] for a in alertes(atelier)}
    assert (codes["sav_en_retard"], codes["sav_prets"]) == (1, 1)


def test_droits_et_perimetre(affecter, client_de, tunis, amel):
    lecteur = affecter("comptable", "ventes.view_dossiersav", portee="magasin", magasin=tunis)
    assert ouvrir(client_de(lecteur), tunis, amel).status_code == 403

    lac = Magasin.tous.create(code="T02", nom="Lac", societe=tunis.societe, pays=tunis.pays)
    autre = affecter("atelier-lac", *DROITS, portee="magasin", magasin=lac)
    ouvrir(client_de(affecter("atelier", *DROITS, portee="magasin", magasin=tunis)), tunis, amel)
    assert DossierSav.tous.count() == 1
    api = client_de(autre)
    assert api.get("/api/v1/sav/").json()["count"] == 0
    assert ouvrir(api, tunis, amel).status_code == 400
