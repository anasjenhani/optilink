"""Liste des ophtalmologistes : recherche, ajout sans doublon, ordonnance rattachée à la liste."""

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.optique.models import Ophtalmologue, Prescription
from apps.optique.ophtalmologues import cle_ophtalmologue

from .test_admin_imports import _admin
from .test_clients_ordonnances import ORDONNANCES, corps_ordonnance, dupont  # noqa: F401

URL = "/api/v1/ophtalmologues/"


@pytest.fixture
def opticien(affecter, reseau):
    return affecter("opticien", *ORDONNANCES, portee="magasin", magasin=reseau["lille"])


def test_cle_sans_titre_accents_ni_ponctuation():
    assert cle_ophtalmologue("Dr. Ben-Sâlah  Ali") == "ali ben salah"
    assert cle_ophtalmologue("docteur ali ben salah") == "ali ben salah"
    assert cle_ophtalmologue("Dr") == ""


def test_recherche_et_ajout_sans_doublon(client_de, opticien):
    api = client_de(opticien)
    reponse = api.post(URL, {"nom": "Dr Ben Salah Ali"}, format="json")
    assert reponse.status_code == 201, reponse.json()
    Ophtalmologue.objects.create(nom="Dr Trabelsi Mona")

    assert [o["nom"] for o in api.get(URL, {"recherche": "salah"}).json()] == ["Dr Ben Salah Ali"]
    assert [o["nom"] for o in api.get(URL, {"recherche": "mona trab"}).json()] == [
        "Dr Trabelsi Mona"
    ]
    assert len(api.get(URL).json()) == 2

    double = api.post(URL, {"nom": "ben-salah ALI"}, format="json")
    assert double.status_code == 400
    assert "déjà dans la liste" in str(double.json())
    assert Ophtalmologue.objects.count() == 2

    with pytest.raises(ValidationError):
        Ophtalmologue(nom="Docteur Ben Salah Ali").full_clean()


def test_ordonnance_reprend_le_medecin_de_la_liste(client_de, opticien, reseau, dupont):  # noqa: F811
    Ophtalmologue.objects.create(nom="Dr Martin")
    api = client_de(opticien)
    corps = corps_ordonnance(dupont, reseau["lille"])
    corps["prescripteur"] = "docteur MARTIN"
    assert api.post("/api/v1/prescriptions/", corps, format="json").status_code == 201
    assert Prescription.objects.get().prescripteur == "Dr Martin"

    # Un médecin inconnu entre dans la liste à la première ordonnance.
    corps["prescripteur"] = "Dr Gharbi"
    assert api.post("/api/v1/prescriptions/", corps, format="json").status_code == 201
    assert Ophtalmologue.objects.filter(cle="gharbi").exists()

    corps["prescripteur"] = "Dr"
    assert api.post("/api/v1/prescriptions/", corps, format="json").status_code == 400


def test_il_faut_le_droit_de_saisir_une_ordonnance(affecter, client_de, reseau):
    vendeur = affecter("vendeur", "crm.view_client", portee="magasin", magasin=reseau["lille"])
    api = client_de(vendeur)
    assert api.get(URL).status_code == 403
    assert api.post(URL, {"nom": "Dr X"}, format="json").status_code == 403


# Fichier « Medecin » de l'ancien logiciel, tel quel (BOM, colonnes TelCabinet…).
MEDECIN = (
    "\ufeffCodeMedecin;Nom;Prenom;Adresse;TelCabinet;TelDomicile;TelPortable1;Ville\r\n"
    "081;REKIK;RIADH;BELVEDAIRE;71847620;;;\r\n"
    "083;rekik;riadh;le bélvédére ;71847620;;98 000 111;\r\n"
    "027;nasri dhahak;henda ;kram;71.734.164;;;\r\n"
    "088;DHAHAK NASRI;HENDA;;71734164;;;\r\n"
    "217;wajdi ;zribi;;74406706;;74406004  fax;\r\n"
    "029;MKHININI;NAOUFEL;;;;36151952;30\r\n"
)


def test_import_du_fichier_medecin_de_l_ancien_logiciel(creer_utilisateur, client_de):
    Ophtalmologue.objects.create(nom="Dr Zribi Wajdi", telephone="")
    navigateur = _admin(creer_utilisateur, client_de)
    liste = "/admin/optique/ophtalmologue/"
    assert f"{liste}importer/ophtalmologues/" in navigateur.get(liste).content.decode()

    url = f"{liste}importer/ophtalmologues/"
    fichier = SimpleUploadedFile("Medecin.csv", MEDECIN.encode())
    verification = navigateur.post(url, {"fichier": fichier})
    rapport = verification.context["rapport"]
    assert (rapport.crees, rapport.modifies, rapport.erreurs) == (3, 1, [])
    fin = navigateur.post(url, {"importer": "1", "jeton": verification.context["jeton"]})
    assert "Import terminé" in fin.content.decode()

    medecins = {o.nom: o for o in Ophtalmologue.objects.all()}
    assert sorted(medecins) == [
        "Dr Zribi Wajdi",
        "MKHININI Naoufel",
        "NASRI DHAHAK Henda",
        "REKIK Riadh",
    ]
    rekik = medecins["REKIK Riadh"]
    assert (rekik.telephone, rekik.telephone_2, rekik.adresse) == (
        "71847620",
        "98000111",
        "BELVEDAIRE",
    )
    assert rekik.anciens_codes == "081, 083"
    # Code OptiLink attribué à la suite : 001, 002…
    assert sorted(o.code for o in medecins.values()) == ["001", "002", "003", "004"]
    assert medecins["NASRI DHAHAK Henda"].anciens_codes == "027, 088"
    assert medecins["Dr Zribi Wajdi"].telephone == "74406706"
    assert medecins["Dr Zribi Wajdi"].telephone_2 == "74406004"
    # Sans téléphone du cabinet, le portable devient le téléphone principal.
    assert medecins["MKHININI Naoufel"].telephone == "36151952"
    assert medecins["MKHININI Naoufel"].ville == ""


def test_code_sequentiel_et_colonne_code(creer_utilisateur, client_de):
    from apps.optique.imports import importer_ophtalmologues

    ali = Ophtalmologue.objects.create(nom="Dr Ali")
    assert ali.code == "001"
    lignes = [
        (2, {"code": "010", "nom": "Mrad", "prenom": "Ahmed"}),
        (3, {"code": "", "nom": "Toumi", "prenom": "Zouheir"}),
    ]
    rapport = importer_ophtalmologues(lignes)
    assert rapport.erreurs == []
    assert Ophtalmologue.objects.get(cle="ahmed mrad").code == "010"
    assert Ophtalmologue.objects.get(cle="toumi zouheir").code == "011"
    # Les codes du fichier font foi : Mrad perd le 010 et reçoit le code suivant.
    rapport = importer_ophtalmologues(
        [(2, {"code": "010", "nom": "Autre", "prenom": "X"}), (3, {"code": "010", "nom": "Y"})]
    )
    assert rapport.erreurs == [{"ligne": 3, "message": "code : 010 déjà en ligne 2."}]
    importer_ophtalmologues([(2, {"code": "010", "nom": "Autre", "prenom": "X"})])
    assert Ophtalmologue.objects.get(cle="autre x").code == "010"
    assert Ophtalmologue.objects.get(cle="ahmed mrad").code == "012"
