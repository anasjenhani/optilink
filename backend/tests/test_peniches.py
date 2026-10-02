"""Péniches : chaque commande est rangée dans un bac numéroté du magasin jusqu'à sa livraison."""

from decimal import Decimal

import pytest

from apps.stock.models import Article, PrixArticle
from apps.ventes.services import VenteInvalide, annuler_vente, enregistrer_vente, livrer_commande
from tests.conftest import recevoir_verres, tva


@pytest.fixture
def verre(tunis):
    article = Article.objects.create(
        reference="VER-P", libelle="Verre", famille="verre", sur_commande=True
    )
    PrixArticle.objects.create(
        article=article, pays=tunis.pays, prix_vente_ttc=Decimal("100.000"), tva=tva(tunis.pays, 7)
    )
    return article


@pytest.fixture
def commander(tunis, verre, creer_utilisateur):
    vendeur = creer_utilisateur("vendeur")

    def _commander(**extra):
        return enregistrer_vente(
            magasin=tunis,
            vendeur=vendeur,
            lignes=[{"article": verre, "quantite": 2}],
            paiements=[],
            commande=True,
            **extra,
        )

    return _commander


def test_le_vendeur_saisit_une_peniche_libre(commander):
    assert commander(peniche=17).peniche == 17
    with pytest.raises(VenteInvalide, match="Saisir le numéro de la péniche"):
        commander()
    with pytest.raises(VenteInvalide, match="péniche 17 contient déjà"):
        commander(peniche=17)
    with pytest.raises(VenteInvalide, match="de 1 à 200"):
        commander(peniche=201)
    with pytest.raises(VenteInvalide, match="de 1 à 200"):
        commander(peniche=0)


def test_peniche_liberee_a_la_livraison_et_a_l_annulation(
    tunis, monture, commander, creer_utilisateur
):
    responsable = creer_utilisateur("responsable")
    premiere, seconde = commander(peniche=1), commander(peniche=2)
    recevoir_verres(premiere, responsable)
    livrer_commande(
        vente=premiere,
        utilisateur=responsable,
        paiements=[{"mode": "especes", "montant": Decimal("200.000")}],
    )
    annuler_vente(vente=seconde, motif="client parti", emetteur=responsable)
    premiere.refresh_from_db()
    assert premiere.peniche == 1  # le numéro reste dans l'historique de la vente
    assert [commander(peniche=1).peniche, commander(peniche=2).peniche] == [1, 2]
    # Une vente remise tout de suite ne prend pas de péniche.
    vente = enregistrer_vente(
        magasin=tunis,
        vendeur=responsable,
        lignes=[{"article": monture, "quantite": 1}],
        paiements=[{"mode": "especes", "montant": Decimal("289.500")}],
        peniche=3,
    )
    assert vente.peniche is None


def test_nombre_de_peniches_par_magasin(tunis, commander):
    tunis.nombre_peniches = 50
    tunis.save()
    with pytest.raises(VenteInvalide, match="de 1 à 50"):
        commander(peniche=51)


def test_peniche_par_l_api(tunis, verre, affecter, client_de):
    vendeur = affecter(
        "vendeur", "ventes.add_vente", "ventes.view_vente", portee="magasin", magasin=tunis
    )
    api = client_de(vendeur)
    corps = {
        "magasin": str(tunis.public_id),
        "lignes": [{"article": str(verre.public_id), "quantite": 2}],
        "paiements": [],
        "commande": True,
        "peniche": 42,
    }
    cree = api.post("/api/v1/ventes/", corps, format="json")
    assert cree.status_code == 201, cree.json()
    assert cree.json()["peniche"] == 42
    assert api.post("/api/v1/ventes/", corps, format="json").status_code == 400
    trouvees = api.get("/api/v1/ventes/", {"peniche": 42}).json()["results"]
    assert [v["numero"] for v in trouvees] == [cree.json()["numero"]]


def test_la_commande_ouvre_sa_propre_transaction(commander, monkeypatch):
    # Le verrou sur le magasin (select_for_update) exige une transaction ouverte par la vente
    # elle-même, pas seulement celle qui entoure chaque test.
    from django.db import connection

    from apps.ventes import services

    verifier = services._verifier_peniche
    profondeurs = []

    def espion(magasin, peniche):
        profondeurs.append(len(connection.savepoint_ids))
        return verifier(magasin, peniche)

    monkeypatch.setattr(services, "_verifier_peniche", espion)
    avant = len(connection.savepoint_ids)
    commander(peniche=1)
    assert profondeurs == [avant + 1]
