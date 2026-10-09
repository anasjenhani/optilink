"""Fiche lunettes : monture, verres droit et gauche, suppléments, ordonnance et mesures."""

from datetime import date
from decimal import Decimal

import pytest

from apps.crm.models import Client
from apps.optique.models import Prescription
from apps.stock.models import Article, Monture, PrixArticle

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
        (lambda s: s["lignes"][3].update(lunette=1), "lunettes inconnues"),
        (lambda s: s["lunettes"].append({}), "Lunette 2 : aucun article"),
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


@pytest.fixture
def lentille(tunis):
    article = Article.objects.create(
        reference="LEN-M", libelle="Acuvue Oasys (6)", famille="lentille"
    )
    PrixArticle.objects.create(
        article=article, pays=tunis.pays, prix_vente_ttc=Decimal("95.000"), tva=tva(tunis.pays, 7)
    )
    from apps.stock.models import MouvementStock

    MouvementStock.tous.create(magasin=tunis, article=article, quantite=10, type="reception")
    return article


def ordonnance_lentilles(client, tunis, opticien):
    prescription = Prescription(
        client=client,
        type="lentilles",
        date_prescription=date(2026, 9, 1),
        prescripteur="Dr Gharbi",
        magasin_saisie=tunis,
        saisie_par=opticien,
    )
    prescription.mesures = {
        "od": {"sphere": "-2.00", "rayon": "8.60", "diametre": "14.20"},
        "og": {"sphere": "-1.75", "rayon": "8.60", "diametre": "14.20"},
    }
    prescription.save()
    return prescription


def test_lentilles_droite_gauche_avec_lot_et_peremption(opticien, client_de, tunis, lentille, amel):
    api = client_de(opticien)
    prescription = ordonnance_lentilles(amel, tunis, opticien)
    corps = {
        "magasin": str(tunis.public_id),
        "client": str(amel.public_id),
        "paiements": [{"mode": "carte", "montant": "285.000"}],
        "lentilles": [{"prescription": str(prescription.public_id), "observation": "Essai"}],
        "lignes": [
            {
                "article": str(lentille.public_id),
                "quantite": 2,
                "lentilles": 0,
                "role": "lentille_d",
                "numero_lot": "B12345",
                "date_peremption": "2028-03-31",
            },
            {
                "article": str(lentille.public_id),
                "quantite": 1,
                "lentilles": 0,
                "role": "lentille_g",
                "numero_lot": "B12346",
            },
        ],
    }
    reponse = api.post("/api/v1/ventes/", corps, format="json")
    assert reponse.status_code == 201, reponse.json()
    (jeu,) = reponse.json()["lentilles"]
    assert (jeu["droite"]["quantite"], jeu["droite"]["numero_lot"]) == (2, "B12345")
    assert jeu["droite"]["date_peremption"] == "2028-03-31"
    assert (jeu["gauche"]["numero_lot"], jeu["total_ttc"]) == ("B12346", "285.000")

    historique = api.get("/api/v1/lentilles/", {"client": amel.public_id}).json()["results"]
    assert [h["id"] for h in historique] == [f"{reponse.json()['numero']}/L1"]

    # Une ordonnance de lunettes ne vaut pas pour des lentilles.
    corps["lentilles"][0]["prescription"] = str(ordonnance(amel, tunis, opticien).public_id)
    refus = api.post("/api/v1/ventes/", corps, format="json")
    assert refus.status_code == 400
    assert "ordonnance de lentilles" in refus.json()["detail"]


@pytest.mark.parametrize(
    ("categorie", "attendu"), [("optique", 400), ("applique", 400), ("solaire", 201)]
)
def test_une_lunette_optique_ou_applique_va_dans_une_peniche(
    opticien, client_de, tunis, monture, categorie, attendu
):
    Monture.objects.create(article=monture, categorie=categorie)
    api = client_de(opticien)
    vente = {
        "magasin": str(tunis.public_id),
        "lignes": [{"article": str(monture.public_id), "quantite": 1}],
        "paiements": [{"mode": "especes", "montant": "289.500"}],
    }
    reponse = api.post("/api/v1/ventes/", vente, format="json")
    assert reponse.status_code == attendu, reponse.json()
    if attendu == 400:
        assert "péniche" in str(reponse.json())
        commande = {**vente, "commande": True, "peniche": peniche()}
        assert api.post("/api/v1/ventes/", commande, format="json").status_code == 201


def test_une_vente_contient_plusieurs_lunettes(
    opticien,
    client_de,
    tunis,
    monture,
    verre,  # noqa: F811
    antireflet,
    amel,
):
    prescription = ordonnance(amel, tunis, opticien)
    corps = saisie(tunis, amel, monture, verre, antireflet, prescription)
    corps["lunettes"].append(dict(corps["lunettes"][0]))
    corps["lignes"] += [
        {**ligne, "lunette": 1} for ligne in corps["lignes"] if ligne["role"] != "monture"
    ]
    reponse = client_de(opticien).post("/api/v1/ventes/", corps, format="json")
    assert reponse.status_code == 201, reponse.json()
    assert len(reponse.json()["lunettes"]) == 2
