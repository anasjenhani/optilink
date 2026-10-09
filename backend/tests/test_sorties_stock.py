"""Bon de sortie et sortie casse, demandes de transfert (alimentation), réassort, stock à une
date."""

from datetime import date, timedelta

import pytest
from django.utils import timezone

from apps.reseau.models import Magasin
from apps.stock.models import DemandeTransfert, MouvementStock, TransfertStock, stock_disponible

SORTIE = "/api/v1/bons-sortie/"
DEMANDES = "/api/v1/demandes-transfert/"
TRAITER = (
    "stock.view_demandetransfert",
    "stock.add_demandetransfert",
    "stock.change_demandetransfert",
)


@pytest.fixture
def depot(tunis, monture):
    depot = Magasin.tous.create(
        code="DEP", nom="Dépôt central", societe=tunis.societe, pays=tunis.pays, type="depot"
    )
    MouvementStock.tous.create(magasin=depot, article=monture, quantite=10, type="reception")
    return depot


@pytest.fixture
def stock(affecter, tunis):
    return affecter(
        "stock",
        "stock.view_bonsortie",
        "stock.add_bonsortie",
        "stock.view_article",
        *TRAITER,
        portee="magasin",
        magasin=tunis,
    )


def test_sortie_casse(affecter, client_de, stock, tunis, monture):
    api = client_de(stock)
    saisie = {
        "magasin": str(tunis.public_id),
        "type": "casse",
        "motif": "Tombée de la vitrine",
        "lignes": [{"article": str(monture.public_id), "quantite": 1}],
    }
    reponse = api.post(SORTIE, saisie, format="json")
    assert reponse.status_code == 201, reponse.json()
    assert reponse.json()["numero"].startswith("T01-BS")
    assert stock_disponible(tunis, monture) == 2
    assert MouvementStock.tous.filter(type="casse", quantite=-1).count() == 1

    trop = {**saisie, "lignes": [{"article": str(monture.public_id), "quantite": 5}]}
    assert "2 en stock" in api.post(SORTIE, trop, format="json").json()["detail"]
    assert api.post(SORTIE, {**saisie, "motif": " "}, format="json").status_code == 400
    assert [b["type_libelle"] for b in api.get(SORTIE).json()["results"]] == ["Sortie casse"]

    vendeur = affecter("vendeur", "stock.view_bonsortie", portee="magasin", magasin=tunis)
    assert client_de(vendeur).post(SORTIE, saisie, format="json").status_code == 403


def test_demande_d_alimentation_servie_par_le_depot(
    affecter, client_de, stock, tunis, depot, monture
):
    api = client_de(stock)
    demande = api.post(
        DEMANDES,
        {
            "magasin": str(tunis.public_id),
            "aupres_de": str(depot.public_id),
            "lignes": [{"article": str(monture.public_id), "quantite": 4}],
        },
        format="json",
    )
    assert demande.status_code == 201, demande.json()
    demande = demande.json()
    assert (demande["numero"][:6], demande["statut"]) == ("T01-DT", "en_attente")

    # Le magasin demandeur ne sert pas sa propre demande.
    assert api.post(f"{DEMANDES}{demande['id']}/servir/", {}, format="json").status_code == 403

    magasinier = client_de(affecter("depot", *TRAITER, portee="magasin", magasin=depot))
    recues = magasinier.get(DEMANDES, {"sens": "recues"}).json()["results"]
    assert [d["numero"] for d in recues] == [demande["numero"]]
    servie = magasinier.post(
        f"{DEMANDES}{demande['id']}/servir/",
        {"lignes": [{"article": str(monture.public_id), "quantite": 3}]},
        format="json",
    )
    assert servie.status_code == 200, servie.json()
    assert servie.json()["statut"] == "servie"
    assert servie.json()["lignes"][0]["quantite_servie"] == 3
    transfert = TransfertStock.tous.get(numero=servie.json()["transfert"])
    assert (transfert.magasin, transfert.destination) == (depot, tunis)
    assert stock_disponible(depot, monture) == 7
    deja = magasinier.post(f"{DEMANDES}{demande['id']}/refuser/", {"motif": "x"})
    assert "déjà servie" in deja.json()["detail"]
    assert DemandeTransfert.tous.get().statut == "servie"


def test_reassort_et_stock_a_la_date(client_de, stock, tunis, depot, monture):
    api = client_de(stock)
    vente = MouvementStock.tous.create(magasin=tunis, article=monture, quantite=-2, type="vente")
    reassort = api.get(DEMANDES + "reassort/", {"magasin": str(tunis.public_id)}).json()
    assert [(r["vendu"], r["stock"], r["stock_depot"], r["propose"]) for r in reassort] == [
        (2, 1, 10, 2)
    ]

    # La vente date d'il y a dix jours : avant, le stock était de 3.
    MouvementStock.tous.filter(pk=vente.pk).update(horodatage=timezone.now() - timedelta(days=10))
    MouvementStock.tous.filter(magasin=tunis, type="reception").update(
        horodatage=timezone.now() - timedelta(days=20)
    )
    params = {"magasin": str(tunis.public_id)}
    il_y_a = (date.today() - timedelta(days=15)).isoformat()
    avant = api.get("/api/v1/stock-a-date/", {**params, "date": il_y_a}).json()
    assert [(ligne["libelle"], ligne["quantite"]) for ligne in avant["lignes"]] == [("Monture", 3)]
    assert api.get("/api/v1/stock-a-date/", params).json()["quantite"] == 1
    trente = (date.today() - timedelta(days=30)).isoformat()
    assert api.get("/api/v1/stock-a-date/", {**params, "date": trente}).json()["lignes"] == []
