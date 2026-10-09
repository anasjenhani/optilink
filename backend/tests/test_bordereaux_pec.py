"""Bordereaux CNAM / conventions : regrouper les prises en charge, envoyer, saisir le règlement."""

from decimal import Decimal

import pytest

from apps.crm.models import Organisme
from apps.ventes.models import BordereauPec

from .test_commandes import commander, verre  # noqa: F401  (fixture)

DROITS = (
    "ventes.view_vente",
    "ventes.view_priseencharge",
    "ventes.add_priseencharge",
    "ventes.change_priseencharge",
    "ventes.view_bordereaupec",
    "ventes.add_bordereaupec",
    "ventes.change_bordereaupec",
)


@pytest.fixture
def gestionnaire(affecter, tunis):
    return affecter("gestionnaire", *DROITS, portee="magasin", magasin=tunis)


@pytest.fixture
def cnam(db):
    return Organisme.objects.get(pays__code="TN", nom="CNAM")


def pec(api, vente, organisme, montant):
    reponse = api.post(
        "/api/v1/prises-en-charge/",
        {"vente": vente.public_id, "organisme": organisme.public_id, "montant": montant},
    )
    assert reponse.status_code == 201, reponse.json()
    return reponse.json()


@pytest.fixture
def deux_pec(gestionnaire, client_de, tunis, monture, verre, cnam):  # noqa: F811
    api = client_de(gestionnaire)
    ventes = [commander(tunis, monture, verre, gestionnaire) for _ in range(2)]
    return api, ventes, [pec(api, v, cnam, "150.000") for v in ventes]


def test_preparer_envoyer_regler(deux_pec, tunis, cnam):
    api, ventes, pecs = deux_pec
    a_envoyer = api.get(
        "/api/v1/bordereaux-pec/a-envoyer/",
        {"magasin": tunis.public_id, "organisme": cnam.public_id},
    ).json()
    assert len(a_envoyer) == 2

    cree = api.post(
        "/api/v1/bordereaux-pec/",
        {
            "magasin": str(tunis.public_id),
            "organisme": str(cnam.public_id),
            "prises_en_charge": [p["id"] for p in pecs],
        },
        format="json",
    )
    assert cree.status_code == 201, cree.json()
    bordereau = cree.json()
    assert bordereau["numero"].startswith("T01-BP")
    assert bordereau["total"] == "300.000"
    url = f"/api/v1/bordereaux-pec/{bordereau['id']}/"

    # Dans un bordereau, le statut ne se change plus à la main.
    refus = api.patch(f"/api/v1/prises-en-charge/{pecs[0]['id']}/", {"statut": "refusee"})
    assert refus.status_code == 400

    # Pas de règlement avant l'envoi.
    assert api.post(url + "regler/", {"le": "2026-10-20", "mode": "virement"}).status_code == 400
    assert api.post(url + "envoyer/", {"le": "2026-10-10"}).status_code == 200
    assert api.delete(url).status_code == 400

    # La CNAM paie la première en entier, réduit la seconde : l'écart revient au client.
    sans_motif = api.post(
        url + "regler/",
        {
            "le": "2026-10-20",
            "mode": "virement",
            "reference": "VIR-889",
            "lignes": [{"prise_en_charge": pecs[1]["id"], "montant_regle": "100.000"}],
        },
        format="json",
    )
    assert sans_motif.status_code == 400
    regle = api.post(
        url + "regler/",
        {
            "le": "2026-10-20",
            "mode": "virement",
            "reference": "VIR-889",
            "lignes": [
                {
                    "prise_en_charge": pecs[1]["id"],
                    "montant_regle": "100.000",
                    "motif_rejet": "Plafond verres",
                }
            ],
        },
        format="json",
    )
    assert regle.status_code == 200, regle.json()
    assert (regle.json()["statut"], regle.json()["total_regle"]) == ("regle", "250.000")
    for vente in ventes:
        vente.refresh_from_db()
    assert [v.reste_a_payer for v in ventes] == [Decimal("299.500"), Decimal("349.500")]


def test_modifier_puis_supprimer(deux_pec, tunis, cnam):
    api, ventes, pecs = deux_pec
    bordereau = api.post(
        "/api/v1/bordereaux-pec/",
        {
            "magasin": str(tunis.public_id),
            "organisme": str(cnam.public_id),
            "prises_en_charge": [pecs[0]["id"]],
        },
        format="json",
    ).json()
    url = f"/api/v1/bordereaux-pec/{bordereau['id']}/"
    # Une prise en charge ne va que dans un seul bordereau.
    doublon = api.post(
        "/api/v1/bordereaux-pec/",
        {
            "magasin": str(tunis.public_id),
            "organisme": str(cnam.public_id),
            "prises_en_charge": [pecs[0]["id"]],
        },
        format="json",
    )
    assert doublon.status_code == 400

    modifie = api.patch(url, {"prises_en_charge": [p["id"] for p in pecs]}, format="json")
    assert modifie.status_code == 200, modifie.json()
    assert len(modifie.json()["prises_en_charge"]) == 2
    assert api.delete(url).status_code == 204
    assert not BordereauPec.tous.exists()
    assert ventes[0].prises_en_charge.get().bordereau is None


def test_rejet_total_et_droits(deux_pec, affecter, client_de, tunis, cnam):
    api, ventes, pecs = deux_pec
    bordereau = api.post(
        "/api/v1/bordereaux-pec/",
        {
            "magasin": str(tunis.public_id),
            "organisme": str(cnam.public_id),
            "prises_en_charge": [pecs[0]["id"]],
        },
        format="json",
    ).json()
    url = f"/api/v1/bordereaux-pec/{bordereau['id']}/"
    api.post(url + "envoyer/", {"le": "2026-10-10"})
    api.post(
        url + "regler/",
        {
            "le": "2026-10-20",
            "mode": "cheque",
            "lignes": [
                {
                    "prise_en_charge": pecs[0]["id"],
                    "montant_regle": "0",
                    "motif_rejet": "Hors délai",
                }
            ],
        },
        format="json",
    )
    ventes[0].refresh_from_db()
    assert ventes[0].reste_a_payer == Decimal("449.500")
    assert ventes[0].prises_en_charge.get().statut == "refusee"

    vendeur = affecter("vendeur", "ventes.view_vente", portee="magasin", magasin=tunis)
    assert client_de(vendeur).get("/api/v1/bordereaux-pec/").status_code == 403
