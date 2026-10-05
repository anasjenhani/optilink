"""Dépôt central : réception et contrôle au dépôt, transferts vers les magasins, bons retour
fournisseur déduits de la facture achat ; le magasin reçoit seulement les verres commandés."""

from decimal import Decimal

import pytest

from apps.achats.factures import FactureImpossible, bons_a_facturer, enregistrer_facture
from apps.achats.models import BonRetour, Fournisseur
from apps.achats.receptions import ReceptionImpossible, enregistrer_reception, lignes_a_recevoir
from apps.achats.retours import RetourImpossible, enregistrer_retour, non_conformes_a_retourner
from apps.reseau.models import Magasin
from apps.stock.models import MouvementStock, stock_disponible
from apps.stock.transferts import TransfertImpossible, envoyer_transfert, recevoir_transfert
from tests import test_receptions
from tests.test_receptions import BL, ligne

# Fixtures partagées avec les tests des bons de réception.
verre = test_receptions.verre
labo = test_receptions.labo
commande_verres = test_receptions.commande_verres


@pytest.fixture
def depot(tunis):
    return Magasin.tous.create(
        code="DEP", nom="Dépôt central", societe=tunis.societe, pays=tunis.pays, type="depot"
    )


@pytest.fixture
def optique(tunis):
    return Fournisseur.objects.create(nom="Opty Gros", pays=tunis.pays)


@pytest.fixture
def achats(creer_utilisateur):
    return creer_utilisateur("achats")


def recevoir(magasin, fournisseur, auteur, lignes, numero_bl="BL-1"):
    return enregistrer_reception(
        magasin=magasin,
        fournisseur=fournisseur,
        numero_bl=numero_bl,
        date_bl=BL,
        lignes=lignes,
        auteur=auteur,
    )


def test_le_stock_se_recoit_au_depot_puis_part_au_magasin(tunis, depot, monture, optique, achats):
    with pytest.raises(ReceptionImpossible, match="dépôt central \\(Dépôt central\\)"):
        recevoir(tunis, optique, achats, [ligne(monture, 2, "100")])

    bon = recevoir(
        depot,
        optique,
        achats,
        [
            ligne(monture, 4, "100"),
            ligne(monture, 1, "100", non_conforme=True, motif="Branche rayée"),
        ],
    )
    # Le BL compte tout ce qui est livré ; le non conforme n'entre pas en stock.
    assert (bon.total_net_ht, stock_disponible(depot, monture)) == (Decimal("500.000"), 4)

    avant = stock_disponible(tunis, monture)
    with pytest.raises(TransfertImpossible, match="5 à envoyer, 4 en stock"):
        envoyer_transfert(
            magasin=depot,
            destination=tunis,
            lignes=[{"article": monture, "quantite": 5}],
            auteur=achats,
        )
    transfert = envoyer_transfert(
        magasin=depot,
        destination=tunis,
        lignes=[{"article": monture, "quantite": 2}, {"article": monture, "quantite": 1}],
        auteur=achats,
    )
    assert transfert.numero.startswith("DEP-TR")
    assert transfert.lignes.get().quantite == 3
    # En route : sorti du dépôt, pas encore entré au magasin.
    assert (stock_disponible(depot, monture), stock_disponible(tunis, monture)) == (1, avant)
    recevoir_transfert(transfert, auteur=achats)
    assert stock_disponible(tunis, monture) == avant + 3
    with pytest.raises(TransfertImpossible, match="déjà réceptionné"):
        recevoir_transfert(transfert, auteur=achats)


def test_bon_retour_et_facture_du_depot(tunis, depot, monture, optique, achats):
    bon = recevoir(
        depot,
        optique,
        achats,
        [
            ligne(monture, 4, "100"),
            ligne(monture, 1, "100", non_conforme=True, motif="Branche rayée"),
        ],
    )
    with pytest.raises(RetourImpossible, match="se saisissent au dépôt central"):
        enregistrer_retour(magasin=tunis, fournisseur=optique, lignes=[{}], auteur=achats)

    non_conforme = non_conformes_a_retourner(depot, optique).get()
    retour = enregistrer_retour(
        magasin=depot,
        fournisseur=optique,
        lignes=[
            {"ligne_reception": non_conforme},
            ligne(monture, 1, "100", motif="Ne se vend pas"),
        ],
        auteur=achats,
    )
    assert retour.numero.startswith("DEP-BR")
    assert (retour.total_net_ht, retour.total_ttc) == (Decimal("200.000"), Decimal("238.000"))
    # La ligne non conforme ne sort pas du stock (elle n'y était pas) ; l'autre en sort.
    assert stock_disponible(depot, monture) == 3
    assert MouvementStock.tous.filter(type="retour_fournisseur", quantite=-1).exists()
    assert not non_conformes_a_retourner(depot, optique).exists()
    with pytest.raises(RetourImpossible, match="4 à renvoyer, 3 en stock"):
        enregistrer_retour(
            magasin=depot, fournisseur=optique, lignes=[ligne(monture, 4, "100")], auteur=achats
        )

    with pytest.raises(FactureImpossible, match="se saisissent au dépôt central"):
        enregistrer_facture(
            magasin=tunis,
            fournisseur=optique,
            reference_fournisseur="F1",
            date_reference=BL,
            bons=[bon.public_id],
            auteur=achats,
        )
    facture = enregistrer_facture(
        magasin=depot,
        fournisseur=optique,
        reference_fournisseur="F1",
        date_reference=BL,
        bons=[bon.public_id],
        retours=[retour.public_id],
        timbre=Decimal("0"),
        auteur=achats,
    )
    # 500 livrés − 200 renvoyés = 300 HT ; TVA 19 % = 57.
    assert (facture.total_net_ht, facture.total_tva, facture.total_ttc) == (
        Decimal("300.000"),
        Decimal("57.000"),
        Decimal("357.000"),
    )
    retour.refresh_from_db()
    assert (retour.facture, retour.etat) == (facture, BonRetour.Etat.FACTURE)


def test_le_magasin_recoit_ses_verres_et_le_depot_les_facture(
    tunis,
    depot,
    verre,
    labo,
    commande_verres,
):
    _, commande, opticien = commande_verres
    a_recevoir = lignes_a_recevoir(tunis, labo).get()
    bon = recevoir(
        tunis, labo, opticien, [ligne(verre, 2, ligne_commande=a_recevoir.pk)], numero_bl="V1"
    )
    assert list(bons_a_facturer(depot, labo)) == [bon]
    assert list(bons_a_facturer(tunis, labo)) == [bon]
    facture = enregistrer_facture(
        magasin=depot,
        fournisseur=labo,
        reference_fournisseur="FV1",
        date_reference=BL,
        bons=[bon.public_id],
        auteur=opticien,
    )
    bon.refresh_from_db()
    assert bon.facture == facture


def test_api_transfert_et_bon_retour(affecter, client_de, tunis, depot, monture, optique, achats):
    recevoir(
        depot,
        optique,
        achats,
        [ligne(monture, 4, "100"), ligne(monture, 1, "100", non_conforme=True, motif="Rayée")],
    )
    gestionnaire = affecter(
        "gestionnaire",
        "stock.view_transfertstock",
        "stock.add_transfertstock",
        "achats.view_bonretour",
        "achats.add_bonretour",
        "achats.view_factureachat",
        "achats.add_factureachat",
        portee="societe",
        societe=tunis.societe,
    )
    vendeur = affecter(
        "vendeur",
        "stock.view_transfertstock",
        "stock.change_transfertstock",
        portee="magasin",
        magasin=tunis,
    )
    api, magasin = client_de(gestionnaire), client_de(vendeur)

    envoi = api.post(
        "/api/v1/transferts/",
        {
            "magasin": str(depot.public_id),
            "destination": str(tunis.public_id),
            "lignes": [{"article": str(monture.public_id), "quantite": 2}],
        },
        format="json",
    )
    assert envoi.status_code == 201, envoi.json()
    transfert = envoi.json()
    assert (transfert["statut"], transfert["total_articles"]) == ("envoye", 2)
    # Le magasin voit le transfert qui lui arrive, et lui seul le réceptionne.
    assert [t["numero"] for t in magasin.get("/api/v1/transferts/").json()["results"]] == [
        transfert["numero"]
    ]
    url = f"/api/v1/transferts/{transfert['id']}/recevoir/"
    assert api.post(url).status_code == 403
    recu = magasin.post(url)
    assert recu.status_code == 200, recu.json()
    assert recu.json()["statut"] == "recu"
    assert magasin.post(url).status_code == 400

    a_retourner = api.get(
        "/api/v1/bons-retour/a-retourner/",
        {"magasin": str(depot.public_id), "fournisseur": str(optique.public_id)},
    ).json()
    assert [x["motif"] for x in a_retourner] == ["Rayée"]
    retour = api.post(
        "/api/v1/bons-retour/",
        {
            "magasin": str(depot.public_id),
            "fournisseur": str(optique.public_id),
            "lignes": [{"ligne_reception": a_retourner[0]["id"]}],
        },
        format="json",
    )
    assert retour.status_code == 201, retour.json()
    assert retour.json()["total_net_ht"] == "100.000"

    a_facturer = api.get(
        "/api/v1/factures-achat/a-facturer/",
        {"magasin": str(depot.public_id), "fournisseur": str(optique.public_id)},
    ).json()
    assert [r["numero"] for r in a_facturer["retours"]] == [retour.json()["numero"]]
    apercu = api.post(
        "/api/v1/factures-achat/apercu/",
        {
            "magasin": str(depot.public_id),
            "fournisseur": str(optique.public_id),
            "bons": [b["id"] for b in a_facturer["bons"]],
            "retours": [retour.json()["id"]],
            "timbre_fiscal": "0",
        },
        format="json",
    ).json()
    assert (apercu["total_net_ht"], len(apercu["lignes"]), len(apercu["lignes_retour"])) == (
        "400.000",
        2,
        1,
    )
    refus = api.get(
        "/api/v1/factures-achat/a-facturer/",
        {"magasin": str(tunis.public_id), "fournisseur": str(optique.public_id)},
    )
    assert "dépôt central" in refus.json()["detail"]
