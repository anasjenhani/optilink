"""Liste des banques : choisie sur les fiches, contrôlée avec le RIB, appliquée aux imports."""

from apps.achats.models import Fournisseur
from apps.reseau.models import Banque

from .test_banque import equipe  # noqa: F401 (fixture)
from .test_imports import fichier, importer
from .test_imports_modeles import acheteur  # noqa: F401 (fixture)
from .test_villes import _admin

COMPTES = "/api/v1/tresorerie/comptes/"
RIB_BIAT = "08 006 0123456789012 34"


def test_la_liste_de_depart_et_l_api(affecter, client_de, tunis):
    assert Banque.objects.filter(pays__code="TN").count() == 20
    assert Banque.objects.get(code="25").sigle == "BZ"
    vendeur = client_de(affecter("vendeur", "crm.view_client", portee="magasin", magasin=tunis))
    sigles = {b["sigle"] for b in vendeur.get("/api/v1/banques/").json()}
    assert {"BIAT", "BZ", "CCP", "WIB"} <= sigles


def test_compte_bancaire_banque_et_rib(tunis, equipe, client_de):  # noqa: F811
    finance = client_de(equipe["finance"])
    corps = {"societe": str(tunis.societe.public_id), "type": "banque", "nom": "Compte BIAT"}
    inconnue = finance.post(COMPTES, {**corps, "banque": "Banque du Coin"}, format="json")
    assert inconnue.status_code == 400 and "liste des banques" in inconnue.json()["banque"][0]
    mauvais_rib = finance.post(COMPTES, {**corps, "banque": "BZ", "rib": RIB_BIAT}, format="json")
    assert mauvais_rib.json()["rib"] == ["Ce RIB est un RIB BIAT, pas BZ."]
    # Le sigle suffit ; et sans banque, le RIB la donne.
    cree = finance.post(COMPTES, {**corps, "banque": "biat", "rib": RIB_BIAT}, format="json")
    assert cree.json()["banque"] == "BANQUE INTERNATIONALE ARABE DE TUNISIE"
    corps["nom"] = "Compte 2"
    cree = finance.post(COMPTES, {**corps, "rib": "25 001 0000000000000 00"}, format="json")
    assert cree.status_code == 201 and cree.json()["banque"] == "BANQUE ZITOUNA"


def test_admin_fournisseur_banque_de_la_liste(creer_utilisateur, client_de, tunis):
    admin = _admin(creer_utilisateur, client_de)
    page = admin.get("/admin/achats/fournisseur/add/").content.decode()
    assert '<datalist id="banques-banque">' in page and ">BIAT</option>" in page
    corps = {"nom": "Opty", "pays": tunis.pays.pk, "regime_tva": "assujetti", "banque": "XYZ"}
    assert (
        "liste des banques" in admin.post("/admin/achats/fournisseur/add/", corps).content.decode()
    )
    reponse = admin.post("/admin/achats/fournisseur/add/", {**corps, "banque": "UBCI"})
    assert reponse.status_code == 302
    assert Fournisseur.objects.get(nom="Opty").banque.startswith("UNION BANCAIRE")


def test_import_fournisseurs_banque(acheteur):  # noqa: F811
    contenu = fichier(f"raison_sociale;banque;rib\nOpty;BIAT;\nBlue;Ma Banque;\nSud;;{RIB_BIAT}\n")
    rapport = importer(acheteur, contenu, "fournisseurs", apercu=True).json()
    assert rapport["crees"] == 3 and len(rapport["alertes"]) == 1
    contenu.seek(0)
    assert importer(acheteur, contenu, "fournisseurs").status_code == 200
    banques = dict(Fournisseur.objects.values_list("nom", "banque"))
    assert banques["Opty"] == banques["Sud"] == "BANQUE INTERNATIONALE ARABE DE TUNISIE"
    assert banques["Blue"] == "Ma Banque"
