"""Liste des villes : choisie sur les fiches, tenue dans /admin/, appliquée aux imports."""

from apps.achats.models import Fournisseur
from apps.reseau.models import Pays, Ville

from .test_imports import fichier, importer
from .test_imports_modeles import acheteur  # noqa: F401 (fixture)

CLIENTS = ("crm.view_client", "crm.add_client", "crm.change_client")


def _admin(creer_utilisateur, client_de):
    anas = creer_utilisateur("anas")
    anas.is_staff = anas.is_superuser = True
    anas.save()
    return client_de(anas)


def test_la_liste_de_depart_et_l_api(affecter, client_de, tunis):
    assert Ville.objects.filter(pays__code="TN").count() == 44
    Ville.objects.filter(nom="Djerba").update(est_active=False)
    vendeur = client_de(affecter("vendeur", "crm.view_client", portee="magasin", magasin=tunis))
    noms = [v["nom"] for v in vendeur.get("/api/v1/villes/", {"pays__code": "TN"}).json()]
    assert {"Ariana", "Aïn Zaghouan", "L'Aouina", "Sfax"} <= set(noms)
    assert "Djerba" not in noms and len(noms) == 43


def test_la_ville_d_un_client_vient_de_la_liste(affecter, client_de, tunis, reseau):
    api = client_de(affecter("vendeur", *CLIENTS, portee="reseau"))
    corps = {"nom": "Ben Salah", "prenom": "Amel", "magasin_origine": str(tunis.public_id)}
    cree = api.post("/api/v1/clients/", {**corps, "ville": "ariena"})
    assert cree.status_code == 400 and "liste des villes" in cree.json()["ville"][0]
    cree = api.post("/api/v1/clients/", {**corps, "ville": "  l aouina "})
    assert cree.status_code == 201 and cree.json()["ville"] == "L'Aouina"
    # Pas de liste pour la France : la ville reste libre.
    lille = {
        "nom": "Durand",
        "prenom": "Paul",
        "ville": "Lille",
        "magasin_origine": str(reseau["lille"].public_id),
    }
    assert api.post("/api/v1/clients/", lille).status_code == 201


def test_admin_fournisseur_ville_de_la_liste(creer_utilisateur, client_de, tunis):
    admin = _admin(creer_utilisateur, client_de)
    page = admin.get("/admin/achats/fournisseur/add/").content.decode()
    assert '<datalist id="villes-ville">' in page and '<option value="Sfax">' in page
    corps = {"nom": "Opty", "pays": tunis.pays.pk, "regime_tva": "assujetti", "ville": "Atlantis"}
    reponse = admin.post("/admin/achats/fournisseur/add/", corps)
    assert "liste des villes" in reponse.content.decode()
    reponse = admin.post("/admin/achats/fournisseur/add/", {**corps, "ville": "SFAX"})
    assert reponse.status_code == 302
    assert Fournisseur.objects.get(nom="Opty").ville == "Sfax"

    # Une ville ajoutée dans Réseau › Villes est aussitôt proposée.
    france = Pays.objects.get(code="FR")
    reponse = admin.post(
        "/admin/reseau/ville/add/", {"nom": "Paris", "pays": france.pk, "est_active": "on"}
    )
    assert reponse.status_code == 302
    assert '<option value="Paris">' in admin.get("/admin/achats/fournisseur/add/").content.decode()


def test_import_corrige_la_ville_ou_alerte(acheteur):  # noqa: F811
    contenu = fichier("raison_sociale;ville\nOpty;sfax\nBlue Optical;Atlantis\n")
    rapport = importer(acheteur, contenu, "fournisseurs", apercu=True).json()
    assert rapport["crees"] == 2 and not rapport["erreurs"]
    assert "Atlantis" in rapport["alertes"][0]["message"]
    contenu.seek(0)
    assert importer(acheteur, contenu, "fournisseurs").status_code == 200
    assert Fournisseur.objects.get(nom="Opty").ville == "Sfax"
    assert Fournisseur.objects.get(nom="Blue Optical").ville == "Atlantis"
