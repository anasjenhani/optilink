"""Commandes : acompte à la commande, règlements, solde à la livraison ; verres hors stock."""

from decimal import Decimal

import pytest

from apps.stock.models import Article, MouvementStock, PrixArticle, stock_disponible
from apps.ventes.models import Vente
from apps.ventes.services import (
    FactureImpossible,
    VenteInvalide,
    encaisser_devis,
    enregistrer_vente,
    etablir_devis,
    generer_facture,
    livrer_commande,
    regler_commande,
)
from tests.conftest import tva


@pytest.fixture
def verre(tunis):
    article = Article.objects.create(
        reference="VER-C", libelle="Verre progressif", famille="verre", sur_commande=True
    )
    PrixArticle.objects.create(
        article=article, pays=tunis.pays, prix_vente_ttc=Decimal("180.000"), tva=tva(tunis.pays, 7)
    )
    return article


def especes(montant):
    return [{"mode": "especes", "montant": Decimal(montant)}]


def commander(tunis, monture, verre, vendeur, acompte="200.000", **extra):
    # 289,500 + 2 × 180,000 = 649,500
    return enregistrer_vente(
        magasin=tunis,
        vendeur=vendeur,
        lignes=[{"article": monture, "quantite": 1}, {"article": verre, "quantite": 2}],
        paiements=especes(acompte) if Decimal(acompte) else [],
        commande=True,
        **extra,
    )


def test_commande_avec_acompte_verres_hors_stock(tunis, monture, verre, creer_utilisateur):
    vente = commander(tunis, monture, verre, creer_utilisateur("vendeur"))
    assert (vente.statut, vente.total_ttc) == (Vente.Statut.EN_COMMANDE, Decimal("649.500"))
    assert vente.reste_a_payer == Decimal("449.500")
    assert vente.livree_le is None
    # La monture sort du stock à la commande ; les verres, commandés au fournisseur, n'y sont pas.
    assert stock_disponible(tunis, monture) == 2
    assert not MouvementStock.tous.filter(article=verre).exists()


def test_verres_vendus_seulement_en_commande(tunis, verre, creer_utilisateur):
    with pytest.raises(VenteInvalide, match="enregistrer une commande"):
        enregistrer_vente(
            magasin=tunis,
            vendeur=creer_utilisateur("vendeur"),
            lignes=[{"article": verre, "quantite": 1}],
            paiements=especes("180.000"),
        )


def test_commande_sans_acompte_et_acompte_trop_eleve(tunis, monture, verre, creer_utilisateur):
    vendeur = creer_utilisateur("vendeur")
    assert commander(tunis, monture, verre, vendeur, acompte="0").reste_a_payer == Decimal(
        "649.500"
    )
    with pytest.raises(VenteInvalide, match="dépasse le total"):
        commander(tunis, monture, verre, vendeur, acompte="700.000")


def test_reglements_puis_livraison_contre_le_solde(
    tunis, monture, verre, societe, creer_utilisateur
):
    vendeur, opticien = creer_utilisateur("vendeur"), creer_utilisateur("opticien")
    vente = commander(tunis, monture, verre, vendeur)
    with pytest.raises(VenteInvalide, match="dépasse le reste"):
        regler_commande(vente=vente, paiements=especes("500.000"), utilisateur=vendeur)
    regler_commande(vente=vente, paiements=especes("100.000"), utilisateur=vendeur)
    with pytest.raises(VenteInvalide, match="doit encore 349.500 TND"):
        livrer_commande(vente=vente, utilisateur=opticien)
    with pytest.raises(FactureImpossible, match="reste 349.500"):
        generer_facture(
            vente=vente, client=societe, emetteur=opticien, mode_paiement_timbre="carte"
        )

    livrer_commande(vente=vente, utilisateur=opticien, paiements=especes("349.500"))
    vente.refresh_from_db()
    assert (vente.statut, vente.livree_par, vente.reste_a_payer) == (
        Vente.Statut.LIVREE,
        opticien,
        0,
    )
    assert [p.recu_par for p in vente.paiements.order_by("recu_le")] == [vendeur, vendeur, opticien]
    with pytest.raises(VenteInvalide, match="déjà livrée"):
        livrer_commande(vente=vente, utilisateur=opticien)
    facture = generer_facture(
        vente=vente, client=societe, emetteur=opticien, mode_paiement_timbre="carte"
    )
    assert facture.net_a_payer == Decimal("650.500")


def test_devis_de_verres_passe_en_commande(tunis, monture, verre, societe, creer_utilisateur):
    opticien = creer_utilisateur("opticien")
    devis = etablir_devis(
        magasin=tunis,
        auteur=opticien,
        client=societe,
        lignes=[{"article": monture, "quantite": 1}, {"article": verre, "quantite": 2}],
    )
    vente = encaisser_devis(
        devis=devis, vendeur=opticien, paiements=especes("300.000"), commande=True
    )
    assert (vente.statut, vente.client, vente.reste_a_payer) == (
        Vente.Statut.EN_COMMANDE,
        societe,
        Decimal("349.500"),
    )


def test_pas_de_stock_pour_un_article_sur_commande(tunis, verre, affecter, client_de):
    logisticien = affecter(
        "logisticien", "stock.add_mouvementstock", portee="magasin", magasin=tunis
    )
    reponse = client_de(logisticien).post(
        "/api/v1/mouvements-stock/",
        {
            "magasin": str(tunis.public_id),
            "article": str(verre.public_id),
            "quantite": 5,
            "type": "reception",
        },
        format="json",
    )
    assert reponse.status_code == 400
    assert "article" in reponse.json()


def test_parcours_commande_par_l_api(tunis, monture, verre, reseau, affecter, client_de):
    vendeur = affecter(
        "vendeur",
        "ventes.add_vente",
        "ventes.view_vente",
        "stock.view_article",
        portee="magasin",
        magasin=tunis,
    )
    api = client_de(vendeur)
    corps = {
        "magasin": str(tunis.public_id),
        "lignes": [
            {"article": str(monture.public_id), "quantite": 1},
            {"article": str(verre.public_id), "quantite": 2},
        ],
        "paiements": [{"mode": "carte", "montant": "200.000"}],
        "commande": True,
        "livraison_prevue_le": "2026-10-15",
    }
    cree = api.post("/api/v1/ventes/", corps, format="json")
    assert cree.status_code == 201, cree.json()
    vente = cree.json()
    assert (vente["statut"], vente["reste_a_payer"], vente["livraison_prevue_le"]) == (
        "en_commande",
        "449.500",
        "2026-10-15",
    )
    en_cours = api.get("/api/v1/ventes/", {"statut": "en_commande"}).json()
    assert [v["numero"] for v in en_cours["results"]] == [vente["numero"]]

    url = f"/api/v1/ventes/{vente['id']}/"
    reglement = api.post(
        url + "reglement/", {"paiements": [{"mode": "especes", "montant": "49.500"}]}, format="json"
    )
    assert reglement.json()["reste_a_payer"] == "400.000"
    assert api.post(url + "livrer/", {}, format="json").status_code == 400
    livree = api.post(
        url + "livrer/", {"paiements": [{"mode": "carte", "montant": "400.000"}]}, format="json"
    )
    assert livree.status_code == 200, livree.json()
    assert (livree.json()["statut"], livree.json()["reste_a_payer"]) == ("livree", "0.000")

    ailleurs = affecter(
        "lille", "ventes.add_vente", "ventes.view_vente", portee="magasin", magasin=reseau["lille"]
    )
    assert client_de(ailleurs).post(url + "livrer/", {}, format="json").status_code == 404
