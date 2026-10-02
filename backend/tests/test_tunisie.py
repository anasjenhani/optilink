"""Le cas de départ d'OptiLink : un magasin en Tunisie (dinar à 3 décimales, timbre sur facture)."""

from decimal import Decimal

import pytest

from apps.reseau.models import Magasin, Pays, Region
from apps.stock.models import Article, MouvementStock, PrixArticle
from apps.ventes.services import (
    FactureImpossible,
    VenteInvalide,
    enregistrer_vente,
    generer_facture,
)
from tests.conftest import tva


@pytest.fixture
def tunis(db):
    tunisie = Pays.objects.get(code="TN")
    region = Region.objects.create(code="GT", nom="Grand Tunis")
    return Magasin.tous.create(code="T01", nom="Tunis Centre", region=region, pays=tunisie)


@pytest.fixture
def monture(tunis):
    article = Article.objects.create(reference="MON-T", libelle="Monture", famille="monture")
    PrixArticle.objects.create(
        article=article, pays=tunis.pays, prix_vente_ttc=Decimal("289.500"), tva=tva(tunis.pays, 19)
    )
    MouvementStock.tous.create(magasin=tunis, article=article, quantite=3, type="reception")
    return article


def test_parametres_tunisie(db):
    tunisie = Pays.objects.get(code="TN")
    assert (tunisie.devise, tunisie.decimales, tunisie.fuseau_horaire) == ("TND", 3, "Africa/Tunis")
    assert sorted(t.taux for t in tunisie.taux_tva.all()) == [7, 13, 19]


@pytest.fixture
def societe(tunis):
    from apps.crm.models import Client

    return Client.objects.create(
        nom="Optique Services",
        prenom="SARL",
        matricule_fiscal="1234567/A/M/000",
        magasin_origine=tunis,
    )


def vendre(tunis, monture, vendeur, **extra):
    return enregistrer_vente(
        magasin=tunis,
        vendeur=vendeur,
        lignes=[{"article": monture, "quantite": 1}],
        paiements=[{"mode": "especes", "montant": Decimal("289.500")}],
        **extra,
    )


def test_ticket_de_caisse_sans_timbre(tunis, monture, creer_utilisateur):
    vente = enregistrer_vente(
        magasin=tunis,
        vendeur=creer_utilisateur("vendeur"),
        lignes=[{"article": monture, "quantite": 1, "remise_pct": Decimal("7")}],
        paiements=[{"mode": "especes", "montant": Decimal("269.235")}],
    )
    assert vente.devise == "TND"
    assert vente.total_ttc == Decimal("269.235")  # 289,500 × 0,93, arrondi au millime
    assert vente.total_ht == Decimal("226.248")  # 269,235 / 1,19
    assert vente.reste_a_payer == 0
    assert vente.numero.startswith("T01-T")
    assert not hasattr(vente, "facture") or vente.facture is None


def test_facture_generee_a_part_avec_timbre(tunis, monture, societe, creer_utilisateur):
    opticien = creer_utilisateur("opticien")
    vente = vendre(tunis, monture, opticien)
    facture = generer_facture(
        vente=vente, client=societe, emetteur=opticien, mode_paiement_timbre="especes"
    )
    assert facture.numero.startswith("T01-F")
    assert (facture.client, facture.vente) == (societe, vente)
    assert facture.total_ttc == Decimal("289.500")
    assert (facture.timbre_fiscal, facture.net_a_payer) == (Decimal("1.000"), Decimal("290.500"))
    assert facture.mode_paiement_timbre == "especes"


def test_tickets_et_factures_ont_chacun_leur_suite(tunis, monture, societe, creer_utilisateur):
    opticien = creer_utilisateur("opticien")
    premiere, seconde = vendre(tunis, monture, opticien), vendre(tunis, monture, opticien)
    facture = generer_facture(
        vente=seconde, client=societe, emetteur=opticien, mode_paiement_timbre="carte"
    )
    assert premiere.numero.endswith("-000001") and seconde.numero.endswith("-000002")
    assert facture.numero.endswith("-000001")


def test_facture_refusee_si_la_commande_n_est_pas_soldee(
    tunis, monture, societe, creer_utilisateur
):
    from apps.ventes.models import Paiement

    opticien = creer_utilisateur("opticien")
    vente = vendre(tunis, monture, opticien)
    # Simule une commande avec acompte : une partie du paiement manque.
    Paiement.objects.filter(vente=vente).update(montant=Decimal("100.000"))
    with pytest.raises(FactureImpossible, match="reste 189.500 TND"):
        generer_facture(
            vente=vente, client=societe, emetteur=opticien, mode_paiement_timbre="carte"
        )


def test_une_seule_facture_par_vente_et_client_obligatoire(
    tunis, monture, societe, creer_utilisateur
):
    opticien = creer_utilisateur("opticien")
    vente = vendre(tunis, monture, opticien)
    with pytest.raises(FactureImpossible, match="client"):
        generer_facture(vente=vente, client=None, emetteur=opticien, mode_paiement_timbre="carte")
    with pytest.raises(FactureImpossible, match="timbre"):
        generer_facture(vente=vente, client=societe, emetteur=opticien)
    generer_facture(vente=vente, client=societe, emetteur=opticien, mode_paiement_timbre="carte")
    with pytest.raises(FactureImpossible, match="déjà facturée"):
        generer_facture(
            vente=vente, client=societe, emetteur=opticien, mode_paiement_timbre="carte"
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
        article=article, pays=tunis.pays, prix_vente_ttc=Decimal("12.345"), tva=tva(tunis.pays, 19)
    ).full_clean()
    with pytest.raises(ValidationError, match="2 décimales"):
        PrixArticle(
            article=article,
            pays=reseau["lille"].pays,
            prix_vente_ttc=Decimal("12.345"),
            tva=tva(reseau["lille"].pays, 20),
        ).full_clean()
    with pytest.raises(ValidationError, match="autre pays"):
        PrixArticle(
            article=article, pays=tunis.pays, prix_vente_ttc=10, tva=tva(reseau["lille"].pays, 20)
        ).full_clean()


def test_l_administrateur_change_le_taux_pour_tous_les_articles(tunis, monture):
    taux = tva(tunis.pays, 19)
    taux.taux = Decimal("18")
    taux.save()
    assert PrixArticle.objects.get(article=monture).tva.taux == Decimal("18")


def test_administrateur_regle_la_tva_sans_voir_les_ventes(db):
    from django.contrib.auth.models import Group

    admin = set(
        Group.objects.get(name="Administrateur système").permissions.values_list(
            "codename", flat=True
        )
    )
    assert {"change_tauxtva", "add_tauxtva", "change_pays"} <= admin
    assert "view_vente" not in admin


def test_caisse_tunisienne_par_l_api(tunis, monture, societe, affecter, client_de):
    vendeur = affecter(
        "vendeur",
        "ventes.add_vente",
        "ventes.view_vente",
        "stock.view_article",
        "crm.view_client",
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
    corps = {
        "magasin": str(tunis.public_id),
        "lignes": [{"article": article["id"], "quantite": 1}],
        "paiements": [{"mode": "carte", "montant": "289.500"}],
    }
    ticket = api.post("/api/v1/ventes/", corps, format="json")
    assert ticket.status_code == 201, ticket.json()
    assert (ticket.json()["total_ttc"], ticket.json()["devise"]) == ("289.500", "TND")
    assert (ticket.json()["reste_a_payer"], ticket.json()["facture"]) == ("0.000", None)

    # Le vendeur encaisse mais ne facture pas ; l'opticien génère la facture.
    demande = {"vente": ticket.json()["id"], "client": str(societe.public_id)}
    assert api.post("/api/v1/factures/", demande, format="json").status_code == 403
    opticien = affecter(
        "opticien",
        "ventes.add_facture",
        "ventes.view_facture",
        "ventes.view_vente",
        portee="magasin",
        magasin=tunis,
    )
    facturation = client_de(opticien)
    sans_timbre = facturation.post("/api/v1/factures/", demande, format="json")
    assert sans_timbre.status_code == 400
    facture = facturation.post(
        "/api/v1/factures/", {**demande, "mode_paiement_timbre": "especes"}, format="json"
    )
    assert facture.status_code == 201, facture.json()
    assert facture.json()["net_a_payer"] == "290.500"
    assert facture.json()["client"]["matricule_fiscal"] == "1234567/A/M/000"
    assert facture.json()["lignes"][0]["libelle"] == "Monture"


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
