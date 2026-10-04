"""Import des clients depuis l'export d'un autre logiciel : colonnes reconnues, tout ou rien."""

from datetime import date, datetime

import pytest

from apps.crm.models import Client

from .test_imports import classeur, fichier, importer

# Export typique d'un ancien logiciel : noms de colonnes à sa façon.
ANCIEN_LOGICIEL = "\n".join(
    [
        "N° Fiche;Civ;Nom;Prénom;Date de naissance;GSM;Fixe;E-mail;Ville;Observations",
        "1042;Madame;Ben Salah;Amira;12/05/1985;98 123 456;71 000 111;amira@exemple.tn;"
        "Tunis;Verres progressifs",
        "1043;M.;Trabelsi;Karim;;22 333 444;;;La Marsa;",
    ]
)


@pytest.fixture
def accueil(affecter, client_de, tunis):
    return client_de(
        affecter(
            "accueil",
            "crm.view_client",
            "crm.add_client",
            "crm.change_client",
            portee="magasin",
            magasin=tunis,
        )
    )


def importer_clients(api, contenu, magasin, **extra):
    return importer(api, contenu, "clients", magasin=str(magasin.public_id), **extra)


def test_import_depuis_un_ancien_logiciel(accueil, tunis):
    reponse = importer_clients(accueil, fichier(ANCIEN_LOGICIEL, "clients.csv"), tunis)
    assert reponse.status_code == 200, reponse.json()
    assert reponse.json()["crees"] == 2

    amira = Client.objects.get(reference_externe="1042")
    assert (amira.civilite, amira.nom, amira.prenom) == ("mme", "Ben Salah", "Amira")
    assert amira.date_naissance == date(1985, 5, 12)
    assert (amira.telephone, amira.telephone_2) == ("98 123 456", "71 000 111")
    assert amira.notes == "Verres progressifs"
    assert amira.magasin_origine == tunis
    assert amira.numero  # nouveau n° de fiche OptiLink

    # On retrouve le client par son ancien n° de fiche.
    trouves = accueil.get("/api/v1/clients/", {"recherche": "1043"}).json()["results"]
    assert [c["nom"] for c in trouves] == ["Trabelsi"]


def test_reimport_met_a_jour_sans_doublon(accueil, tunis):
    importer_clients(accueil, fichier(ANCIEN_LOGICIEL, "clients.csv"), tunis)
    corrige = ANCIEN_LOGICIEL.replace("La Marsa", "Carthage")
    verification = importer_clients(accueil, fichier(corrige, "clients.csv"), tunis, apercu=True)
    assert verification.json()["modifies"] == 2
    assert "déjà importé" in verification.json()["alertes"][0]["message"]

    importer_clients(accueil, fichier(corrige, "clients.csv"), tunis)
    assert Client.objects.count() == 2
    assert Client.objects.get(reference_externe="1043").ville == "Carthage"


def test_excel_avec_nom_complet_et_doublon_possible(accueil, tunis):
    Client.objects.create(
        nom="Ben Salah", prenom="Amira", telephone="98 123 456", magasin_origine=tunis
    )
    contenu = classeur(
        [
            ["Code client", "Nom et prénom", "Téléphone", "Date naiss"],
            [7, "BEN-SALAH Amira", "98 123 456", datetime(1985, 5, 12)],
        ],
        "export.xlsx",
    )
    verification = importer_clients(accueil, contenu, tunis, apercu=True)
    assert verification.status_code == 200, verification.json()
    assert "doublon possible" in verification.json()["alertes"][0]["message"]

    contenu.seek(0)
    importer_clients(accueil, contenu, tunis)
    nouveau = Client.objects.get(reference_externe="7")
    assert (nouveau.nom, nouveau.prenom, nouveau.date_naissance) == (
        "BEN-SALAH",
        "Amira",
        date(1985, 5, 12),
    )


def test_erreurs_par_ligne_et_rien_enregistre(accueil, tunis):
    contenu = "\n".join(
        [
            "N° fiche;Nom;Prénom;Date de naissance;Email",
            "1;Ben Ali;Sami;31/02/1990;",
            "2;Gharbi;;;",
            "1;Jaziri;Leila;;pas-un-email",
        ]
    )
    reponse = importer_clients(accueil, fichier(contenu, "clients.csv"), tunis, apercu=True)
    assert reponse.status_code == 400
    erreurs = {e["ligne"]: e["message"] for e in reponse.json()["erreurs"]}
    assert "pas une date" in erreurs[2]
    assert "prenom" in erreurs[3]
    assert "déjà en ligne 2" in erreurs[4]
    assert Client.objects.count() == 0


def test_import_clients_reserve(affecter, client_de, tunis, reseau):
    vendeur = client_de(affecter("vendeur", "crm.view_client", portee="magasin", magasin=tunis))
    reponse = importer_clients(vendeur, fichier(ANCIEN_LOGICIEL, "clients.csv"), tunis)
    assert reponse.status_code == 403

    # Droit de créer des clients à Tunis seulement : Lille, hors périmètre, est introuvable.
    accueil = client_de(
        affecter(
            "accueil",
            "crm.add_client",
            "crm.change_client",
            portee="magasin",
            magasin=tunis,
        )
    )
    ailleurs = importer_clients(accueil, fichier(ANCIEN_LOGICIEL, "clients.csv"), reseau["lille"])
    assert ailleurs.status_code == 404
