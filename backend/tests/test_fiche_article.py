"""Fiche des verres, lentilles et articles divers : création, modification, désactivation."""

import pytest

from apps.achats.models import Fournisseur
from apps.stock.models import Article

from .test_fiche_monture import DROITS, url


@pytest.fixture
def api(client_de, affecter, tunis):
    return client_de(affecter("gestionnaire", *DROITS, portee="magasin", magasin=tunis))


@pytest.fixture
def essilor(tunis):
    return Fournisseur.objects.create(nom="Essilor Tunisie", pays=tunis.pays)


def prix(vente="320.000"):
    return {
        "prix_achat_ht": "150",
        "taux_remise_achat": "10",
        "taux_tva": "19",
        "prix_vente_ttc": vente,
    }


def test_creation_et_modification_d_un_verre(api, tunis, essilor):
    reponse = api.post(
        url(tunis),
        {
            "famille": "verre",
            "fournisseur": str(essilor.public_id),
            "stockable": False,
            "verre": {
                "marque": "Essilor",
                "gamme": "Varilux Comfort",
                "geometrie": "progressif",
                "indice": "1.6",
                "matiere": "organique",
                "traitements": "Crizal",
                "diametre": 70,
            },
            "nouveau_prix": prix(),
        },
        format="json",
    )
    assert reponse.status_code == 201, reponse.json()
    donnees = reponse.json()
    assert donnees["reference"] == "VER-000001"
    assert donnees["libelle"] == "Essilor Varilux Comfort Progressif 1.6 Crizal"
    assert donnees["code_barres"] == ""  # Le code interne ne va qu'aux montures.
    assert donnees["stockable"] is False
    assert donnees["verre"]["indice"] == "1.600"
    assert donnees["lentille"] is None and donnees["monture"] is None
    assert donnees["prix"]["prix_vente_ttc"] == "320.000"

    article = Article.objects.get(public_id=donnees["id"])
    modifie = api.patch(
        url(tunis, article),
        {"est_actif": False, "verre": {"photochromique": True}, "nouveau_prix": prix("350")},
        format="json",
    )
    assert modifie.status_code == 200, modifie.json()
    article.refresh_from_db()
    assert not article.est_actif  # Désactivé, jamais supprimé.
    assert article.verre.photochromique and article.verre.gamme == "Varilux Comfort"
    assert modifie.json()["prix"]["prix_vente_ttc"] == "350.000"
    # Désactivé : hors du catalogue, mais on le retrouve pour le réactiver.
    actifs = api.get("/api/v1/articles/", {"famille": "verre"}).json()["results"]
    desactives = api.get("/api/v1/articles/", {"famille": "verre", "desactives": "true"})
    assert actifs == [] and [a["id"] for a in desactives.json()["results"]] == [donnees["id"]]


def test_creation_d_une_lentille_et_d_un_article_divers(api, tunis, essilor):
    lentille = api.post(
        url(tunis),
        {
            "famille": "lentille",
            "fournisseur": str(essilor.public_id),
            "code_barres": "3600000000001",
            "lentille": {
                "marque": "Acuvue",
                "modele": "Oasys",
                "renouvellement": "bimensuelle",
                "type": "torique",
                "rayon": "8.6",
                "puissance": "-3.25",
                "cylindre": "-0.75",
                "axe": 180,
                "lentilles_par_boite": 6,
            },
        },
        format="json",
    )
    assert lentille.status_code == 201, lentille.json()
    assert lentille.json()["libelle"] == "Acuvue Oasys Bimensuelle"
    assert lentille.json()["lentille"]["puissance"] == "-3.25"

    divers = api.post(
        url(tunis),
        {
            "famille": "divers",
            "fournisseur": str(essilor.public_id),
            "libelle": "Spray nettoyant 30 ml",
            "code_barres": "3600000000001",
        },
        format="json",
    )
    assert "LEN-000001" in divers.json()["code_barres"][0]  # Code-barres déjà pris.
    divers = api.post(
        url(tunis),
        {"famille": "divers", "fournisseur": str(essilor.public_id), "libelle": "Spray 30 ml"},
        format="json",
    )
    assert divers.status_code == 201, divers.json()
    assert divers.json()["reference"] == "ART-000001"


def test_controles_des_caracteristiques(api, tunis, essilor):
    base = {"fournisseur": str(essilor.public_id)}
    sans_geometrie = api.post(url(tunis), {**base, "famille": "verre"}, format="json")
    assert "geometrie" in sans_geometrie.json()["verre"]
    mauvais = api.post(
        url(tunis),
        {**base, "famille": "lentille", "lentille": {"renouvellement": "mensuelle", "axe": 200}},
        format="json",
    )
    assert "axe" in mauvais.json()["lentille"]
    croise = api.post(
        url(tunis),
        {**base, "famille": "divers", "verre": {"geometrie": "unifocal"}},
        format="json",
    )
    assert "verre" in croise.json()
    assert not Article.objects.exists()
