"""Recherche des verres (stock fournisseur, prescription, magasin) et plages de puissances."""

from decimal import Decimal

import pytest

from apps.achats.models import Fournisseur
from apps.stock.models import Article, MouvementStock, PlageVerre, PrixArticle, Verre

from .conftest import peniche, tva
from .test_imports import fichier, importer
from .test_imports_modeles import acheteur  # noqa: F401  (fixture)

DROITS_VENTE = ("ventes.view_vente", "ventes.add_vente", "stock.view_article")


@pytest.fixture
def vendeur(affecter, tunis):
    return affecter("vendeur", *DROITS_VENTE, portee="magasin", magasin=tunis)


@pytest.fixture
def tn_optic(tunis):
    return Fournisseur.objects.create(nom="TN OPTIC", pays=tunis.pays)


def creer_verre(tunis, fournisseur, reference, libelle, *, fabrication, sur_commande=True, prix):
    article = Article.objects.create(
        reference=reference,
        libelle=libelle,
        famille="verre",
        fournisseur=fournisseur,
        sur_commande=sur_commande,
    )
    Verre.objects.create(
        article=article, geometrie="unifocal", indice="1.560", fabrication=fabrication
    )
    PrixArticle.objects.create(
        article=article, pays=tunis.pays, prix_vente_ttc=Decimal(prix), tva=tva(tunis.pays, 7)
    )
    return article


def plage(article, tunis, sph, cyl, prix, ordre=1):
    return PlageVerre.objects.create(
        article=article,
        pays=tunis.pays,
        ordre=ordre,
        sphere_debut=Decimal(sph[0]),
        sphere_fin=Decimal(sph[1]),
        cylindre_debut=Decimal(cyl[0]),
        cylindre_fin=Decimal(cyl[1]),
        prix_vente_ttc=Decimal(prix),
    )


@pytest.fixture
def relax(tunis, tn_optic):
    article = creer_verre(
        tunis, tn_optic, "VER-RLX", "RELAX 400 ASP 1.56 BLANC", fabrication="stock", prix="92.859"
    )
    plage(article, tunis, ("-2.75", "4"), ("0", "3"), "92.859", ordre=1)
    plage(article, tunis, ("-4", "0"), ("0", "3"), "98.573", ordre=2)
    return article


def test_trois_listes_et_plages_qui_couvrent_la_correction(
    client_de, vendeur, tunis, tn_optic, relax
):
    creer_verre(
        tunis,
        tn_optic,
        "VER-FTO",
        "F.T.O 450 ORGA-CR 1.50",
        fabrication="prescription",
        prix="173.612",
    )
    solaire = creer_verre(
        tunis,
        tn_optic,
        "VER-GRIS",
        "1.50 GRIS",
        fabrication="prescription",
        sur_commande=False,
        prix="70.000",
    )
    MouvementStock.tous.create(magasin=tunis, article=solaire, quantite=2, type="reception")
    api = client_de(vendeur)

    tout = api.get("/api/v1/articles/recherche-verres/", {"magasin": tunis.public_id}).json()
    assert [(v["designation"], v["prix_vente_ttc"]) for v in tout["stock_fournisseur"]] == [
        ("RELAX 400 ASP 1.56 BLANC", "92.859"),
        ("RELAX 400 ASP 1.56 BLANC", "98.573"),
    ]
    assert [v["designation"] for v in tout["prescription"]] == ["F.T.O 450 ORGA-CR 1.50"]
    assert tout["prescription"][0]["plage"] is None
    assert [(v["designation"], v["quantite"]) for v in tout["magasin"]] == [("1.50 GRIS", 2)]

    # Sphère -3,50 et cylindre -0,75 : seule la deuxième plage du RELAX couvre (cylindre en
    # valeur absolue) ; le verre sans plage reste proposé.
    filtre = api.get(
        "/api/v1/articles/recherche-verres/",
        {"magasin": tunis.public_id, "sphere": "-3,50", "cylindre": "-0.75"},
    ).json()
    assert [v["prix_vente_ttc"] for v in filtre["stock_fournisseur"]] == ["98.573"]
    assert len(filtre["prescription"]) == 1

    par_mot = api.get(
        "/api/v1/articles/recherche-verres/",
        {"magasin": tunis.public_id, "designation": "relax blanc"},
    ).json()
    assert len(par_mot["stock_fournisseur"]) == 2
    assert par_mot["prescription"] == par_mot["magasin"] == []


def test_la_vente_prend_le_prix_de_la_plage(client_de, vendeur, tunis, relax):
    seconde = PlageVerre.objects.get(article=relax, ordre=2)
    ligne = {"article": str(relax.public_id), "quantite": 1, "plage": seconde.pk}
    api = client_de(vendeur)
    reponse = api.post(
        "/api/v1/ventes/",
        {
            "magasin": str(tunis.public_id),
            "commande": True,
            "peniche": peniche(),
            "lignes": [ligne],
            "paiements": [],
        },
        format="json",
    )
    assert reponse.status_code == 201, reponse.json()
    assert reponse.json()["total_ttc"] == "98.573"

    autre = creer_verre(
        tunis, relax.fournisseur, "VER-AUTRE", "Autre verre", fabrication="stock", prix="10.000"
    )
    reponse = api.post(
        "/api/v1/ventes/",
        {
            "magasin": str(tunis.public_id),
            "commande": True,
            "peniche": peniche(),
            "lignes": [{**ligne, "article": str(autre.public_id)}],
            "paiements": [],
        },
        format="json",
    )
    assert reponse.status_code == 400
    assert "plage de puissances" in str(reponse.json())


def test_import_des_verres_avec_leurs_plages(acheteur, tunis, tn_optic):  # noqa: F811
    entete = (
        "reference;libelle;fournisseur;geometrie;indice;fabrication;diametre_commercial;"
        "sphere_debut;sphere_fin;cylindre_debut;cylindre_fin;prix_ttc;tva\n"
    )
    contenu = fichier(
        entete
        + "VER-RLX;RELAX 400 ASP 1.56 BLANC;TN OPTIC;Unifocal;1,56;stock;65;-2,75;4;0;3;92,859;7\n"
        + "VER-RLX;RELAX 400 ASP 1.56 BLANC;TN OPTIC;Unifocal;;;;-4;0;0;3;98,573;7\n"
        + "VER-FTO;F.T.O 450;TN OPTIC;Unifocal;1,5;;65/70;;;;;173,612;7\n"
    )
    reponse = importer(acheteur, contenu, "verres")
    assert reponse.status_code == 200, reponse.json()
    relax = Article.objects.get(reference="VER-RLX")
    assert (relax.verre.fabrication, relax.verre.diametre_commercial) == ("stock", "65")
    assert [(p.ordre, p.sphere_debut, p.prix_vente_ttc) for p in relax.plages.all()] == [
        (1, Decimal("-2.75"), Decimal("92.859")),
        (2, Decimal("-4.00"), Decimal("98.573")),
    ]
    assert relax.prix.get().prix_vente_ttc == Decimal("92.859")
    fto = Article.objects.get(reference="VER-FTO")
    assert (fto.verre.fabrication, fto.plages.count()) == ("prescription", 0)

    # Réimport : les plages du fichier remplacent les anciennes.
    contenu = fichier(entete + "VER-RLX;RELAX;TN OPTIC;Unifocal;;;;-6;6;0;2;110;7\n")
    assert importer(acheteur, contenu, "verres").status_code == 200
    assert [(p.sphere_debut, p.sphere_fin) for p in relax.plages.all()] == [
        (Decimal("-6.00"), Decimal("6.00"))
    ]

    # Une référence répétée sans plage reste une erreur.
    double = fichier(
        entete + "VER-X;X;TN OPTIC;Unifocal;;;;;;;;10;7\nVER-X;X;TN OPTIC;Unifocal;;;;;;;;10;7\n"
    )
    erreurs = importer(acheteur, double, "verres").json()["erreurs"]
    assert erreurs == [{"ligne": 3, "message": "Référence VER-X déjà en ligne 2."}]
