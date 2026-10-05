"""Fiche monture : création, modification, prix d'achat et de vente, stock et mouvements."""

from datetime import date
from decimal import Decimal

import pytest

from apps.achats.models import Fournisseur
from apps.achats.receptions import enregistrer_reception
from apps.stock.api.fiches import cle_ean13
from apps.stock.models import Article, Monture

DROITS = (
    "stock.view_article",
    "stock.add_article",
    "stock.change_article",
    "stock.add_prixarticle",
    "stock.change_prixarticle",
    "stock.view_mouvementstock",
)


@pytest.fixture
def gestionnaire(affecter, tunis):
    return affecter("gestionnaire", *DROITS, portee="magasin", magasin=tunis)


@pytest.fixture
def api(client_de, gestionnaire):
    return client_de(gestionnaire)


@pytest.fixture
def cartier(tunis):
    return Fournisseur.objects.create(nom="Cartier Tunisie", pays=tunis.pays)


def url(tunis, article=None, suite=""):
    base = "/api/v1/fiches-articles/" + (f"{article.public_id}/" if article else "")
    return f"{base}{suite}?magasin={tunis.public_id}"


def fiche(cartier, **autres):
    return {
        "famille": "monture",
        "fournisseur": str(cartier.public_id),
        "reference": "CL.S.40235-30N",
        "reference_fournisseur": "40235",
        "promotion": False,
        "monture": {
            "categorie": "solaire",
            "marque": "Celine",
            "modele": "CL40235",
            "matiere": "acetate",
            "forme": "Papillon",
            "tranche_age": "adulte",
            "couleur": "Noir",
            "couleur_verres": "Gris",
            "calibre": 55,
        },
        "nouveau_prix": {
            "prix_achat_ht": "798.320",
            "taux_remise_achat": "20",
            "taux_tva": "19",
            "prix_vente_ttc": "2500.000",
        },
        **autres,
    }


def test_creation_d_une_fiche_monture(api, tunis, cartier, gestionnaire):
    reponse = api.post(url(tunis), fiche(cartier), format="json")
    assert reponse.status_code == 201, reponse.json()
    donnees = reponse.json()
    article = Article.objects.get(reference="CL.S.40235-30N")
    assert article.cree_par == gestionnaire
    assert donnees["libelle"] == "Celine CL40235 Noir 55"
    # Code monture : EAN-13 interne attribué.
    code = donnees["code_barres"]
    assert len(code) == 13 and code.startswith("2") and code[-1] == cle_ean13(code[:12])
    assert article.monture.solaire  # La vente au comptoir le range en solaire.
    assert donnees["prix"] == {
        "prix_achat_ht": "798.320",
        "taux_remise_achat": "20.00",
        "taux_tva": "19.00",
        "prix_vente_ttc": "2500.000",
    }
    assert donnees["stocks"] == [{"magasin": "Tunis Centre", "stock": 0}]
    assert donnees["stockable"] is True

    # Le code suivant se suit.
    autre = api.post(
        url(tunis), fiche(cartier, reference="", libelle="Autre"), format="json"
    ).json()
    assert autre["reference"] == "MON-000001"
    assert int(autre["code_barres"][:12]) == int(code[:12]) + 1


def test_modification_et_controles(api, tunis, cartier):
    article = api.post(url(tunis), fiche(cartier), format="json").json()
    cible = Article.objects.get(public_id=article["id"])
    reponse = api.patch(
        url(tunis, cible),
        {
            "promotion": True,
            "monture": {"categorie": "optique", "type": ""},
            "nouveau_prix": {"taux_tva": "19", "prix_vente_ttc": "2600"},
        },
        format="json",
    )
    assert reponse.status_code == 200, reponse.json()
    cible.refresh_from_db()
    assert cible.promotion and not cible.monture.solaire
    assert cible.monture.marque == "Celine"  # Les champs non envoyés restent.
    assert reponse.json()["prix"]["prix_achat_ht"] == "798.320"

    erreurs = api.post(
        url(tunis),
        fiche(cartier, code_barres=cible.code_barres, monture={"matiere": "plastique"}),
        format="json",
    ).json()
    assert erreurs["reference"] == [
        "Cette référence est déjà celle d'un autre article (CL.S.40235-30N)."
    ]
    # Même référence en minuscules : refusée aussi.
    minuscules = api.post(url(tunis), fiche(cartier, reference="cl.s.40235-30n"), format="json")
    assert "CL.S.40235-30N" in minuscules.json()["reference"][0]
    assert cible.reference in erreurs["code_barres"][0]
    assert "matiere" in erreurs["monture"]

    taux = api.patch(
        url(tunis, cible), {"nouveau_prix": {"taux_tva": "8", "prix_vente_ttc": "1"}}, format="json"
    )
    assert "Taux du pays" in str(taux.json())


def test_dernier_achat_et_mouvements(api, tunis, cartier, gestionnaire):
    article = Article.objects.get(
        public_id=api.post(url(tunis), fiche(cartier), format="json").json()["id"]
    )
    enregistrer_reception(
        magasin=tunis,
        fournisseur=cartier,
        numero_bl="BL-7",
        date_bl=date(2026, 10, 1),
        lignes=[
            {
                "article": article,
                "quantite": 2,
                "prix_achat_ht": Decimal("800"),
                "taux_remise": Decimal("25"),
                "taux_tva": Decimal("19"),
                "non_conforme": False,
                "motif": "",
            }
        ],
        auteur=gestionnaire,
    )
    donnees = api.get(url(tunis, article)).json()
    assert donnees["dernier_achat"]["net_ht"] == "600.000"
    assert donnees["dernier_achat"]["numero_bl"] == "BL-7"
    assert donnees["stocks"] == [{"magasin": "Tunis Centre", "stock": 2}]
    mouvements = api.get(url(tunis, article, "mouvements/")).json()
    assert [(m["quantite"], m["magasin"]) for m in mouvements] == [(2, "Tunis Centre")]


def test_droits(client_de, affecter, tunis, cartier):
    vendeur = client_de(affecter("vendeur", "stock.view_article", portee="magasin", magasin=tunis))
    assert vendeur.post(url(tunis), fiche(cartier), format="json").status_code == 403


def test_reprise_des_anciennes_montures(db):
    """La migration range l'ancienne case « solaire » et les matières tapées à la main."""
    from importlib import import_module

    from django.apps import apps

    migration = import_module("apps.stock.migrations.0009_fiche_monture")
    article = Article.objects.create(reference="X", libelle="X", famille="monture")
    Monture.objects.create(article=article, matiere="Titanium")
    Monture.objects.filter(pk=article.pk).update(solaire=True, categorie="optique")
    migration.reprendre(apps, None)
    fiche = Monture.objects.get(pk=article.pk)
    assert (fiche.categorie, fiche.matiere) == ("solaire", "titane")


def test_suggestions_des_valeurs_deja_saisies(api, tunis, cartier):
    api.post(url(tunis), fiche(cartier), format="json")
    suggestions = api.get("/api/v1/fiches-articles/suggestions/").json()
    assert suggestions["marque"] == ["Celine"]
    assert suggestions["forme"] == ["Papillon"]


def test_import_refuse_une_reference_en_minuscules(client_de, affecter, tunis, cartier):
    from .test_imports import fichier, importer

    Article.objects.create(reference="CL.S.1", libelle="Celine", famille="monture")
    acheteur = client_de(affecter("acheteur", *DROITS, portee="magasin", magasin=tunis))
    reponse = importer(
        acheteur,
        fichier(f"reference;libelle;famille;fournisseur\ncl.s.1;Celine;Monture;{cartier.code}\n"),
        "catalogue",
    )
    assert "déjà celle de CL.S.1" in reponse.json()["erreurs"][0]["message"]
