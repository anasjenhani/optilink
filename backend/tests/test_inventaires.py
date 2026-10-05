"""Inventaire : comptage du stock d'un magasin, écarts, correction du stock à la validation."""

import pytest

from apps.achats.models import Fournisseur
from apps.stock.inventaires import (
    InventaireImpossible,
    compter,
    etat,
    ouvrir_inventaire,
    trouver_article,
    valider_inventaire,
)
from apps.stock.models import Article, Inventaire, Monture, MouvementStock, stock_disponible


@pytest.fixture
def etui(tunis):
    article = Article.objects.create(
        reference="ETUI", libelle="Étui", famille="divers", code_barres="6190000000017"
    )
    MouvementStock.tous.create(magasin=tunis, article=article, quantite=5, type="reception")
    return article


@pytest.fixture
def auteur(creer_utilisateur):
    return creer_utilisateur("stock")


def test_valider_corrige_le_stock_et_compte_zero_les_absents(tunis, monture, etui, auteur):
    inventaire = ouvrir_inventaire(magasin=tunis, auteur=auteur)
    assert inventaire.numero.startswith("T01-IN")
    with pytest.raises(InventaireImpossible, match="déjà en cours dans ce magasin"):
        ouvrir_inventaire(magasin=tunis, auteur=auteur, famille="monture")

    # Scan de l'étui deux fois, monture non comptée.
    compter(inventaire, trouver_article("6190000000017"), quantite=1)
    compter(inventaire, trouver_article("etui"), quantite=1)
    lignes = {x["article"].reference: x for x in etat(inventaire)}
    assert (lignes["ETUI"]["quantite_comptee"], lignes["ETUI"]["ecart"]) == (2, -3)
    assert (lignes["MON-T"]["comptee"], lignes["MON-T"]["ecart"]) == (False, -3)

    compter(inventaire, etui, quantite=6, remplacer=True)
    valider_inventaire(inventaire, auteur=auteur)
    assert (stock_disponible(tunis, etui), stock_disponible(tunis, monture)) == (6, 0)
    ajustements = MouvementStock.tous.filter(type="ajustement", reference=inventaire.numero)
    assert sorted(ajustements.values_list("quantite", flat=True)) == [-3, 1]

    inventaire.refresh_from_db()
    assert inventaire.statut == Inventaire.Statut.VALIDE
    figees = {x.article.reference: (x.stock_theorique, x.ecart) for x in inventaire.lignes.all()}
    assert figees == {"ETUI": (5, 1), "MON-T": (3, -3)}
    with pytest.raises(InventaireImpossible, match="validé"):
        compter(inventaire, etui, quantite=1)


def test_inventaire_d_une_famille(tunis, monture, etui, auteur):
    inventaire = ouvrir_inventaire(magasin=tunis, auteur=auteur, famille="monture")
    with pytest.raises(InventaireImpossible, match="n'entre pas dans cet inventaire \\(Monture\\)"):
        compter(inventaire, etui, quantite=1)
    assert [x["article"] for x in etat(inventaire)] == [monture]
    compter(inventaire, monture, quantite=3)
    valider_inventaire(inventaire, auteur=auteur)
    assert not MouvementStock.tous.filter(type="ajustement").exists()
    assert stock_disponible(tunis, etui) == 5


def test_inventaire_par_marque_nature_et_fournisseur(tunis, monture, auteur):
    luxottica = Fournisseur.objects.create(nom="Luxottica", pays=tunis.pays)
    Monture.objects.create(article=monture, marque="Ray-Ban", categorie="solaire")
    autre = Article.objects.create(
        reference="MON-2", libelle="Oakley", famille="monture", fournisseur=luxottica
    )
    Monture.objects.create(article=autre, marque="Oakley", categorie="solaire")
    MouvementStock.tous.create(magasin=tunis, article=autre, quantite=2, type="reception")

    inventaire = ouvrir_inventaire(magasin=tunis, auteur=auteur, marque="ray-ban ")
    assert (inventaire.famille, inventaire.marque) == ("monture", "ray-ban")
    assert [x["article"] for x in etat(inventaire)] == [monture]
    with pytest.raises(InventaireImpossible, match="Monture · ray-ban"):
        compter(inventaire, autre, quantite=1)
    inventaire.statut = Inventaire.Statut.ANNULE
    inventaire.save()

    solaires = ouvrir_inventaire(magasin=tunis, auteur=auteur, nature="solaire")
    assert len(etat(solaires)) == 2
    solaires.statut = Inventaire.Statut.ANNULE
    solaires.save()
    chez_luxottica = ouvrir_inventaire(magasin=tunis, auteur=auteur, fournisseur=luxottica)
    assert [x["article"] for x in etat(chez_luxottica)] == [autre]
    with pytest.raises(InventaireImpossible, match="concernent les montures"):
        ouvrir_inventaire(magasin=tunis, auteur=auteur, famille="divers", marque="X")


def test_api_inventaire(tunis, reseau, monture, etui, affecter, client_de):
    vendeur = affecter(
        "vendeur",
        "stock.view_inventaire",
        "stock.change_inventaire",
        portee="magasin",
        magasin=tunis,
    )
    responsable = affecter(
        "resp",
        "stock.view_inventaire",
        "stock.add_inventaire",
        "stock.change_inventaire",
        "stock.valider_inventaire",
        "reseau.view_magasin",
        portee="magasin",
        magasin=tunis,
    )
    resp = client_de(responsable)
    assert (
        client_de(vendeur)
        .post("/api/v1/inventaires/", {"magasin": str(tunis.public_id)}, format="json")
        .status_code
        == 403
    )
    reponse = resp.post(
        "/api/v1/inventaires/",
        {"magasin": str(tunis.public_id), "famille": "divers"},
        format="json",
    )
    assert reponse.status_code == 201, reponse.json()
    inventaire = reponse.json()
    assert inventaire["perimetre"] == "Divers"
    assert resp.get("/api/v1/inventaires/choix/").json()["marques"] == []
    assert [(x["reference"], x["comptee"], x["ecart"]) for x in inventaire["lignes"]] == [
        ("ETUI", False, -5)
    ]

    vend = client_de(vendeur)
    url = f"/api/v1/inventaires/{inventaire['id']}/"
    compte = vend.post(
        url + "compter/",
        {"code": "6190000000017", "quantite": 4, "observation": "1 abîmé"},
        format="json",
    )
    assert compte.status_code == 200, compte.json()
    assert (compte.json()["lignes"][0]["ecart"], compte.json()["lignes"][0]["observation"]) == (
        -1,
        "1 abîmé",
    )
    inconnu = vend.post(url + "compter/", {"code": "XYZ"}, format="json")
    assert inconnu.status_code == 400 and "XYZ" in inconnu.json()["detail"]
    assert vend.post(url + "valider/").status_code == 403

    valide = resp.post(url + "valider/")
    assert valide.status_code == 200 and valide.json()["statut"] == "valide"
    assert stock_disponible(tunis, etui) == 4
    liste = resp.get("/api/v1/inventaires/", {"statut": "valide"}).json()
    assert [(i["numero"], i["articles_comptes"]) for i in liste["results"]] == [
        (inventaire["numero"], 1)
    ]

    ailleurs = affecter("lille", "stock.view_inventaire", portee="magasin", magasin=reseau["lille"])
    assert client_de(ailleurs).get("/api/v1/inventaires/").json()["count"] == 0
    assert client_de(ailleurs).get(url).status_code == 404
