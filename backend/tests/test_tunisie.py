"""Le cas de départ d'OptiLink : un magasin en Tunisie (dinar à 3 décimales, timbre fiscal)."""

from decimal import Decimal

import pytest

from apps.reseau.models import Magasin, Pays, Region
from apps.stock.models import Article, MouvementStock, PrixArticle
from apps.ventes.services import VenteInvalide, enregistrer_vente


@pytest.fixture
def tunis(db):
    tunisie = Pays.objects.get(code="TN")
    region = Region.objects.create(code="GT", nom="Grand Tunis")
    return Magasin.tous.create(code="T01", nom="Tunis Centre", region=region, pays=tunisie)


@pytest.fixture
def monture(tunis):
    article = Article.objects.create(reference="MON-T", libelle="Monture", famille="monture")
    PrixArticle.objects.create(
        article=article, pays=tunis.pays, prix_vente_ttc=Decimal("289.500"), taux_tva=Decimal("19")
    )
    MouvementStock.tous.create(magasin=tunis, article=article, quantite=3, type="reception")
    return article


def test_parametres_tunisie(db):
    tunisie = Pays.objects.get(code="TN")
    assert (tunisie.devise, tunisie.decimales, tunisie.fuseau_horaire) == ("TND", 3, "Africa/Tunis")
    assert sorted(t.taux for t in tunisie.taux_tva.all()) == [7, 13, 19]


def test_vente_en_dinars_avec_timbre(tunis, monture, creer_utilisateur):
    vendeur = creer_utilisateur("vendeur")
    vente = enregistrer_vente(
        magasin=tunis,
        vendeur=vendeur,
        lignes=[{"article": monture, "quantite": 1, "remise_pct": Decimal("7")}],
        paiements=[{"mode": "especes", "montant": Decimal("270.235")}],
    )
    assert vente.devise == "TND"
    assert vente.total_ttc == Decimal("269.235")  # 289,500 × 0,93, arrondi au millime
    assert vente.total_ht == Decimal("226.248")  # 269,235 / 1,19
    assert vente.timbre_fiscal == Decimal("1.000")
    assert vente.net_a_payer == Decimal("270.235")
    assert vente.numero.startswith("T01-")


def test_le_timbre_doit_etre_paye(tunis, monture, creer_utilisateur):
    with pytest.raises(VenteInvalide, match="net à payer"):
        enregistrer_vente(
            magasin=tunis,
            vendeur=creer_utilisateur("vendeur"),
            lignes=[{"article": monture, "quantite": 1}],
            paiements=[{"mode": "carte", "montant": Decimal("289.500")}],
        )


def test_article_sans_prix_dans_le_pays_invendable(tunis, creer_utilisateur):
    article = Article.objects.create(reference="X", libelle="X", famille="accessoire")
    MouvementStock.tous.create(magasin=tunis, article=article, quantite=1, type="reception")
    with pytest.raises(VenteInvalide, match="pas de prix en Tunisie"):
        enregistrer_vente(
            magasin=tunis,
            vendeur=creer_utilisateur("vendeur"),
            lignes=[{"article": article, "quantite": 1}],
            paiements=[{"mode": "carte", "montant": Decimal("1")}],
        )


def test_prix_controle_selon_la_monnaie(tunis, reseau):
    from django.core.exceptions import ValidationError

    article = Article.objects.create(reference="Y", libelle="Y", famille="accessoire")
    PrixArticle(
        article=article, pays=tunis.pays, prix_vente_ttc=Decimal("12.345"), taux_tva=19
    ).full_clean()
    with pytest.raises(ValidationError, match="2 décimales"):
        PrixArticle(
            article=article,
            pays=reseau["lille"].pays,
            prix_vente_ttc=Decimal("12.345"),
            taux_tva=20,
        ).full_clean()
    with pytest.raises(ValidationError, match="TVA inconnu"):
        PrixArticle(article=article, pays=tunis.pays, prix_vente_ttc=10, taux_tva=20).full_clean()


def test_caisse_tunisienne_par_l_api(tunis, monture, affecter, client_de):
    vendeur = affecter(
        "vendeur",
        "ventes.add_vente",
        "ventes.view_vente",
        "stock.view_article",
        portee="magasin",
        magasin=tunis,
    )
    api = client_de(vendeur)
    article = api.get("/api/v1/articles/", {"magasin": str(tunis.public_id)}).json()["results"][0]
    assert (article["prix_vente_ttc"], article["taux_tva"], article["devise"]) == (
        "289.500",
        "19.00",
        "TND",
    )
    reponse = api.post(
        "/api/v1/ventes/",
        {
            "magasin": str(tunis.public_id),
            "lignes": [{"article": article["id"], "quantite": 1}],
            "paiements": [{"mode": "carte", "montant": "290.500"}],
        },
        format="json",
    )
    assert reponse.status_code == 201, reponse.json()
    assert (reponse.json()["net_a_payer"], reponse.json()["devise"]) == ("290.500", "TND")


def test_identifiant_prescripteur_selon_le_pays(tunis, reseau, affecter, client_de):
    from apps.crm.models import Client

    opticien = affecter(
        "opticien", "optique.add_prescription", "optique.view_prescription", portee="reseau"
    )
    client = Client.objects.create(nom="Ben Ali", prenom="Sami", magasin_origine=tunis)
    corps = {
        "client": str(client.public_id),
        "type": "lunettes",
        "date_prescription": "2026-09-01",
        "prescripteur": "Dr Trabelsi",
        "prescripteur_identifiant": "TN-4521",
        "mesures": {"od": {"sphere": "-1.00"}, "og": {"sphere": "-1.25"}},
    }
    api = client_de(opticien)
    # En Tunisie, pas de format imposé ; en France, le n° RPPS compte 11 chiffres.
    tunisie = api.post(
        "/api/v1/prescriptions/", {**corps, "magasin_saisie": str(tunis.public_id)}, format="json"
    )
    assert tunisie.status_code == 201, tunisie.json()
    france = api.post(
        "/api/v1/prescriptions/",
        {**corps, "magasin_saisie": str(reseau["lille"].public_id)},
        format="json",
    )
    assert france.status_code == 400
    assert "prescripteur_identifiant" in france.json()
