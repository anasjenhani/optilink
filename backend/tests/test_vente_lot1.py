"""Vente, lot 1 : liste et fiche des visites, reçus, reste par vendeur, casse de verre."""

from decimal import Decimal

import pytest

from apps.crm.models import Client
from apps.ventes.services import enregistrer_vente, livrer_commande

from .conftest import recevoir_verres
from .test_commandes import commander, especes, verre  # noqa: F401  (fixture)

DROITS = (
    "ventes.view_vente",
    "ventes.add_vente",
    "crm.view_client",
    "achats.view_casseverre",
    "achats.add_casseverre",
)


@pytest.fixture
def opticien(affecter, tunis):
    return affecter("opticien", *DROITS, portee="magasin", magasin=tunis)


@pytest.fixture
def amel(tunis):
    return Client.objects.create(
        magasin_origine=tunis, nom="Ben Salah", prenom="Amel", telephone="98 123 456"
    )


def numeros(api, **filtres):
    reponse = api.get("/api/v1/ventes/", filtres)
    assert reponse.status_code == 200, reponse.json()
    return [v["numero"] for v in reponse.json()["results"]]


def test_liste_et_historique_des_visites(opticien, client_de, tunis, monture, verre, amel):  # noqa: F811
    api = client_de(opticien)
    commande = commander(tunis, monture, verre, opticien, client=amel)
    passage = enregistrer_vente(
        magasin=tunis,
        vendeur=opticien,
        lignes=[{"article": monture, "quantite": 1}],
        paiements=especes("289.500"),
    )
    assert numeros(api) == [passage.numero, commande.numero]
    # Recherche par nom, téléphone, n° de fiche ou n° de visite ; historique d'un client.
    assert numeros(api, recherche="salah") == [commande.numero]
    assert numeros(api, recherche="98 123") == [commande.numero]
    assert numeros(api, recherche=str(amel.numero)) == [commande.numero]
    assert numeros(api, client=amel.public_id) == [commande.numero]
    assert numeros(api, recherche="2") == [passage.numero]
    assert numeros(api, statut="en_commande", vendeur="opticien") == [commande.numero]
    assert numeros(api, facturee="false", du="2000-01-01") == [passage.numero, commande.numero]
    assert numeros(api, facturee="true") == []


def test_fiche_de_visite(opticien, client_de, tunis, monture, verre, amel):  # noqa: F811
    api = client_de(opticien)
    vente = commander(tunis, monture, verre, opticien, client=amel)
    recevoir_verres(vente, opticien)
    fiche = api.get(f"/api/v1/ventes/{vente.public_id}/fiche/").json()
    assert fiche["client_fiche"]["telephone"] == "98 123 456"
    assert (fiche["etat"], fiche["etat_libelle"]) == ("montage", "Montage en cours")
    assert [r["mode_libelle"] for r in fiche["reglements"]] == ["Espèces"]
    assert [(v["statut"], v["casse"]) for v in fiche["verres_commandes"]] == [("recue", None)]


def test_casse_de_verre_le_remet_a_commander(opticien, client_de, tunis, monture, verre, amel):  # noqa: F811
    api = client_de(opticien)
    vente = commander(tunis, monture, verre, opticien, client=amel)
    recevoir_verres(vente, opticien)
    api.post(f"/api/v1/ventes/{vente.public_id}/etape/", {"etape": "controle"})
    verre_recu = api.get(f"/api/v1/ventes/{vente.public_id}/fiche/").json()["verres_commandes"][0]

    reponse = api.post(
        "/api/v1/casses-verres/",
        {"ligne_commande": verre_recu["id"], "cause": "atelier", "observation": "Éclat au perçage"},
    )
    assert reponse.status_code == 201, reponse.json()
    assert reponse.json()["cause_libelle"] == "Casse à l'atelier (montage)"
    fiche = api.get(f"/api/v1/ventes/{vente.public_id}/fiche/").json()
    assert fiche["etat"] == "a_commander"
    assert fiche["verres"] == "a_commander"
    assert fiche["verres_commandes"][0]["casse"] == "Casse à l'atelier (montage)"
    assert fiche["etapes"][-1]["observation"].startswith("Casse verre")
    # Pas deux fois la même casse ; la livraison attend le nouveau verre.
    double = api.post(
        "/api/v1/casses-verres/", {"ligne_commande": verre_recu["id"], "cause": "atelier"}
    )
    assert double.status_code == 400
    recevoir_verres(vente, opticien)
    assert api.get(f"/api/v1/ventes/{vente.public_id}/fiche/").json()["etat"] == "montage"
    assert [c["vente_numero"] for c in api.get("/api/v1/casses-verres/").json()["results"]] == [
        vente.numero
    ]


def test_casse_sans_droit_refusee(affecter, client_de, tunis, monture, verre):  # noqa: F811
    vendeur = affecter("vendeur", "ventes.view_vente", portee="magasin", magasin=tunis)
    vente = commander(tunis, monture, verre, vendeur)
    recevoir_verres(vente, vendeur)
    ligne = vente.lignes.get(article=verre).commandes_fournisseur.get()
    reponse = client_de(vendeur).post(
        "/api/v1/casses-verres/", {"ligne_commande": ligne.pk, "cause": "client"}
    )
    assert reponse.status_code == 403


def test_recus_et_reste_par_vendeur(opticien, client_de, tunis, monture, verre, amel):  # noqa: F811
    api = client_de(opticien)
    vente = commander(tunis, monture, verre, opticien, client=amel)  # 649,500 dont 200
    api.post(
        f"/api/v1/ventes/{vente.public_id}/reglement/",
        {"paiements": [{"mode": "carte", "montant": "100.000"}]},
        format="json",
    )
    recus = api.get("/api/v1/ventes/recus/", {"magasin": tunis.public_id}).json()
    assert [(r["mode"], r["montant"], r["deja_regle"], r["reste_apres"]) for r in recus] == [
        ("carte", "100.000", "200.000", "349.500"),
        ("especes", "200.000", "0.000", "449.500"),
    ]
    assert recus[0]["magasin"]["societe"] == "Optique de Tunis"
    assert api.get("/api/v1/ventes/recus/", {"mode": "carte"}).json()[0]["vente_numero"] == (
        vente.numero
    )

    reste = api.get("/api/v1/ventes/reste-par-vendeur/").json()
    assert [(r["vendeur"], r["nombre"], r["reste"]) for r in reste] == [("opticien", 1, "349.500")]
    recevoir_verres(vente, opticien)
    livrer_commande(vente=vente, utilisateur=opticien, paiements=especes("349.500"))
    assert api.get("/api/v1/ventes/reste-par-vendeur/").json() == []
    assert vente.reste_a_payer == Decimal("0")


def test_recherche_clients_par_colonne_avec_solde(opticien, client_de, tunis, monture, verre, amel):  # noqa: F811
    api = client_de(opticien)
    Client.objects.create(
        magasin_origine=tunis,
        nom="Hakim",
        prenom="Ahlem",
        telephone="20422000",
        reference_externe="CM2/10/2024",
        notes="Préfère les montures légères",
    )
    commander(tunis, monture, verre, opticien, client=amel)  # 649,500 dont 200 réglés

    def lignes(**filtres):
        reponse = api.get("/api/v1/clients/", filtres)
        assert reponse.status_code == 200, reponse.json()
        return [(c["nom"], c["solde"]) for c in reponse.json()["results"]]

    assert lignes(tri="fiche") == [("Ben Salah", "449.500"), ("Hakim", "0.000")]
    assert lignes(fiche="10/2024") == [("Hakim", "0.000")]
    # Comme dans l'ancien logiciel, la colonne cherche « contient » : 1 trouve aussi CM2/10/2024.
    assert ("Ben Salah", "449.500") in lignes(fiche=str(amel.numero))
    assert lignes(telephone="98 123") == [("Ben Salah", "449.500")]
    assert lignes(nom="amel ben") == [("Ben Salah", "449.500")]
    assert lignes(prenom="ahl") == [("Hakim", "0.000")]
    assert lignes(observation="légères") == [("Hakim", "0.000")]
    assert api.get(f"/api/v1/clients/{amel.public_id}/").json()["solde"] == "449.500"
