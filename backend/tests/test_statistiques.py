"""Statistiques des ventes : marques, remises, gratuits, TVA, bénéfice journalier."""

from decimal import Decimal

import pytest

from apps.stock.models import Monture, PrixArticle

URL = "/api/v1/statistiques/"


@pytest.fixture
def responsable(affecter, tunis):
    return affecter(
        "responsable",
        "ventes.view_vente",
        "ventes.add_vente",
        "ventes.appliquer_remise",
        "ventes.consulter_reporting",
        portee="magasin",
        magasin=tunis,
    )


def test_statistiques_des_ventes(affecter, client_de, responsable, tunis, monture):
    Monture.objects.create(article=monture, marque="Ray-Ban", categorie="solaire")
    PrixArticle.objects.filter(article=monture).update(prix_achat_ht=Decimal("100.000"))
    api = client_de(responsable)
    for remise, paye in (("10", "260.550"), ("100", None)):
        reponse = api.post(
            "/api/v1/ventes/",
            {
                "magasin": str(tunis.public_id),
                "lignes": [
                    {"article": str(monture.public_id), "quantite": 1, "remise_pct": remise}
                ],
                "paiements": [{"mode": "especes", "montant": paye}] if paye else [],
            },
            format="json",
        )
        assert reponse.status_code == 201, reponse.json()

    def stat(rapport):
        reponse = api.get(f"{URL}{rapport}/")
        assert reponse.status_code == 200, reponse.json()
        return reponse.json()

    montures = stat("montures")
    assert montures["devise"] == "TND"
    assert [(m["marque"], m["quantite"], m["ca_ttc"]) for m in montures["lignes"]] == [
        ("Ray-Ban", 2, "260.550")
    ]
    remises = stat("remises")["lignes"]
    assert [(r["lignes"], r["remise"]) for r in remises] == [(2, "318.450")]
    gratuits = stat("gratuits")["lignes"]
    assert [(g["article"], g["quantite"], g["valeur"]) for g in gratuits] == [
        ("Monture", 1, "289.500")
    ]
    tva = stat("tva")["lignes"]
    assert [(t["taux"], t["base_ht"], t["tva"]) for t in tva] == [("19 %", "218.950", "41.600")]
    benefice = stat("benefice")
    assert [(b["ca_ht"], b["cout"], b["benefice"]) for b in benefice["lignes"]] == [
        ("218.950", "200.000", "18.950")
    ]
    assert benefice["totaux"]["marge"] == "8.65"
    assert stat("ophtalmologues")["lignes"] == []

    assert api.get(f"{URL}inconnu/").status_code == 404
    vendeur = affecter("vendeur", "ventes.view_vente", portee="magasin", magasin=tunis)
    assert client_de(vendeur).get(f"{URL}tva/").status_code == 403
