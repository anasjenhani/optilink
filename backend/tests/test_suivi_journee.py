"""Suivi qualité des commandes (étapes de l'atelier) et état de la journée de vente."""

from decimal import Decimal

import pytest
from django.utils import timezone

from apps.ventes.models import EtapeCommande, Vente
from apps.ventes.services import enregistrer_vente, livrer_commande

from .conftest import recevoir_verres
from .test_commandes import commander, especes, verre  # noqa: F401  (fixture)

DROITS_VENDEUR = ("ventes.view_vente", "ventes.add_vente", "crm.view_client")


@pytest.fixture
def opticien(affecter, tunis):
    return affecter("opticien", *DROITS_VENDEUR, portee="magasin", magasin=tunis)


def etats(api, **filtres):
    reponse = api.get("/api/v1/ventes/suivi/", filtres)
    assert reponse.status_code == 200, reponse.json()
    return {ligne["numero"]: ligne["etat"] for ligne in reponse.json()}


def test_etapes_de_la_visite_a_la_livraison(opticien, client_de, tunis, monture, verre):  # noqa: F811
    api = client_de(opticien)
    vente = commander(tunis, monture, verre, opticien)
    ligne = api.get("/api/v1/ventes/suivi/").json()[0]
    assert ligne["etat"] == "a_commander"
    assert ligne["etat_libelle"] == "Visite créée à commander"
    assert (ligne["type"], ligne["stockable"]) == ("verre", False)
    assert ligne["monture"]["reference"] == "MON-T"

    # Verres reçus du fournisseur : la commande passe au montage d'elle-même.
    recevoir_verres(vente, opticien)
    assert etats(api) == {vente.numero: "montage"}

    url = f"/api/v1/ventes/{vente.public_id}/etape/"
    reponse = api.post(url, {"etape": "controle", "observation": "Axe OG à revoir"})
    assert reponse.status_code == 200, reponse.json()
    api.post(url, {"etape": "contact_client"})
    ligne = api.get("/api/v1/ventes/suivi/").json()[0]
    assert ligne["etat"] == "contact_client"
    assert ligne["observation"] == "Axe OG à revoir"
    assert list(EtapeCommande.objects.values_list("etape", "par__username")) == [
        ("controle", "opticien"),
        ("contact_client", "opticien"),
    ]

    livrer_commande(vente=vente, utilisateur=opticien, paiements=especes("449.500"))
    assert etats(api, etat="livree") == {vente.numero: "livree"}
    assert etats(api, etat="contact_client") == {}
    refus = api.post(url, {"etape": "montage"})
    assert refus.status_code == 400


def test_instance_et_saisie_ne_reculent_pas_les_verres(
    opticien,
    client_de,
    tunis,
    monture,
    verre,  # noqa: F811
):
    api = client_de(opticien)
    vente = commander(tunis, monture, verre, opticien)
    url = f"/api/v1/ventes/{vente.public_id}/etape/"
    api.post(url, {"etape": "instance", "observation": "Client injoignable"})
    assert etats(api) == {vente.numero: "instance"}
    api.post(url, {"etape": "commandee"})
    recevoir_verres(vente, opticien)
    # Les verres reçus l'emportent sur une étape saisie plus tôt dans le parcours.
    assert etats(api) == {vente.numero: "montage"}


def test_vente_immediate_hors_suivi_et_filtres(opticien, client_de, tunis, monture, verre):  # noqa: F811
    api = client_de(opticien)
    enregistrer_vente(
        magasin=tunis,
        vendeur=opticien,
        lignes=[{"article": monture, "quantite": 1}],
        paiements=especes("289.500"),
    )
    vente = commander(tunis, monture, verre, opticien)
    annee = timezone.localdate().year
    assert list(etats(api)) == [vente.numero]
    assert list(etats(api, annee=annee, type="verre")) == [vente.numero]
    assert etats(api, type="lentille") == {}
    assert etats(api, annee=annee - 1) == {}


def test_suivi_et_journee_reserves(affecter, client_de, tunis):
    stagiaire = client_de(affecter("stagiaire", "crm.view_client", portee="magasin", magasin=tunis))
    assert stagiaire.get("/api/v1/ventes/suivi/").status_code == 403
    params = {"magasin": str(tunis.public_id)}
    assert stagiaire.get("/api/v1/ventes/journee/", params).status_code == 403


def test_journee_de_vente(opticien, client_de, tunis, monture, verre, reseau):  # noqa: F811
    api = client_de(opticien)
    comptant = enregistrer_vente(
        magasin=tunis,
        vendeur=opticien,
        lignes=[{"article": monture, "quantite": 1}],
        paiements=[{"mode": "carte", "montant": Decimal("289.500")}],
    )
    commande = commander(tunis, monture, verre, opticien)  # 649,500, acompte 200 en espèces

    reponse = api.get("/api/v1/ventes/journee/", {"magasin": str(tunis.public_id)})
    assert reponse.status_code == 200, reponse.json()
    jour = reponse.json()
    assert jour["nombre_ventes"] == 2
    assert Decimal(jour["total_ventes"]) == Decimal("939.000")
    assert Decimal(jour["reste_sur_ventes"]) == Decimal("449.500")
    assert {m["mode"]: Decimal(m["montant"]) for m in jour["encaisse_par_mode"]} == {
        "Carte bancaire": Decimal("289.500"),
        "Espèces": Decimal("200.000"),
    }
    lignes = {ligne["numero"]: ligne for ligne in jour["ventes"]}
    assert (lignes[comptant.numero]["soldee"], lignes[comptant.numero]["livree"]) == (True, True)
    assert lignes[comptant.numero]["commande"] is False
    assert lignes[commande.numero]["commande"] is True
    assert (lignes[commande.numero]["soldee"], lignes[commande.numero]["livree"]) == (False, False)
    assert Decimal(lignes[commande.numero]["reste"]) == Decimal("449.500")

    hier = api.get(
        "/api/v1/ventes/journee/", {"magasin": str(tunis.public_id), "date": "2020-01-01"}
    ).json()
    assert hier["nombre_ventes"] == 0
    # Un magasin hors du périmètre est introuvable.
    ailleurs = api.get("/api/v1/ventes/journee/", {"magasin": str(reseau["lille"].public_id)})
    assert ailleurs.status_code == 404
    assert Vente.objects.count() == 2
