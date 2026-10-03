"""Alertes et reporting dans l'administration du serveur, chacun dans son périmètre."""

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


def staff(utilisateur):
    utilisateur.is_staff = True
    utilisateur.save()
    return utilisateur


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

    reponse = client_de(staff(vendeur)).get("/admin/pilotage/alerte/")
    assert reponse.status_code == 200
    alertes = [(a["code"], a["magasin"], a["nombre"]) for a in reponse.context["alertes"]]
    assert alertes == [
        ("commandes_en_retard", "Lille", 1),
        ("stock_faible", "Lille", 1),
    ]
    assert "Monture" in reponse.context["alertes"][1]["detail"]
    assert reponse.context["alertes"][0]["lien"] == "/admin/ventes/vente/"
    assert "Commandes en retard" in reponse.content.decode()

    rh = staff(affecter("rh", "rh.decider_demandeconge", portee="reseau"))
    codes = [a["code"] for a in client_de(rh).get("/admin/pilotage/alerte/").context["alertes"]]
    assert codes == ["conges_a_decider"]

    # Hors de l'administration (compte non « équipe »), pas d'accès.
    assert (
        client_de(affecter("v2", "ventes.view_vente", portee="reseau"))
        .get("/admin/pilotage/alerte/")
        .status_code
        == 302
    )


def test_reporting_du_perimetre(affecter, client_de, reseau, articles):
    responsable = affecter(
        "resp", "ventes.consulter_reporting", portee="magasin", magasin=reseau["lille"]
    )
    vendeur = affecter("v", "ventes.add_vente", portee="reseau")
    vendre(reseau["lille"], vendeur, articles["monture"], 1, "149.00")
    vendre(reseau["lille"], responsable, articles["lentilles"], 2, "60.00")
    vendre(reseau["arras"], vendeur, articles["monture"], 1, "149.00")

    navigateur = client_de(staff(responsable))
    reponse = navigateur.get("/admin/pilotage/reporting/")
    assert reponse.status_code == 200
    [section] = reponse.context["sections"]
    assert section["devise"] == "EUR"
    assert (section["ca_ttc"], section["nombre_ventes"], section["panier_moyen"]) == (
        Decimal("209.000"),
        2,
        Decimal("104.500"),
    )
    assert [m["magasin"] for m in section["par_magasin"]] == ["Lille"]
    assert [(f["famille"], f["quantite"]) for f in section["par_famille"]] == [
        ("Monture", 1),
        ("Lentille", 2),
    ]
    assert section["encaissements"] == [{"mode": "Carte bancaire", "montant": Decimal("209.000")}]
    assert len(section["par_vendeur"]) == 2

    hier = (timezone.localdate() - timedelta(days=1)).isoformat()
    vide = navigateur.get("/admin/pilotage/reporting/", {"du": hier, "au": hier})
    assert vide.context["sections"][0]["nombre_ventes"] == 0

    export = navigateur.get("/admin/pilotage/reporting/", {"format": "csv"})
    assert export["Content-Type"].startswith("text/csv")
    assert "Chiffre d'affaires TTC;209,000" in export.content.decode("utf-8-sig")

    sans_droit = staff(affecter("x", "ventes.view_vente", portee="reseau"))
    assert client_de(sans_droit).get("/admin/pilotage/reporting/").status_code == 403
