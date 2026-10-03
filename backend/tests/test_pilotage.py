"""Alertes du jour et reporting des ventes, chacun dans son périmètre."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.rh.models import Employe
from apps.stock.models import Article, MouvementStock, PrixArticle
from apps.ventes.models import Vente
from apps.ventes.services import enregistrer_vente
from tests.conftest import tva


@pytest.fixture
def articles(reseau):
    france = reseau["lille"].pays
    monture = Article.objects.create(reference="MON-1", libelle="Monture", famille="monture")
    lentilles = Article.objects.create(reference="LEN-1", libelle="Lentilles", famille="lentille")
    for article, prix in ((monture, "149.00"), (lentilles, "30.00")):
        PrixArticle.objects.create(
            article=article, pays=france, prix_vente_ttc=Decimal(prix), tva=tva(france, 20)
        )
        for magasin in (reseau["lille"], reseau["arras"]):
            MouvementStock.tous.create(
                magasin=magasin, article=article, quantite=3, type="reception"
            )
    return {"monture": monture, "lentilles": lentilles}


def vendre(magasin, vendeur, article, quantite, montant):
    return enregistrer_vente(
        magasin=magasin,
        vendeur=vendeur,
        lignes=[{"article": article, "quantite": quantite}],
        paiements=[{"mode": "carte", "montant": Decimal(montant)}],
    )


def test_alertes_selon_droits_et_magasins(affecter, client_de, reseau, articles):
    vendeur = affecter(
        "vendeur",
        "ventes.view_vente",
        "stock.view_article",
        portee="magasin",
        magasin=reseau["lille"],
    )
    # Lille : il reste 1 monture (seuil 1) ; Arras, hors périmètre, aussi.
    vendre(reseau["lille"], vendeur, articles["monture"], 2, "298.00")
    vendre(reseau["arras"], vendeur, articles["monture"], 2, "298.00")
    commande = vendre(reseau["lille"], vendeur, articles["lentilles"], 1, "30.00")
    Vente.tous.filter(pk=commande.pk).update(
        statut="en_commande", livraison_prevue_le=timezone.localdate() - timedelta(days=2)
    )
    employe = Employe.objects.create(
        magasin=reseau["lille"], nom="Ben", prenom="Sami", date_embauche="2025-01-01"
    )
    employe.conges.create(
        magasin=reseau["lille"],
        type="annuel",
        debut="2026-11-02",
        fin="2026-11-03",
        jours=2,
        demandee_par=vendeur,
    )

    reponse = client_de(vendeur).get("/api/v1/pilotage/alertes/")
    assert reponse.status_code == 200
    alertes = [(a["code"], a["magasin"], a["nombre"]) for a in reponse.json()]
    assert alertes == [
        ("commandes_en_retard", "Lille", 1),
        ("stock_faible", "Lille", 1),
    ]
    stock = reponse.json()[1]
    assert "Monture" in stock["detail"] and (stock["module"], stock["ecran"]) == (
        "stock",
        "stock-monture",
    )

    rh = affecter("rh", "rh.decider_demandeconge", portee="reseau")
    codes = [a["code"] for a in client_de(rh).get("/api/v1/pilotage/alertes/").json()]
    assert codes == ["conges_a_decider"]


def test_reporting_du_perimetre(affecter, client_de, reseau, articles):
    responsable = affecter(
        "resp", "ventes.consulter_reporting", portee="magasin", magasin=reseau["lille"]
    )
    vendeur = affecter("v", "ventes.add_vente", portee="reseau")
    vendre(reseau["lille"], vendeur, articles["monture"], 1, "149.00")
    vendre(reseau["lille"], responsable, articles["lentilles"], 2, "60.00")
    vendre(reseau["arras"], vendeur, articles["monture"], 1, "149.00")

    reponse = client_de(responsable).get("/api/v1/pilotage/reporting/")
    assert reponse.status_code == 200
    [section] = reponse.json()
    assert section["devise"] == "EUR"
    assert (section["ca_ttc"], section["nombre_ventes"], section["panier_moyen"]) == (
        "209.000",
        2,
        "104.500",
    )
    assert [m["magasin"] for m in section["par_magasin"]] == ["Lille"]
    assert [(f["famille"], f["quantite"]) for f in section["par_famille"]] == [
        ("Monture", 1),
        ("Lentille", 2),
    ]
    assert section["encaissements"] == [{"mode": "Carte bancaire", "montant": "209.000"}]
    assert len(section["par_vendeur"]) == 2

    hier = (timezone.localdate() - timedelta(days=1)).isoformat()
    vide = client_de(responsable).get("/api/v1/pilotage/reporting/", {"du": hier, "au": hier})
    assert vide.json()[0]["nombre_ventes"] == 0

    sans_droit = affecter("x", "ventes.view_vente", portee="reseau")
    assert client_de(sans_droit).get("/api/v1/pilotage/reporting/").status_code == 403
