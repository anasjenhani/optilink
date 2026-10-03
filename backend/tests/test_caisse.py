from decimal import Decimal

import pytest

from apps.securite.models import Affectation
from apps.stock.models import Article, MouvementStock, PrixArticle, stock_disponible
from apps.ventes.models import Vente
from apps.ventes.services import VenteInvalide, enregistrer_vente
from tests.conftest import tva


@pytest.fixture
def articles(reseau):
    france = reseau["lille"].pays
    monture = Article.objects.create(reference="MON-1", libelle="Monture", famille="monture")
    lentilles = Article.objects.create(reference="LEN-1", libelle="Lentilles", famille="lentille")
    PrixArticle.objects.create(
        article=monture, pays=france, prix_vente_ttc=Decimal("149.00"), tva=tva(france, 20)
    )
    PrixArticle.objects.create(
        article=lentilles, pays=france, prix_vente_ttc=Decimal("32.90"), tva=tva(france, "5.50")
    )
    for magasin in (reseau["lille"], reseau["arras"]):
        for article in (monture, lentilles):
            MouvementStock.tous.create(
                magasin=magasin, article=article, quantite=5, type="reception"
            )
    return {"monture": monture, "lentilles": lentilles}


VENDRE = ("ventes.add_vente", "ventes.view_vente", "stock.view_article")


def corps_vente(magasin, *lignes, paiements):
    return {
        "magasin": str(magasin.public_id),
        "lignes": [
            {"article": str(article.public_id), "quantite": quantite, "remise_pct": remise}
            for article, quantite, remise in lignes
        ],
        "paiements": [{"mode": mode, "montant": montant} for mode, montant in paiements],
    }


# Service


def test_vente_complete(reseau, articles, creer_utilisateur):
    lille = reseau["lille"]
    vente = enregistrer_vente(
        magasin=lille,
        vendeur=creer_utilisateur("v"),
        lignes=[
            {"article": articles["monture"], "quantite": 1},
            {"article": articles["lentilles"], "quantite": 2, "remise_pct": Decimal("10")},
        ],
        paiements=[
            {"mode": "carte", "montant": Decimal("150.00")},
            {"mode": "especes", "montant": Decimal("58.22")},
        ],
    )

    assert vente.numero.startswith("M01-") and vente.numero.endswith("-000001")
    assert vente.total_ttc == Decimal("208.22")  # 149.00 + 2 × 32.90 × 0,9
    assert vente.total_ht == Decimal("124.17") + Decimal("56.13")
    assert vente.total_tva == vente.total_ttc - vente.total_ht
    assert stock_disponible(lille, articles["monture"]) == 4
    assert stock_disponible(lille, articles["lentilles"]) == 3
    assert stock_disponible(reseau["arras"], articles["monture"]) == 5


def test_numerotation_continue_par_magasin(reseau, articles, creer_utilisateur):
    vendeur = creer_utilisateur("v")

    def vendre(magasin):
        return enregistrer_vente(
            magasin=magasin,
            vendeur=vendeur,
            lignes=[{"article": articles["lentilles"], "quantite": 1}],
            paiements=[{"mode": "carte", "montant": Decimal("32.90")}],
        ).sequence

    assert [vendre(reseau["lille"]), vendre(reseau["lille"]), vendre(reseau["arras"])] == [1, 2, 1]


def test_vente_refusee_ne_laisse_ni_trou_ni_trace(reseau, articles, creer_utilisateur):
    vendeur = creer_utilisateur("v")
    lille = reseau["lille"]
    with pytest.raises(VenteInvalide, match="ne couvrent pas"):
        enregistrer_vente(
            magasin=lille,
            vendeur=vendeur,
            lignes=[{"article": articles["monture"], "quantite": 1}],
            paiements=[{"mode": "carte", "montant": Decimal("100.00")}],
        )
    assert not Vente.tous.exists()
    assert stock_disponible(lille, articles["monture"]) == 5

    vente = enregistrer_vente(
        magasin=lille,
        vendeur=vendeur,
        lignes=[{"article": articles["monture"], "quantite": 1}],
        paiements=[{"mode": "carte", "montant": Decimal("149.00")}],
    )
    assert vente.sequence == 1


def test_stock_insuffisant(reseau, articles, creer_utilisateur):
    with pytest.raises(VenteInvalide, match="Stock insuffisant"):
        enregistrer_vente(
            magasin=reseau["lille"],
            vendeur=creer_utilisateur("v"),
            lignes=[
                {"article": articles["monture"], "quantite": 3},
                {"article": articles["monture"], "quantite": 3},
            ],
            paiements=[{"mode": "carte", "montant": Decimal("894.00")}],
        )


# API


def test_caisse_par_l_api(reseau, articles, affecter, client_de):
    vendeur = affecter("vendeur", *VENDRE, portee="magasin", magasin=reseau["lille"])
    client = client_de(vendeur)

    catalogue = client.get(f"/api/v1/articles/?magasin={reseau['lille'].public_id}&recherche=mon")
    assert [(a["reference"], a["stock"]) for a in catalogue.json()["results"]] == [("MON-1", 5)]

    reponse = client.post(
        "/api/v1/ventes/",
        corps_vente(reseau["lille"], (articles["monture"], 2, 0), paiements=[("carte", "298.00")]),
        format="json",
    )
    assert reponse.status_code == 201, reponse.json()
    assert reponse.json()["total_ttc"] == "298.000"
    assert reponse.json()["lignes"][0]["libelle"] == "Monture"
    assert client.get("/api/v1/ventes/").json()["count"] == 1


def test_vente_hors_perimetre_refusee(reseau, articles, affecter, client_de):
    vendeur = affecter("vendeur", *VENDRE, portee="magasin", magasin=reseau["lille"])
    reponse = client_de(vendeur).post(
        "/api/v1/ventes/",
        corps_vente(reseau["arras"], (articles["monture"], 1, 0), paiements=[("carte", "149")]),
        format="json",
    )
    assert reponse.status_code == 400
    assert not Vente.tous.exists()


def test_droit_de_vente_verifie_par_magasin(reseau, articles, affecter, client_de):
    utilisateur = affecter("mixte", *VENDRE, portee="magasin", magasin=reseau["lille"])
    lecture = affecter("autre", "ventes.view_vente", portee="magasin", magasin=reseau["arras"])
    Affectation.objects.filter(utilisateur=lecture).update(utilisateur=utilisateur)

    reponse = client_de(utilisateur).post(
        "/api/v1/ventes/",
        corps_vente(reseau["arras"], (articles["monture"], 1, 0), paiements=[("carte", "149")]),
        format="json",
    )
    assert reponse.status_code == 403


def test_remise_reservee_aux_roles_autorises(reseau, articles, affecter, client_de):
    lille = reseau["lille"]
    vendeur = affecter("vendeur", *VENDRE, portee="magasin", magasin=lille)
    opticien = affecter(
        "opticien", *VENDRE, "ventes.appliquer_remise", portee="magasin", magasin=lille
    )
    corps = corps_vente(lille, (articles["monture"], 1, "10"), paiements=[("carte", "134.10")])

    assert client_de(vendeur).post("/api/v1/ventes/", corps, format="json").status_code == 403
    assert client_de(opticien).post("/api/v1/ventes/", corps, format="json").status_code == 201


def test_erreur_metier_renvoyee_lisiblement(reseau, articles, affecter, client_de):
    vendeur = affecter("vendeur", *VENDRE, portee="magasin", magasin=reseau["lille"])
    reponse = client_de(vendeur).post(
        "/api/v1/ventes/",
        corps_vente(reseau["lille"], (articles["monture"], 9, 0), paiements=[("carte", "1341")]),
        format="json",
    )
    assert reponse.status_code == 400
    assert reponse.json() == {"detail": "Stock insuffisant pour MON-1."}


def test_reception_de_stock(reseau, articles, affecter, client_de):
    logisticien = affecter(
        "logisticien",
        "stock.add_mouvementstock",
        "stock.view_mouvementstock",
        portee="magasin",
        magasin=reseau["lille"],
    )
    reponse = client_de(logisticien).post(
        "/api/v1/mouvements-stock/",
        {
            "magasin": str(reseau["lille"].public_id),
            "article": str(articles["monture"].public_id),
            "quantite": 3,
            "type": "reception",
            "reference": "BL-42",
        },
        format="json",
    )
    assert reponse.status_code == 201, reponse.json()
    assert stock_disponible(reseau["lille"], articles["monture"]) == 8


def test_roles_de_depart_ont_les_droits_caisse(db):
    from django.contrib.auth.models import Group

    def perms(nom):
        role = Group.objects.get(name=nom)
        return {f"{p.content_type.app_label}.{p.codename}" for p in role.permissions.all()}

    assert {"ventes.add_vente", "stock.view_article"} <= perms("Vendeur")
    assert "ventes.appliquer_remise" not in perms("Vendeur")
    assert "ventes.appliquer_remise" in perms("Opticien")
    assert "ventes.add_vente" not in perms("Comptabilité & Finance")
    assert not any(p.startswith(("ventes.", "stock.")) for p in perms("Administrateur"))
