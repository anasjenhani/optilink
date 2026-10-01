"""Commandes de verres aux fournisseurs, liées aux commandes clients."""

from decimal import Decimal

import pytest
from django.contrib.auth.models import Group

from apps.achats.models import CommandeFournisseur, Fournisseur
from apps.achats.services import (
    CommandeFournisseurImpossible,
    annuler_commande_fournisseur,
    etat_verres,
    passer_commande,
    receptionner,
    verres_a_commander,
)
from apps.stock.models import Article, PrixArticle
from apps.ventes.services import enregistrer_vente, livrer_commande
from tests.conftest import tva


@pytest.fixture
def verre(tunis):
    article = Article.objects.create(
        reference="VER-F", libelle="Verre progressif", famille="verre", sur_commande=True
    )
    PrixArticle.objects.create(
        article=article, pays=tunis.pays, prix_vente_ttc=Decimal("180.000"), tva=tva(tunis.pays, 7)
    )
    return article


@pytest.fixture
def labo(tunis):
    return Fournisseur.objects.create(nom="Essilor Tunisie", pays=tunis.pays)


def commande_client(tunis, monture, verre, vendeur, solde=False):
    return enregistrer_vente(
        magasin=tunis,
        vendeur=vendeur,
        lignes=[{"article": monture, "quantite": 1}, {"article": verre, "quantite": 2}],
        paiements=[{"mode": "carte", "montant": Decimal("649.500" if solde else "200.000")}],
        commande=True,
    )


def test_verres_a_commander_puis_reception_et_livraison(
    tunis, monture, verre, labo, creer_utilisateur
):
    opticien = creer_utilisateur("opticien")
    vente = commande_client(tunis, monture, verre, opticien, solde=True)
    a_commander = list(verres_a_commander(tunis))
    assert [ligne.article for ligne in a_commander] == [verre]
    assert etat_verres(vente) == "a_commander"

    commande = passer_commande(
        magasin=tunis,
        fournisseur=labo,
        lignes=[{"ligne_vente": a_commander[0].pk, "details": "OD -2.25 add +2.00 / OG -1.75"}],
        auteur=opticien,
        reference_fournisseur="ESS-889",
    )
    assert commande.numero.startswith("T01-C")
    assert list(verres_a_commander(tunis)) == []
    assert etat_verres(vente) == "commandes"
    with pytest.raises(CommandeFournisseurImpossible, match="déjà commandée"):
        passer_commande(
            magasin=tunis,
            fournisseur=labo,
            lignes=[{"ligne_vente": a_commander[0].pk}],
            auteur=opticien,
        )

    receptionner(commande=commande, utilisateur=opticien)
    assert etat_verres(vente) == "recus"
    livrer_commande(vente=vente, utilisateur=opticien)
    with pytest.raises(CommandeFournisseurImpossible, match="déjà reçue"):
        receptionner(commande=commande, utilisateur=opticien)


def test_commande_fournisseur_annulee_les_verres_repassent_a_commander(
    tunis, monture, verre, labo, creer_utilisateur
):
    opticien = creer_utilisateur("opticien")
    commande_client(tunis, monture, verre, opticien)
    ligne = verres_a_commander(tunis).get()
    commande = passer_commande(
        magasin=tunis, fournisseur=labo, lignes=[{"ligne_vente": ligne.pk}], auteur=opticien
    )
    annuler_commande_fournisseur(commande=commande)
    assert list(verres_a_commander(tunis)) == [ligne]


def test_une_commande_client_d_un_autre_magasin_ne_se_commande_pas(
    tunis, monture, verre, labo, reseau, creer_utilisateur
):
    opticien = creer_utilisateur("opticien")
    commande_client(tunis, monture, verre, opticien)
    ligne = verres_a_commander(tunis).get()
    with pytest.raises(CommandeFournisseurImpossible, match="hors de ce magasin"):
        passer_commande(
            magasin=reseau["lille"],
            fournisseur=labo,
            lignes=[{"ligne_vente": ligne.pk}],
            auteur=opticien,
        )


def test_droits_des_roles_sur_les_commandes_fournisseurs(db):
    def permissions(role):
        return set(Group.objects.get(name=role).permissions.values_list("codename", flat=True))

    assert {"add_commandefournisseur", "change_commandefournisseur"} <= permissions("Opticien")
    assert "add_fournisseur" not in permissions("Opticien")
    assert "add_fournisseur" in permissions("Logisticien")
    assert "add_commandefournisseur" not in permissions("Vendeur")


def test_parcours_commande_fournisseur_par_l_api(
    tunis, monture, verre, labo, reseau, affecter, client_de, creer_utilisateur
):
    commande_client(tunis, monture, verre, creer_utilisateur("vendeur"))
    opticien = affecter(
        "opticien",
        "achats.view_fournisseur",
        "achats.view_commandefournisseur",
        "achats.add_commandefournisseur",
        "achats.change_commandefournisseur",
        portee="magasin",
        magasin=tunis,
    )
    api = client_de(opticien)
    assert [f["nom"] for f in api.get("/api/v1/fournisseurs/").json()["results"]] == [
        "Essilor Tunisie"
    ]
    a_commander = api.get(
        "/api/v1/commandes-fournisseurs/a-commander/", {"magasin": str(tunis.public_id)}
    ).json()
    assert [(v["libelle"], v["quantite"]) for v in a_commander] == [("Verre progressif", 2)]

    cree = api.post(
        "/api/v1/commandes-fournisseurs/",
        {
            "magasin": str(tunis.public_id),
            "fournisseur": str(labo.public_id),
            "reference_fournisseur": "ESS-1",
            "lignes": [{"ligne": a_commander[0]["ligne"], "details": "OD -2.25 / OG -1.75"}],
        },
        format="json",
    )
    assert cree.status_code == 201, cree.json()
    assert cree.json()["lignes"][0]["details"] == "OD -2.25 / OG -1.75"
    url = f"/api/v1/commandes-fournisseurs/{cree.json()['id']}/"
    assert api.post(url + "receptionner/").json()["statut"] == "recue"

    ailleurs = affecter(
        "lille", "achats.view_commandefournisseur", portee="magasin", magasin=reseau["lille"]
    )
    assert client_de(ailleurs).get(url).status_code == 404
    assert CommandeFournisseur.tous.count() == 1
