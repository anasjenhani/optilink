"""Sociétés : code généré, fiche complète, logo, et reprise des anciennes régions."""

import pytest
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from apps.reseau.admin import SocieteForm
from apps.reseau.models import Societe

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def formulaire(instance=None, fichiers=None, **donnees):
    return SocieteForm(
        data={"raison_sociale": "Jribi Optic L'Aouina"} | donnees,
        files=fichiers or {},
        instance=instance,
    )


@pytest.mark.django_db
def test_code_genere_a_la_suite():
    premiere = Societe.objects.create(raison_sociale="A")
    Societe.objects.create(raison_sociale="Ancienne", code="AUTRE")
    deuxieme = Societe.objects.create(raison_sociale="B")
    assert (premiere.code, deuxieme.code) == ("SCTE001", "SCTE002")
    deuxieme.raison_sociale = "B modifiée"
    deuxieme.save()
    assert deuxieme.code == "SCTE002"


@pytest.mark.django_db
def test_fiche_complete_et_logo():
    f = formulaire(
        fichiers={"logo_fichier": SimpleUploadedFile("logo.png", PNG)},
        forme_juridique="SARL",
        matricule_fiscal="1875667/K/N/M/000",
        banque="Zitouna",
        rib="25148000000850850283",
        adresse="Résidence Rania M20, L'Aouina",
        code_postal="4216",
        ville="Ariana",
        telephone_1="24648500",
        site_web="http://www.jribioptic.com",
    )
    assert f.is_valid(), f.errors
    societe = f.save()
    societe.refresh_from_db()
    assert societe.code == "SCTE001"
    assert (bytes(societe.logo), societe.logo_type) == (PNG, "image/png")

    # Modifier la fiche sans envoyer de fichier garde le logo ; la case le supprime.
    f = formulaire(instance=societe, ville="Tunis")
    assert f.is_valid(), f.errors
    f.save()
    societe.refresh_from_db()
    assert bytes(societe.logo) == PNG
    f = formulaire(instance=societe, supprimer_logo="on")
    assert f.is_valid(), f.errors
    f.save()
    societe.refresh_from_db()
    assert societe.logo is None and societe.logo_type == ""


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("contenu", "erreur"),
    [
        (b"<svg onload=alert(1)>", "PNG, JPEG ou WebP"),
        (PNG + b"\x00" * 1024 * 1024, "1 Mo"),
    ],
)
def test_logo_refuse(contenu, erreur):
    f = formulaire(fichiers={"logo_fichier": SimpleUploadedFile("logo.png", contenu)})
    assert not f.is_valid()
    assert erreur in str(f.errors["logo_fichier"])


@pytest.mark.django_db
def test_rib_refuse_la_ponctuation():
    f = formulaire(rib="2514-8000")
    assert not f.is_valid() and "rib" in f.errors


@pytest.mark.django_db
def test_role_responsable_societe():
    assert Group.objects.filter(name="Responsable société").exists()
    assert not Group.objects.filter(name="Responsable régional").exists()


@pytest.mark.django_db(transaction=True)
def test_les_regions_deviennent_des_societes():
    avant = [("reseau", "0004_code_numerique"), ("securite", "0003_journaux_en_ajout_seul")]
    apres = [("reseau", "0005_societes"), ("securite", "0004_perimetre_societe")]
    executor = MigrationExecutor(connection)
    executor.migrate(avant)
    anciens = executor.loader.project_state(avant).apps
    Region = anciens.get_model("reseau", "Region")
    Group = anciens.get_model("auth", "Group")
    nord = Region.objects.create(code="NORD", nom="Nord")
    Region.objects.create(code="SUD", nom="Sud")
    tunisie = anciens.get_model("reseau", "Pays").objects.get(code="TN")
    magasin = anciens.get_model("reseau", "Magasin").objects.create(
        code="T01", nom="Tunis", region=nord, pays=tunisie
    )
    Group.objects.filter(name="Responsable société").update(name="Responsable régional")
    role = Group.objects.get(name="Responsable régional")
    utilisateur = anciens.get_model("securite", "Utilisateur").objects.create(username="resp")
    anciens.get_model("securite", "Affectation").objects.create(
        utilisateur=utilisateur, role=role, portee="region", region=nord
    )

    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(apres)
    nouveaux = executor.loader.project_state(apres).apps
    Societe_ = nouveaux.get_model("reseau", "Societe")
    assert list(Societe_.objects.values_list("code", "raison_sociale")) == [
        ("SCTE001", "Nord"),
        ("SCTE002", "Sud"),
    ]
    assert nouveaux.get_model("reseau", "Magasin").objects.get(pk=magasin.pk).societe.code == (
        "SCTE001"
    )
    affectation = nouveaux.get_model("securite", "Affectation").objects.get()
    assert (affectation.portee, affectation.societe.code) == ("societe", "SCTE001")
    assert nouveaux.get_model("auth", "Group").objects.get(pk=role.pk).name == (
        "Responsable société"
    )

    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())
