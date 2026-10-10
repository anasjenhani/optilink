"""Dépôts rattachés aux magasins : le stock se compte par dépôt (vente, central, casse)."""

import pytest
from django.core.exceptions import ValidationError

from apps.reseau.models import Depot, Magasin
from apps.stock.imports import importer_stock
from apps.stock.inventaires import compter, ouvrir_inventaire, terminer_comptage, valider_inventaire
from apps.stock.models import MouvementStock, stock_disponible
from apps.stock.transferts import TransfertImpossible, envoyer_transfert, recevoir_transfert
from tests.test_admin_imports import _admin
from tests.test_depot_central import optique, recevoir  # noqa: F401
from tests.test_receptions import ligne


@pytest.fixture
def aouina(tunis):
    """Le magasin de Tunis abrite le dépôt central et le dépôt casse, à côté de son dépôt de
    vente, comme DEPTN, DEPCEN et DEPCAS dans l'ancien logiciel."""
    Depot.objects.create(magasin=tunis, code="DEPCEN", nom="Dépôt central", type="central")
    Depot.objects.create(magasin=tunis, code="DEPCAS", nom="Dépôt casse", type="casse")
    return tunis


def _depot(code):
    return Depot.objects.get(code=code)


def test_chaque_magasin_a_son_depot_de_vente(tunis):
    vente = tunis.depots.get()
    assert (vente.code, vente.type, vente.nom) == ("T01", "vente", "Dépôt Tunis Centre")
    assert tunis.depot_de_vente == tunis.depot_de_reception == vente
    assert not tunis.est_depot


def test_un_seul_depot_central_par_societe(aouina):
    lac = Magasin.tous.create(code="T02", nom="Lac", societe=aouina.societe, pays=aouina.pays)
    autre = Depot(magasin=lac, code="DEPLAC", nom="Autre central", type="central")
    with pytest.raises(ValidationError, match="déjà un dépôt central"):
        autre.full_clean()


def test_le_stock_se_compte_par_depot(aouina, monture, optique, creer_utilisateur):  # noqa: F811
    auteur = creer_utilisateur("depot")
    # Le magasin abrite le dépôt central : il saisit les achats, qui entrent au dépôt central.
    assert aouina.est_depot and aouina.depot_de_reception == _depot("DEPCEN")
    recevoir(aouina, optique, auteur, [ligne(monture, 4, "100")])
    assert stock_disponible(aouina, monture, _depot("DEPCEN")) == 4
    # Les ventes sortent du dépôt de vente, qui a son propre stock (3 au départ).
    assert stock_disponible(aouina, monture) == 3

    # Du dépôt central au dépôt de vente, dans le même magasin.
    transfert = envoyer_transfert(
        magasin=aouina,
        destination=aouina,
        lignes=[{"article": monture, "quantite": 2}],
        auteur=auteur,
    )
    assert (transfert.depot_origine.code, transfert.depot_destination.code) == ("DEPCEN", "T01")
    recevoir_transfert(transfert, auteur=auteur)
    assert stock_disponible(aouina, monture) == 5
    assert stock_disponible(aouina, monture, _depot("DEPCEN")) == 2

    # Un article cassé part au dépôt casse ; il ne compte plus dans le stock de vente.
    casse = envoyer_transfert(
        magasin=aouina,
        destination=aouina,
        depot_origine=aouina.depot_de_vente,
        depot_destination=_depot("DEPCAS"),
        lignes=[{"article": monture, "quantite": 1}],
        auteur=auteur,
    )
    recevoir_transfert(casse, auteur=auteur)
    assert stock_disponible(aouina, monture) == 4
    assert stock_disponible(aouina, monture, _depot("DEPCAS")) == 1
    with pytest.raises(TransfertImpossible, match="autre dépôt"):
        envoyer_transfert(
            magasin=aouina,
            destination=aouina,
            depot_origine=_depot("DEPCAS"),
            depot_destination=_depot("DEPCAS"),
            lignes=[{"article": monture, "quantite": 1}],
            auteur=auteur,
        )


def test_inventaire_d_un_depot(aouina, monture, creer_utilisateur):
    auteur = creer_utilisateur("stock")
    central = _depot("DEPCEN")
    MouvementStock.tous.create(depot=central, article=monture, quantite=5, type="reception")
    inventaire = ouvrir_inventaire(magasin=aouina, depot=central, auteur=auteur)
    # Un inventaire à la fois par dépôt, mais le dépôt de vente peut être compté en même temps.
    ouvrir_inventaire(magasin=aouina, auteur=auteur)
    compter(inventaire, monture, quantite=4)
    terminer_comptage(inventaire, auteur=auteur)
    valider_inventaire(inventaire, auteur=auteur, observation="Comptage du dépôt")
    assert stock_disponible(aouina, monture, central) == 4
    assert stock_disponible(aouina, monture) == 3


def test_import_du_stock_dans_un_depot(aouina, monture, creer_utilisateur):
    auteur = creer_utilisateur("stock")
    lignes = [
        (2, {"reference": "MON-T", "quantite": "6", "depot": "depcen"}),
        (3, {"reference": "MON-T", "quantite": "1", "depot": ""}),
    ]
    rapport = importer_stock(lignes, magasin=aouina, utilisateur=auteur)
    assert (rapport.crees, rapport.erreurs) == (2, [])
    assert stock_disponible(aouina, monture, _depot("DEPCEN")) == 6
    assert stock_disponible(aouina, monture) == 4

    erreur = importer_stock(
        [(2, {"reference": "MON-T", "quantite": "1", "depot": "INCONNU"})],
        magasin=aouina,
        utilisateur=auteur,
    )
    assert "n'est pas un dépôt actif" in erreur.erreurs[0]["message"]


def test_les_depots_dans_l_api_et_l_administration(aouina, creer_utilisateur, client_de):
    navigateur = _admin(creer_utilisateur, client_de)
    magasin = navigateur.get(f"/api/v1/magasins/{aouina.public_id}/").json()
    assert (magasin["type"], magasin["depot_central"]) == ("magasin", True)
    assert [d["code"] for d in magasin["depots"]] == ["DEPCAS", "DEPCEN", "T01"]
    page = navigateur.get("/admin/reseau/depot/").content.decode()
    assert "DEPCEN" in page and "Dépôt central" in page
    fiche = navigateur.get(f"/admin/reseau/magasin/{aouina.pk}/change/").content.decode()
    assert "DEPCAS" in fiche
