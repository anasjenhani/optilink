"""Liste des ophtalmologistes : recherche, ajout sans doublon, ordonnance rattachée à la liste."""

import pytest
from django.core.exceptions import ValidationError

from apps.optique.models import Ophtalmologue, Prescription
from apps.optique.ophtalmologues import cle_ophtalmologue

from .test_clients_ordonnances import ORDONNANCES, corps_ordonnance, dupont  # noqa: F401

URL = "/api/v1/ophtalmologues/"


@pytest.fixture
def opticien(affecter, reseau):
    return affecter("opticien", *ORDONNANCES, portee="magasin", magasin=reseau["lille"])


def test_cle_sans_titre_accents_ni_ponctuation():
    assert cle_ophtalmologue("Dr. Ben-Sâlah  Ali") == "ben salah ali"
    assert cle_ophtalmologue("docteur ben salah ali") == "ben salah ali"
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
