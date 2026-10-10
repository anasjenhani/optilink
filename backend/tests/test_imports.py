"""Import du catalogue et des entrées de stock depuis Excel ou CSV : tout ou rien."""

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import Workbook

from apps.achats.models import Fournisseur
from apps.stock.api.serializers import decrire
from apps.stock.models import Article, MouvementStock, PrixArticle, stock_disponible

DROITS_CATALOGUE = (
    "stock.add_article",
    "stock.change_article",
    "stock.add_prixarticle",
    "stock.change_prixarticle",
)

ENTETES = (
    "Référence;Libellé;Famille;Fournisseur;Code-barres;Prix TTC;TVA;Marque;Modèle;Couleur;"
    "Calibre;Pont;Branche;Type;Géométrie;Indice;Renouvellement;Lentilles par boîte"
)
CATALOGUE = "\n".join(
    [
        ENTETES,
        "MON-1;Monture Ray-Ban RB5154;Monture;Luxottica Tunisie;8053672000001;489,000;19;"
        "Ray-Ban;RB5154;écaille;51;21;145;Cerclée;;;;",
        "VER-1;Verre progressif 1.6;verre;essilor tunisie;;180;7;Essilor;;;;;;;Progressif;1,600;;",
        "LEN-1;Lentilles journalières;Lentille;Johnson & Johnson Vision;;85,5;7;Acuvue;Moist;"
        "Ocean Blue;;;;Sphérique;;;Journalière;30",
        "DIV-1;Étui rigide;Divers;Luxottica Tunisie;3700000000017;25;19;;;;;;;;;;;",
    ]
)


def fichier(texte, nom="catalogue.csv"):
    return SimpleUploadedFile(nom, texte.encode("utf-8"), content_type="text/csv")


def classeur(lignes, nom="catalogue.xlsx"):
    wb = Workbook()
    for ligne in lignes:
        wb.active.append(ligne)
    tampon = io.BytesIO()
    wb.save(tampon)
    return SimpleUploadedFile(nom, tampon.getvalue())


@pytest.fixture
def fournisseurs(tunis):
    for nom in ("Luxottica Tunisie", "Essilor Tunisie", "Johnson & Johnson Vision"):
        Fournisseur.objects.create(nom=nom, pays=tunis.pays)


@pytest.fixture
def logisticien(affecter, client_de, tunis):
    return client_de(
        affecter(
            "logisticien",
            *DROITS_CATALOGUE,
            "stock.add_mouvementstock",
            portee="magasin",
            magasin=tunis,
        )
    )


def importer(api, contenu, quoi="catalogue", **extra):
    """Vérifie le fichier puis l'importe avec le jeton de la vérification, comme l'écran.

    Avec ``apercu=True``, vérifie seulement ; une vérification en erreur est rendue telle quelle.
    """
    url = f"/api/v1/imports/{quoi}/"
    verification = api.post(url, {"fichier": contenu, **extra, "apercu": True}, format="multipart")
    if extra.get("apercu") or verification.status_code != 200:
        return verification
    contenu.seek(0)
    jeton = verification.json()["jeton"]
    return api.post(url, {"fichier": contenu, **extra, "jeton": jeton}, format="multipart")


def test_import_du_catalogue_csv(logisticien, tunis, fournisseurs):
    reponse = importer(logisticien, fichier(CATALOGUE))
    assert reponse.status_code == 200, reponse.json()
    assert reponse.json() | {"erreurs": None} == {
        "apercu": False,
        "lignes": 4,
        "crees": 4,
        "modifies": 0,
        "erreurs": None,
        "alertes": [],
        "jeton": "",
    }
    monture = Article.objects.get(reference="MON-1")
    assert (monture.fournisseur.nom, monture.code_barres, monture.sur_commande) == (
        "Luxottica Tunisie",
        "8053672000001",
        False,
    )
    assert (monture.monture.marque, monture.monture.calibre, monture.monture.type) == (
        "Ray-Ban",
        51,
        "cerclee",
    )
    verre = Article.objects.get(reference="VER-1")
    assert verre.sur_commande  # un verre est à commander, sauf colonne sur_commande à « non »
    assert (verre.verre.geometrie, str(verre.verre.indice)) == ("progressif", "1.600")
    lentille = Article.objects.get(reference="LEN-1").lentille
    assert (lentille.renouvellement, lentille.lentilles_par_boite) == ("journaliere", 30)
    assert (lentille.categorie, lentille.couleur) == ("optique", "Ocean Blue")
    prix = PrixArticle.objects.get(article__reference="LEN-1", pays=tunis.pays)
    assert (str(prix.prix_vente_ttc), prix.tva.taux) == ("85.500", 7)
    assert not hasattr(Article.objects.get(reference="DIV-1"), "monture")

    # Réimporter met à jour par référence, sans doublon.
    modifie = CATALOGUE.replace("489,000", "499,000")
    assert importer(logisticien, fichier(modifie)).json()["modifies"] == 4
    assert str(PrixArticle.objects.get(article=monture).prix_vente_ttc) == "499.000"
    assert Article.objects.count() == 4


def test_lentille_solaire_de_couleur(logisticien, fournisseurs):
    contenu = (
        "reference;libelle;famille;fournisseur;prix_ttc;tva;categorie;couleur;renouvellement\n"
        "167;I SEE COLOR FRECH MINT;Lentille;Johnson & Johnson Vision;35;19;Lentille solaire;"
        "FRECH MINT;Trimestrielle\n"
    )
    reponse = importer(logisticien, fichier(contenu))
    assert reponse.status_code == 200, reponse.json()
    lentille = Article.objects.get(reference="167").lentille
    assert (lentille.categorie, lentille.couleur) == ("solaire", "FRECH MINT")
    assert decrire(lentille).startswith("solaire · FRECH MINT · Trimestrielle")


def test_import_excel_avec_code_barres_numerique(logisticien, fournisseurs):
    contenu = classeur(
        [
            ["reference", "libelle", "famille", "fournisseur", "code_barres", "sur_commande"],
            ["MON-9", "Monture enfant", "monture", "Luxottica Tunisie", 8053672000099, ""],
            ["VER-9", "Verre unifocal de stock", "verre", "Essilor Tunisie", None, "non"],
        ]
    )
    reponse = importer(logisticien, contenu)
    assert reponse.status_code == 400  # un verre exige sa géométrie
    assert reponse.json()["erreurs"][0]["ligne"] == 3
    assert "geometrie" in reponse.json()["erreurs"][0]["message"]
    assert not Article.objects.exists()

    contenu = classeur(
        [
            [
                "reference",
                "libelle",
                "famille",
                "fournisseur",
                "code_barres",
                "sur_commande",
                "geometrie",
            ],
            ["MON-9", "Monture enfant", "monture", "Luxottica Tunisie", 8053672000099, "", ""],
            ["VER-9", "Verre de stock", "verre", "Essilor Tunisie", None, "non", "unifocal"],
        ]
    )
    assert importer(logisticien, contenu).status_code == 200
    assert Article.objects.get(reference="MON-9").code_barres == "8053672000099"
    assert not Article.objects.get(reference="VER-9").sur_commande


def test_erreurs_signalees_par_ligne_et_rien_enregistre(logisticien, fournisseurs):
    lignes = CATALOGUE.splitlines()
    lignes[2] = lignes[2].replace("essilor tunisie", "Inconnu SA")
    lignes[3] = lignes[3].replace(";85,5;7;", ";85,5;12;")
    lignes.append(lignes[1])
    lignes.append("DIV-2;Chiffon;Accessoire;Luxottica Tunisie;;;;;;;;;;;;;;")
    reponse = importer(logisticien, fichier("\n".join(lignes)))
    assert reponse.status_code == 400
    erreurs = {e["ligne"]: e["message"] for e in reponse.json()["erreurs"]}
    assert set(erreurs) == {3, 4, 6, 7}
    assert "Inconnu SA" in erreurs[3] and "écran Fournisseurs" in erreurs[3]
    assert "tva" in erreurs[4] and "19" in erreurs[4]
    assert "déjà en ligne 2" in erreurs[6]
    assert "Accessoire" in erreurs[7]
    assert not Article.objects.exists()


def test_apercu_sans_rien_enregistrer(logisticien, fournisseurs):
    reponse = importer(logisticien, fichier(CATALOGUE), apercu=True)
    assert (reponse.status_code, reponse.json()["crees"], reponse.json()["apercu"]) == (
        200,
        4,
        True,
    )
    assert not Article.objects.exists()


def test_fichiers_refuses(logisticien, fournisseurs):
    for contenu, attendu in (
        (SimpleUploadedFile("a.pdf", b"%PDF"), "xlsx ou .csv"),
        (fichier(""), "vide"),
        (SimpleUploadedFile("a.xlsx", b"pas un classeur"), "illisible"),
    ):
        reponse = importer(logisticien, contenu)
        assert reponse.status_code == 400
        assert attendu in reponse.json()["fichier"][0]
    colonnes = importer(logisticien, fichier("reference;libelle\nX;Y\n"))
    assert "fournisseur" in colonnes.json()["erreurs"][0]["message"]


def test_import_du_catalogue_reserve(affecter, client_de, tunis, fournisseurs):
    vendeur = client_de(affecter("vendeur", "stock.view_article", portee="magasin", magasin=tunis))
    assert importer(vendeur, fichier(CATALOGUE)).status_code == 403


def test_entrees_de_stock(logisticien, tunis, reseau, fournisseurs, affecter, client_de):
    importer(logisticien, fichier(CATALOGUE))
    bon = "code_barres,reference,quantite\n8053672000001,,5\n,DIV-1,12\n"
    tunis_ = {"magasin": str(tunis.public_id)}
    reponse = importer(logisticien, fichier(bon, "bl.csv"), "stock", piece="BL-778", **tunis_)
    assert reponse.status_code == 200, reponse.json()
    assert reponse.json()["crees"] == 2
    monture = Article.objects.get(reference="MON-1")
    assert stock_disponible(tunis, monture) == 5
    assert set(MouvementStock.tous.values_list("reference", "type")) == {("BL-778", "reception")}

    bon_faux = "reference;quantite\nMON-1;2\nVER-1;1\nINCONNU;1\nDIV-1;-3\n"
    erreurs = importer(logisticien, fichier(bon_faux, "b.csv"), "stock", **tunis_)
    assert erreurs.status_code == 400
    messages = {e["ligne"]: e["message"] for e in erreurs.json()["erreurs"]}
    assert set(messages) == {3, 4, 5}
    assert "commandé pour chaque client" in messages[3]
    assert stock_disponible(tunis, monture) == 5  # rien enregistré, pas même la ligne valide

    # Hors de son magasin, le logisticien ne fait pas d'entrée de stock.
    ailleurs = importer(
        logisticien, fichier(bon, "bl.csv"), "stock", magasin=str(reseau["lille"].public_id)
    )
    assert ailleurs.status_code == 404


def test_import_sans_verification_refuse(logisticien, fournisseurs):
    direct = logisticien.post(
        "/api/v1/imports/catalogue/", {"fichier": fichier(CATALOGUE)}, format="multipart"
    )
    assert direct.status_code == 400
    assert "Vérifier ce fichier" in direct.json()["jeton"][0]
    # Le jeton d'un fichier ne vaut pas pour un autre, même modifié d'un caractère.
    jeton = importer(logisticien, fichier(CATALOGUE), apercu=True).json()["jeton"]
    autre = logisticien.post(
        "/api/v1/imports/catalogue/",
        {"fichier": fichier(CATALOGUE.replace("489,000", "1,000")), "jeton": jeton},
        format="multipart",
    )
    assert autre.status_code == 400
    assert not Article.objects.exists()


def test_alertes_sur_les_articles_deja_en_stock(logisticien, tunis, fournisseurs):
    importer(logisticien, fichier(CATALOGUE))
    tunis_ = {"magasin": str(tunis.public_id)}
    bon = "code_barres;quantite\n8053672000001;5\n"
    importer(logisticien, fichier(bon, "bl.csv"), "stock", **tunis_)

    # Le catalogue réimporté signale les articles existants et leur stock.
    verification = importer(logisticien, fichier(CATALOGUE), apercu=True).json()
    alertes = {a["ligne"]: a["message"] for a in verification["alertes"]}
    assert alertes[2] == (
        "MON-1 existe déjà au catalogue : il sera mis à jour (en stock : Tunis Centre 5)."
    )
    assert alertes[5].endswith("(pas en stock).")

    # Une nouvelle entrée signale le stock déjà présent, cumulé ligne après ligne.
    DEPOT_TUNIS = "au dépôt Dépôt Tunis Centre"  # noqa: N806
    bon = "code_barres;quantite\n8053672000001;2\n8053672000001;3\n3700000000017;1\n"
    verification = importer(logisticien, fichier(bon, "bl.csv"), "stock", apercu=True, **tunis_)
    assert verification.json()["alertes"] == [
        {"ligne": 2, "message": f"MON-1 déjà en stock {DEPOT_TUNIS} : 5 ; 7 après l'entrée."},
        {"ligne": 3, "message": f"MON-1 déjà en stock {DEPOT_TUNIS} : 7 ; 10 après l'entrée."},
    ]
