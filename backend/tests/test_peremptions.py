"""Péremption des lentilles : dates saisies à la réception, suivies par les transferts, fixées
par l'inventaire pour le stock d'avant."""

import datetime
from decimal import Decimal

import pytest

from apps.achats.models import Fournisseur
from apps.achats.receptions import enregistrer_reception
from apps.reseau.models import Magasin
from apps.stock.inventaires import compter, ouvrir_inventaire, terminer_comptage, valider_inventaire
from apps.stock.models import Article, Lentille, MouvementStock
from apps.stock.peremptions import peremptions
from apps.stock.transferts import envoyer_transfert, recevoir_transfert

FIN_2026, MI_2027 = datetime.date(2026, 12, 31), datetime.date(2027, 6, 30)
NOVEMBRE = datetime.date(2026, 11, 1)


def _lentille(reference):
    article = Article.objects.create(reference=reference, libelle=reference, famille="lentille")
    Lentille.objects.create(article=article, renouvellement="mensuelle")
    return article


@pytest.fixture
def depot(tunis):
    return Magasin.tous.create(
        code="DEP", nom="Dépôt central", societe=tunis.societe, pays=tunis.pays, type="depot"
    )


def _recevoir(depot, article, quantite, peremption, bl, auteur):
    enregistrer_reception(
        magasin=depot,
        fournisseur=Fournisseur.objects.get_or_create(nom="SICOM", pays=depot.pays)[0],
        numero_bl=bl,
        date_bl=datetime.date(2026, 10, 1),
        lignes=[
            {
                "article": article,
                "quantite": quantite,
                "prix_achat_ht": Decimal("10"),
                "taux_remise": Decimal("0"),
                "taux_tva": Decimal("19"),
                "non_conforme": False,
                "date_peremption": peremption,
            }
        ],
        auteur=auteur,
    )


def _resume(magasin):
    return [
        (r["article"].reference, r["etat"], [(lot["date"], lot["quantite"]) for lot in r["lots"]])
        for r in peremptions(magasin, NOVEMBRE)
    ]


def test_dates_suivies_de_la_reception_au_magasin(tunis, depot, creer_utilisateur):
    auteur = creer_utilisateur("stock")
    biofinity = _lentille("LEN-000314")
    _recevoir(depot, biofinity, 6, FIN_2026, "BL1", auteur)
    _recevoir(depot, biofinity, 4, MI_2027, "BL2", auteur)
    assert _resume(depot) == [("LEN-000314", "proche", [(FIN_2026, 6), (MI_2027, 4)])]

    # Le dépôt envoie d'abord les boîtes qui périment le plus tôt.
    transfert = envoyer_transfert(
        magasin=depot,
        destination=tunis,
        lignes=[{"article": biofinity, "quantite": 7}],
        auteur=auteur,
    )
    assert transfert.lignes.get().peremptions == [
        {"date": "2026-12-31", "quantite": 6},
        {"date": "2027-06-30", "quantite": 1},
    ]
    recevoir_transfert(transfert, auteur=auteur)
    assert _resume(depot) == [("LEN-000314", "ok", [(MI_2027, 3)])]
    assert _resume(tunis) == [("LEN-000314", "proche", [(FIN_2026, 6), (MI_2027, 1)])]

    # Une vente part des boîtes les plus anciennes.
    MouvementStock.tous.create(magasin=tunis, article=biofinity, quantite=-6, type="vente")
    assert _resume(tunis) == [("LEN-000314", "ok", [(MI_2027, 1)])]


def test_le_stock_repris_se_date_a_l_inventaire(tunis, creer_utilisateur):
    auteur = creer_utilisateur("stock")
    proclear = _lentille("LEN-000233")
    MouvementStock.tous.create(magasin=tunis, article=proclear, quantite=3, type="ajustement")
    assert _resume(tunis) == [("LEN-000233", "inconnue", [(None, 3)])]

    inventaire = ouvrir_inventaire(magasin=tunis, auteur=auteur, famille="lentille")
    compter(inventaire, proclear, quantite=3, date_peremption=datetime.date(2026, 9, 30))
    terminer_comptage(inventaire, auteur=auteur)
    valider_inventaire(inventaire, auteur=auteur, observation="Lentilles")
    assert _resume(tunis) == [("LEN-000233", "perimee", [(datetime.date(2026, 9, 30), 3)])]


def test_saisie_de_la_date_au_comptage(tunis, monture, affecter, client_de):
    proclear = _lentille("LEN-000233")
    api = client_de(
        affecter(
            "resp",
            "stock.view_inventaire",
            "stock.add_inventaire",
            "stock.change_inventaire",
            portee="magasin",
            magasin=tunis,
        )
    )
    inventaire = api.post(
        "/api/v1/inventaires/", {"magasin": str(tunis.public_id)}, format="json"
    ).json()
    url = f"/api/v1/inventaires/{inventaire['id']}/compter/"
    reponse = api.post(
        url, {"article": str(proclear.public_id), "quantite": 2, "date_peremption": "2027-01-31"}
    )
    assert reponse.status_code == 200, reponse.json()
    ligne = next(lig for lig in reponse.json()["lignes"] if lig["reference"] == "LEN-000233")
    assert (ligne["quantite_comptee"], ligne["date_peremption"]) == (2, "2027-01-31")
    # Recompter sans date garde celle saisie.
    reponse = api.post(url, {"article": str(proclear.public_id), "quantite": 1})
    ligne = next(lig for lig in reponse.json()["lignes"] if lig["reference"] == "LEN-000233")
    assert (ligne["quantite_comptee"], ligne["date_peremption"]) == (3, "2027-01-31")
    refus = api.post(
        url, {"article": str(monture.public_id), "quantite": 1, "date_peremption": "2027-01-31"}
    )
    assert "lentilles" in refus.json()["detail"]


def test_api(tunis, affecter, client_de, creer_utilisateur):
    proclear = _lentille("LEN-000233")
    MouvementStock.tous.create(magasin=tunis, article=proclear, quantite=2, type="ajustement")
    api = client_de(affecter("stock", "stock.view_article", portee="magasin", magasin=tunis))
    reponse = api.get("/api/v1/peremptions-lentilles/", {"magasin": str(tunis.public_id)})
    assert reponse.status_code == 200, reponse.json()
    assert reponse.json() == [
        {
            "article": str(proclear.public_id),
            "reference": "LEN-000233",
            "libelle": "LEN-000233",
            "stock": 2,
            "prochaine": None,
            "etat": "inconnue",
            "lots": [{"date": None, "quantite": 2}],
        }
    ]
    assert api.get("/api/v1/peremptions-lentilles/").status_code == 400
