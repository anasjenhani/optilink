"""Bons de réception achat : verres des clients reçus, stock du magasin, totaux du BL."""

import datetime
from decimal import Decimal

import pytest

from apps.achats.models import BonReception, CommandeFournisseur, Fournisseur
from apps.achats.receptions import ReceptionImpossible, enregistrer_reception, lignes_a_recevoir
from apps.achats.services import etat_verres, passer_commande, verres_a_commander
from apps.stock.models import Article, MouvementStock, stock_disponible
from tests import test_achats
from tests.test_achats import commande_client

# Fixtures partagées avec les tests des commandes fournisseurs.
verre = test_achats.verre
labo = test_achats.labo

BL = datetime.date(2026, 10, 1)


def ligne(article, quantite=1, prix="50.000", **autres):
    return {
        "article": article,
        "quantite": quantite,
        "prix_achat_ht": Decimal(prix),
        "taux_remise": Decimal(autres.pop("remise", "0")),
        "taux_tva": Decimal(autres.pop("tva", "19")),
        "non_conforme": autres.pop("non_conforme", False),
        **autres,
    }


@pytest.fixture
def commande_verres(tunis, monture, verre, labo, creer_utilisateur):
    opticien = creer_utilisateur("opticien")
    vente = commande_client(tunis, monture, verre, opticien, solde=True)
    a_commander = verres_a_commander(tunis).get()
    commande = passer_commande(
        magasin=tunis,
        fournisseur=labo,
        lignes=[{"ligne_vente": a_commander.pk, "details": "Progressif 1.6 OD -2.25 add 2"}],
        auteur=opticien,
    )
    return vente, commande, opticien


def test_les_verres_commandes_recus_passent_la_commande_a_recue(
    tunis,
    verre,
    labo,
    commande_verres,
):
    vente, commande, opticien = commande_verres
    a_recevoir = list(lignes_a_recevoir(tunis, labo))
    assert [x.commande for x in a_recevoir] == [commande]

    bon = enregistrer_reception(
        magasin=tunis,
        fournisseur=labo,
        numero_bl="6007648",
        date_bl=BL,
        lignes=[ligne(verre, 2, "50.000", remise="10", tva="7", ligne_commande=a_recevoir[0].pk)],
        auteur=opticien,
    )
    assert bon.numero.startswith("T01-R")
    # 2 × 50 = 100, remise 10 % → net 90, TVA 7 % → 6,300.
    assert (bon.total_ht, bon.total_remise, bon.total_net_ht) == (
        Decimal("100.000"),
        Decimal("10.000"),
        Decimal("90.000"),
    )
    assert (bon.total_tva, bon.total_ttc) == (Decimal("6.300"), Decimal("96.300"))
    assert bon.lignes.get().designation == "Progressif 1.6 OD -2.25 add 2"
    commande.refresh_from_db()
    assert commande.statut == CommandeFournisseur.Statut.RECUE
    assert etat_verres(vente) == "recus"
    assert list(lignes_a_recevoir(tunis, labo)) == []
    # Verre commandé pour un client : il ne passe pas par le stock du magasin.
    assert not MouvementStock.tous.filter(article=verre).exists()


def test_verre_non_conforme_reste_a_recevoir(tunis, verre, labo, commande_verres):
    _, commande, opticien = commande_verres
    a_recevoir = lignes_a_recevoir(tunis, labo).get()
    lignes = [ligne(verre, 2, non_conforme=True, ligne_commande=a_recevoir.pk)]
    with pytest.raises(ReceptionImpossible, match="motif obligatoire"):
        enregistrer_reception(
            magasin=tunis,
            fournisseur=labo,
            numero_bl="A",
            date_bl=BL,
            lignes=lignes,
            auteur=opticien,
        )
    lignes = [ligne(verre, 2, non_conforme=True, motif="Mauvais axe", ligne_commande=a_recevoir.pk)]
    bon = enregistrer_reception(
        magasin=tunis, fournisseur=labo, numero_bl="A", date_bl=BL, lignes=lignes, auteur=opticien
    )
    # Le BL compte le verre livré (le fournisseur le facture) ; un bon retour le déduira.
    assert bon.total_ttc == Decimal("119.000")
    commande.refresh_from_db()
    assert commande.statut == CommandeFournisseur.Statut.ENVOYEE
    assert list(lignes_a_recevoir(tunis, labo)) == [a_recevoir]


def test_montures_en_stock_fodec_et_remise_exceptionnelle(tunis, monture, creer_utilisateur):
    auteur = creer_utilisateur("stock")
    optique = Fournisseur.objects.create(nom="Opty Gros", pays=tunis.pays, fodec=True)
    avant = stock_disponible(tunis, monture)
    bon = enregistrer_reception(
        magasin=tunis,
        fournisseur=optique,
        numero_bl="115000076",
        date_bl=BL,
        taux_remise_ex=Decimal("10"),
        lignes=[
            ligne(monture, 3, "100.000", numero_serie="SN1"),
            ligne(monture, 1, "100.000", non_conforme=True, motif="Branche rayée"),
        ],
        auteur=auteur,
    )
    assert stock_disponible(tunis, monture) == avant + 3
    # Tout le livré compte, non conforme compris (il se renvoie par un bon retour) :
    # net 400 − remise ex. 40 = 360 ; FODEC 1 % = 3,600 ; TVA 19 % de 363,600 = 69,084.
    assert (bon.remise_ex, bon.total_net_ht, bon.total_fodec) == (
        Decimal("40.000"),
        Decimal("360.000"),
        Decimal("3.600"),
    )
    assert (bon.total_tva, bon.total_ttc) == (Decimal("69.084"), Decimal("432.684"))
    with pytest.raises(ReceptionImpossible, match="déjà enregistré"):
        enregistrer_reception(
            magasin=tunis,
            fournisseur=optique,
            numero_bl="115000076",
            date_bl=BL,
            lignes=[ligne(monture)],
            auteur=auteur,
        )


def test_un_verre_de_client_ne_se_recoit_pas_sans_sa_commande(
    tunis, verre, labo, creer_utilisateur
):
    with pytest.raises(ReceptionImpossible, match="importez le bon de commande"):
        enregistrer_reception(
            magasin=tunis,
            fournisseur=labo,
            numero_bl="X",
            date_bl=BL,
            lignes=[ligne(verre)],
            auteur=creer_utilisateur("x"),
        )


def test_api_bon_de_reception_liste_et_fournisseurs(
    tunis,
    monture,
    verre,
    labo,
    commande_verres,
    affecter,
    client_de,
):
    responsable = affecter(
        "resp",
        "achats.view_bonreception",
        "achats.add_bonreception",
        "achats.view_fournisseur",
        "achats.add_fournisseur",
        "achats.change_fournisseur",
        portee="magasin",
        magasin=tunis,
    )
    client = client_de(responsable)
    a_recevoir = client.get(
        "/api/v1/bons-reception/a-recevoir/",
        {"magasin": tunis.public_id, "fournisseur": labo.public_id},
    ).json()
    assert [(x["commande"], x["quantite"], x["taux_tva"]) for x in a_recevoir] == [
        (CommandeFournisseur.objects.get().numero, 2, "7.00")
    ]
    corps = {
        "magasin": str(tunis.public_id),
        "fournisseur": str(labo.public_id),
        "numero_bl": "2026/38801",
        "date_bl": "2026-09-29",
        "lignes": [
            {
                "article": str(verre.public_id),
                "ligne_commande": a_recevoir[0]["ligne_commande"],
                "quantite": 2,
                "prix_achat_ht": "538.000",
                "taux_tva": "19",
            },
            {
                "article": str(monture.public_id),
                "quantite": 1,
                "prix_achat_ht": "40",
                "taux_tva": "19",
            },
        ],
    }
    reponse = client.post("/api/v1/bons-reception/", corps, format="json")
    assert reponse.status_code == 201, reponse.json()
    bon = reponse.json()
    assert bon["total_ttc"] == "1328.040"
    assert bon["detail_tva"] == [{"taux": "19.00", "base_ht": "1116.000", "montant_tva": "212.040"}]
    assert bon["type_bl"] == "Mixte" and bon["total_articles"] == 3

    prix = client.get(
        "/api/v1/bons-reception/derniers-prix/",
        {"magasin": tunis.public_id, "articles": str(verre.public_id)},
    ).json()
    assert prix[str(verre.public_id)]["dernier_prix_achat"] == "538.000"

    liste = client.get("/api/v1/bons-reception/", {"fournisseur": "essilor"}).json()
    assert [b["numero_bl"] for b in liste["results"]] == ["2026/38801"]
    assert liste["totaux"]["total_ttc"] == "1328.040"
    assert liste["totaux"]["total_articles"] == 3

    nouveau = client.post(
        "/api/v1/fournisseurs/",
        {"nom": "SICOM", "ville": "Tunis", "fodec": True, "fournisseur_verres": True},
        format="json",
    ).json()
    assert nouveau["code"] == labo.code + 1 and nouveau["pays"] == "TN"
    trouves = client.get("/api/v1/fournisseurs/", {"code": nouveau["code"]}).json()
    assert [f["nom"] for f in trouves["results"]] == ["SICOM"]
    modifie = client.patch(
        f"/api/v1/fournisseurs/{nouveau['id']}/", {"est_actif": False}, format="json"
    )
    assert modifie.status_code == 200
    assert client.get("/api/v1/fournisseurs/", {"nom": "sicom"}).json()["count"] == 0


def test_un_bon_d_un_autre_magasin_n_est_pas_visible(tunis, reseau, monture, affecter, client_de):
    auteur = affecter("x", "achats.view_bonreception", portee="magasin", magasin=reseau["lille"])
    optique = Fournisseur.objects.create(nom="Opty", pays=tunis.pays)
    enregistrer_reception(
        magasin=tunis,
        fournisseur=optique,
        numero_bl="1",
        date_bl=BL,
        lignes=[ligne(monture)],
        auteur=auteur,
    )
    assert BonReception.tous.count() == 1
    assert client_de(auteur).get("/api/v1/bons-reception/").json()["count"] == 0


def test_codes_des_fournisseurs(tunis):
    premier = Fournisseur.objects.create(nom="A", pays=tunis.pays)
    second = Fournisseur.objects.create(nom="B", pays=tunis.pays)
    assert second.code == premier.code + 1
    assert Article  # import utilisé par les autres tests
