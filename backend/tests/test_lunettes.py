"""Fiche lunettes : monture, verres droit et gauche, suppléments, ordonnance et mesures."""

from datetime import date
from decimal import Decimal

import pytest

from apps.crm.models import Client
from apps.optique.models import Prescription
from apps.stock.models import Article, PrixArticle

from .conftest import tva
from .test_commandes import peniche, verre  # noqa: F401  (fixture)

DROITS = (
    "ventes.view_vente",
    "ventes.add_vente",
    "crm.view_client",
    "optique.view_prescription",
)


@pytest.fixture
def opticien(affecter, tunis):
    return affecter("opticien", *DROITS, portee="magasin", magasin=tunis)


@pytest.fixture
def amel(tunis):
    return Client.objects.create(magasin_origine=tunis, nom="Ben Salah", prenom="Amel")


@pytest.fixture
def antireflet(tunis):
    article = Article.objects.create(
        reference="SUP-AR", libelle="Antireflet", famille="supplement", sur_commande=True
    )
    PrixArticle.objects.create(
        article=article, pays=tunis.pays, prix_vente_ttc=Decimal("40.000"), tva=tva(tunis.pays, 7)
    )
    return article


def ordonnance(client, tunis, opticien):
    prescription = Prescription(
        client=client,
        type="lunettes",
        date_prescription=date(2026, 9, 1),
        prescripteur="Dr Gharbi",
        magasin_saisie=tunis,
        saisie_par=opticien,
    )
    prescription.mesures = {
        "od": {"sphere": "-1.25", "cylindre": "-0.50", "axe": 90, "addition": "2.00"},
        "og": {"sphere": "-1.00", "cylindre": "0", "axe": None, "addition": "2.00"},
    }
    prescription.save()
    return prescription


def saisie(tunis, client, monture, verre, antireflet, prescription, **lunette):  # noqa: F811
    return {
        "magasin": str(tunis.public_id),
        "client": str(client.public_id),
        "commande": True,
        "peniche": peniche(),
        "paiements": [{"mode": "especes", "montant": "100.000"}],
        "lunettes": [
            {
                "vision": "progressif",
                "prescription": str(prescription.public_id),
                "oeil_directeur": "droit",
                "ecart_d": "31.5",
                "ecart_g": "32.0",
                "hauteur_d": "18.0",
                "hauteur_g": "18.0",
                "observation": "Monture à ajuster",
                **lunette,
            }
        ],
        "lignes": [
            {"article": str(monture.public_id), "quantite": 1, "lunette": 0, "role": "monture"},
            {"article": str(verre.public_id), "quantite": 1, "lunette": 0, "role": "verre_d"},
            {"article": str(verre.public_id), "quantite": 1, "lunette": 0, "role": "verre_g"},
            {
                "article": str(antireflet.public_id),
                "quantite": 1,
                "lunette": 0,
                "role": "supplement_d",
            },
        ],
    }


def test_lunette_enregistree_avec_ses_verres_et_mesures(
    opticien,
    client_de,
    tunis,
    monture,
    verre,  # noqa: F811
    antireflet,
    amel,
):
    api = client_de(opticien)
    prescription = ordonnance(amel, tunis, opticien)
    reponse = api.post(
        "/api/v1/ventes/",
        saisie(tunis, amel, monture, verre, antireflet, prescription),
        format="json",
    )
    assert reponse.status_code == 201, reponse.json()
    vente = reponse.json()
    assert vente["total_ttc"] == "689.500"  # 289,500 + 2 × 180 + 40
    (lunette,) = vente["lunettes"]
    assert lunette["monture"] == "Monture"
    assert (lunette["verre_d"], lunette["verre_g"]) == ("Verre progressif", "Verre progressif")
    assert lunette["supplements_d"] == ["Antireflet"]
    assert (lunette["vision_libelle"], lunette["ecart_d"], lunette["hauteur_g"]) == (
        "Progressif",
        "31.5",
        "18.0",
    )
    assert lunette["prescription"] == str(prescription.public_id)
    assert {ligne["role"] for ligne in vente["lignes"]} == {
        "monture",
        "verre_d",
        "verre_g",
        "supplement_d",
    }

    historique = api.get("/api/v1/lunettes/", {"client": amel.public_id}).json()["results"]
    assert [(h["id"], h["peniche"], h["monture"]) for h in historique] == [
        (f"{vente['numero']}/1", vente["peniche"], "Monture")
    ]


@pytest.mark.parametrize(
    ("changer", "message"),
    [
        (lambda s: s["lignes"][2].update(role="verre_d"), "verre droit en double"),
        (lambda s: s["lignes"][1].update(quantite=2), "quantité 1 par lunette"),
        (lambda s: s["lignes"][0].update(role="verre_d"), "ne peut pas servir de verre droit"),
        (lambda s: s["lignes"].pop(1), "un supplément va avec son verre"),
        (lambda s: s["lignes"][3].update(lunette=1), "lunette inconnue"),
        (lambda s: s["lunettes"].append({}), "La lunette 2 ne contient aucun article"),
    ],
)
def test_lunette_mal_composee_refusee(
    opticien,
    client_de,
    tunis,
    monture,
    verre,  # noqa: F811
    antireflet,
    amel,
    changer,
    message,
):
    corps = saisie(tunis, amel, monture, verre, antireflet, ordonnance(amel, tunis, opticien))
    changer(corps)
    reponse = client_de(opticien).post("/api/v1/ventes/", corps, format="json")
    assert reponse.status_code == 400
    assert message.lower() in reponse.json()["detail"].lower()


def test_ordonnance_d_un_autre_client_ou_sans_droit_refusee(
    opticien,
    affecter,
    client_de,
    tunis,
    monture,
    verre,  # noqa: F811
    antireflet,
    amel,
):
    autre = Client.objects.create(magasin_origine=tunis, nom="Hakim", prenom="Ahlem")
    corps = saisie(tunis, amel, monture, verre, antireflet, ordonnance(autre, tunis, opticien))
    reponse = client_de(opticien).post("/api/v1/ventes/", corps, format="json")
    assert reponse.status_code == 400
    assert "pas celle du client" in reponse.json()["detail"]

    vendeur = affecter("vendeur", *DROITS[:3], portee="magasin", magasin=tunis)
    corps = saisie(tunis, amel, monture, verre, antireflet, ordonnance(amel, tunis, opticien))
    assert client_de(vendeur).post("/api/v1/ventes/", corps, format="json").status_code == 403
