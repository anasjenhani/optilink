"""Listes de référence des verres et des montures : import, liens et contrôles."""

import pytest
from django.core.exceptions import ValidationError

from apps.achats.models import Fournisseur
from apps.stock.imports_referentiels import importer_liste
from apps.stock.models import (
    Article,
    CouleurVerre,
    FamilleVerre,
    MarqueMonture,
    SousFamilleVerre,
    Verre,
)

from .test_admin_imports import _admin
from .test_imports import fichier, importer
from .test_imports_modeles import acheteur  # noqa: F401  (fixture)


def lignes(*dicts):
    return [(n, d) for n, d in enumerate(dicts, start=2)]


@pytest.fixture
def sicom(tunis):
    return Fournisseur.objects.create(nom="SICOM", pays=tunis.pays)


def test_familles_puis_sous_familles(sicom):
    rapport = importer_liste(
        "familles_verres",
        lignes(
            {
                "code": "27FV93",
                "fournisseur": "SICOM",
                "libelle": "VARILUX COMFORT",
                "foyer": "Progressif",
            },
            {
                "code": "27C",
                "fournisseur": "sicom",
                "libelle": "Varilux",
                "foyer": "03",
                "actif": "non",
            },
        ),
    )
    assert [e["message"] for e in rapport.erreurs] == [
        "foyer : « 03 » inconnu (valeurs possibles : Unifocal, Bifocal, Progressif)."
    ]
    assert not FamilleVerre.objects.exists()  # tout ou rien

    rapport = importer_liste(
        "familles_verres",
        lignes(
            {
                "code": "27FV93",
                "fournisseur": "SICOM",
                "libelle": "VARILUX COMFORT",
                "foyer": "Progressif",
            },
            {"code": "27C", "fournisseur": "sicom", "libelle": "Varilux", "actif": "non"},
        ),
    )
    assert rapport.erreurs == [] and rapport.crees == 2
    comfort = FamilleVerre.objects.get(code="27FV93")
    assert (comfort.fournisseur, comfort.foyer, comfort.est_actif) == (sicom, "progressif", True)

    rapport = importer_liste(
        "sous_familles_verres",
        lignes(
            {"code": "27SFV441", "famille": "27FV93", "libelle": "SPHERO"},
            {"code": "27SFV441", "famille": "27FV93", "libelle": "ORMA"},
            {"code": "X1", "famille": "16FV105", "libelle": "1.50"},
            {"code": "X2", "famille": "27C", "libelle": "Comfort"},
        ),
    )
    assert [e["message"] for e in rapport.erreurs] == [
        "code : 27SFV441 déjà en ligne 2.",
        "famille : code « 16FV105 » inconnu ; importer d'abord les familles.",
        "est_actif : La famille de cette sous-famille est inactive.",
    ]
    rapport = importer_liste(
        "sous_familles_verres",
        lignes({"code": "27SFV441", "famille": "27FV93", "libelle": "SPHERO"}),
    )
    assert rapport.crees == 1
    # Réimport : met à jour, une case vide garde la valeur.
    rapport = importer_liste(
        "familles_verres", lignes({"code": "27FV93", "libelle": "VX COMFORT", "fournisseur": ""})
    )
    assert rapport.modifies == 1
    comfort.refresh_from_db()
    assert (comfort.libelle, comfort.fournisseur) == ("VX COMFORT", sicom)


def test_fournisseur_inconnu_et_marques(db):
    rapport = importer_liste(
        "couleurs_verres",
        lignes({"code": "141CO81", "fournisseur": "141", "libelle": "RAYBAN GRIS"}),
    )
    assert "fournisseur : « 141 » inconnu" in rapport.erreurs[0]["message"]
    rapport = importer_liste(
        "marques_montures",
        lignes({"code": "R", "libelle": "RAY BAN"}, {"code": "RT", "libelle": "RAY BAN"}),
    )
    assert "libelle" in rapport.erreurs[0]["message"] or "Libellé" in rapport.erreurs[0]["message"]
    assert not MarqueMonture.objects.exists()


def test_le_verre_suit_sa_famille_et_son_fournisseur(sicom, tunis):
    famille = FamilleVerre.objects.create(code="27FV93", fournisseur=sicom, libelle="VX COMFORT")
    autre = FamilleVerre.objects.create(code="TNFV35", libelle="HILUX")
    sphero = SousFamilleVerre.objects.create(code="27SFV441", famille=famille, libelle="SPHERO")
    gris = CouleurVerre.objects.create(
        code="TNCO53",
        libelle="Gris",
        fournisseur=Fournisseur.objects.create(nom="TN OPTIC", pays=tunis.pays),
    )
    article = Article.objects.create(
        reference="V1", libelle="Verre", famille="verre", fournisseur=sicom
    )
    verre = Verre(article=article, geometrie="progressif", sous_famille=sphero)
    verre.full_clean()
    assert verre.famille_verre == famille
    verre.famille_verre = autre
    with pytest.raises(ValidationError, match="n'appartient pas"):
        verre.full_clean()
    verre.famille_verre, verre.couleur = famille, gris
    with pytest.raises(ValidationError, match="autre fournisseur"):
        verre.full_clean()


def test_listes_dans_l_administration(creer_utilisateur, client_de):
    navigateur = _admin(creer_utilisateur, client_de)
    for liste, quoi in (
        ("familleverre", "familles_verres"),
        ("sousfamilleverre", "sous_familles_verres"),
        ("couleurverre", "couleurs_verres"),
        ("diametreverre", "diametres_verres"),
        ("matiereverre", "matieres_verres"),
        ("marquemonture", "marques_montures"),
        ("marquelentille", "marques_lentilles"),
        ("couleurlentille", "couleurs_lentilles"),
        ("matierelentille", "matieres_lentilles"),
    ):
        page = navigateur.get(f"/admin/stock/{liste}/").content.decode()
        assert f"/admin/stock/{liste}/importer/{quoi}/" in page
        assert (
            navigateur.get(f"/admin/stock/{liste}/importer/{quoi}/modele.xlsx").status_code == 200
        )


def test_import_des_verres_avec_famille_et_couleur(acheteur, sicom):  # noqa: F811
    famille = FamilleVerre.objects.create(code="27FV93", fournisseur=sicom, libelle="VX COMFORT")
    SousFamilleVerre.objects.create(code="27SFV441", famille=famille, libelle="SPHERO")
    CouleurVerre.objects.create(code="27CO29", fournisseur=sicom, libelle="TR VII Gris")
    contenu = fichier(
        "reference;libelle;fournisseur;geometrie;sous_famille;couleur;prix_ttc;tva\n"
        "V1;Comfort Sphero;SICOM;Progressif;27SFV441;tr vii gris;300;7\n"
        "V2;Comfort X;SICOM;Progressif;INCONNUE;;300;7\n"
    )
    erreurs = importer(acheteur, contenu, "verres").json()["erreurs"]
    assert [e["ligne"] for e in erreurs] == [3]
    assert "sous_famille : « INCONNUE » absent de la liste" in erreurs[0]["message"]
