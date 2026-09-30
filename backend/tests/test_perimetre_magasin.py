import datetime

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.securite.models import Affectation
from core.perimetre import perimetre


def codes(reponse):
    return sorted(m["code"] for m in reponse.json()["results"])


def test_anonyme_refuse(client, reseau):
    assert client.get("/api/v1/magasins/").status_code == 403


def test_affectation_magasin_ne_voit_que_son_magasin(reseau, creer_utilisateur, client_de):
    vendeur = creer_utilisateur("vendeur", portee="magasin", magasin=reseau["lille"])
    client = client_de(vendeur)

    assert codes(client.get("/api/v1/magasins/")) == ["M01"]
    nice = reseau["nice"].public_id
    assert client.get(f"/api/v1/magasins/{nice}/").status_code == 404


def test_affectation_region_voit_les_magasins_de_la_region(reseau, creer_utilisateur, client_de):
    responsable = creer_utilisateur("resp", portee="region", region=reseau["nord"])
    assert codes(client_de(responsable).get("/api/v1/magasins/")) == ["M01", "M02"]


def test_affectation_reseau_voit_tout(reseau, creer_utilisateur, client_de):
    direction = creer_utilisateur("direction", portee="reseau")
    assert codes(client_de(direction).get("/api/v1/magasins/")) == ["M01", "M02", "M03"]


def test_sans_affectation_ne_voit_rien(reseau, creer_utilisateur, client_de):
    assert codes(client_de(creer_utilisateur("nouveau")).get("/api/v1/magasins/")) == []


def test_affectation_terminee_ne_donne_plus_acces(reseau, creer_utilisateur, client_de):
    hier = datetime.date.today() - datetime.timedelta(days=1)
    ancien = creer_utilisateur(
        "ancien",
        portee="magasin",
        magasin=reseau["lille"],
        debut=hier - datetime.timedelta(days=30),
        fin=hier,
    )
    assert codes(client_de(ancien).get("/api/v1/magasins/")) == []


def test_perimetre_filtre_aussi_hors_api(reseau):
    from apps.reseau.models import Magasin

    with perimetre({reseau["arras"].id}):
        assert list(Magasin.objects.values_list("code", flat=True)) == ["M02"]
    assert Magasin.objects.count() == 3


def test_portee_incoherente_refusee_par_la_validation(reseau, role, creer_utilisateur):
    affectation = Affectation(
        utilisateur=creer_utilisateur("x"), role=role, portee="magasin", region=reseau["nord"]
    )
    with pytest.raises(ValidationError):
        affectation.full_clean()


def test_portee_incoherente_refusee_par_la_base(reseau, role, creer_utilisateur):
    with pytest.raises(IntegrityError):
        Affectation.objects.create(
            utilisateur=creer_utilisateur("y"), role=role, portee="reseau", magasin=reseau["lille"]
        )
