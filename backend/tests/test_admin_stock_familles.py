"""Administration du stock rangée par type d'article : Verres, Montures, Lentilles, Produits."""

from django.core.files.uploadedfile import SimpleUploadedFile

from apps.achats.models import Fournisseur
from apps.stock.imports_referentiels import importer_liste
from apps.stock.models import Article, CouleurLentille, Lentille
from tests.test_admin_imports import _admin


def test_sections_par_type(creer_utilisateur, client_de):
    navigateur = _admin(creer_utilisateur, client_de)
    page = navigateur.get("/admin/stock/")
    titres = [app["name"] for app in page.context["app_list"]]
    assert titres == ["Verres", "Montures", "Lentilles", "Produits", "Stock"]
    sections = {
        app["name"]: [m["object_name"] for m in app["models"]] for app in page.context["app_list"]
    }
    assert sections["Lentilles"] == [
        "ArticleLentille",
        "MarqueLentille",
        "CouleurLentille",
        "MatiereLentille",
    ]
    assert sections["Montures"] == ["ArticleMonture", "MarqueMonture"]
    assert "Article" in sections["Stock"] and "Inventaire" in sections["Stock"]
    accueil = navigateur.get("/admin/", {"onglet": "stock"})
    assert "Lentilles" in [app["name"] for app in accueil.context["app_list"]]


def test_liste_et_import_des_lentilles(creer_utilisateur, client_de, tunis):
    Fournisseur.objects.create(nom="SICOM", pays=tunis.pays)
    monture = Article.objects.create(reference="MON-1", libelle="Monture", famille="monture")
    navigateur = _admin(creer_utilisateur, client_de)
    url = "/admin/stock/articlelentille/importer/lentilles/"
    liste = navigateur.get("/admin/stock/articlelentille/").content.decode()
    assert f'href="{url}"' in liste and monture.libelle not in liste

    fichier = SimpleUploadedFile(
        "lentilles.csv",
        b"reference;libelle;fournisseur;prix_ttc;tva;couleur;renouvellement;puissance\n"
        b"LEN-000314;biofinity SPH : -6.00;SICOM;25;19;;Mensuelle;-6\n",
    )
    verification = navigateur.post(url, {"fichier": fichier, "magasin": str(tunis.public_id)})
    assert verification.context["rapport"].crees == 1, verification.context["rapport"].erreurs
    navigateur.post(
        url,
        {"importer": "1", "jeton": verification.context["jeton"], "magasin": str(tunis.public_id)},
    )
    lentille = Lentille.objects.get(article__reference="LEN-000314")
    assert (lentille.article.famille, str(lentille.puissance)) == ("lentille", "-6.00")
    assert "biofinity" in navigateur.get("/admin/stock/articlelentille/").content.decode()
    fiche = navigateur.get(f"/admin/stock/articlelentille/{lentille.article.pk}/change/")
    assert fiche.status_code == 200 and "Renouvellement" in fiche.content.decode()


def test_import_des_couleurs_de_lentille(db):
    rapport = importer_liste(
        "couleurs_lentilles",
        [(2, {"code": "10", "libelle": " pure  hazel "}), (3, {"code": "11", "libelle": "grey"})],
    )
    assert (rapport.crees, rapport.erreurs) == (2, [])
    assert CouleurLentille.objects.get(code="10").libelle == "pure hazel"


def test_ajouter_un_produit(creer_utilisateur, client_de, tunis):
    navigateur = _admin(creer_utilisateur, client_de)
    page = navigateur.get("/admin/stock/articleproduit/add/")
    assert page.status_code == 200
    assert 'name="famille"' not in page.content.decode()
