"""Devis d'équipement : prix figés jusqu'à la date de validité, puis encaissement en caisse."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group

from apps.crm.models import Client
from apps.optique.models import Prescription
from apps.stock.models import Article, PrixArticle
from apps.ventes.models import Devis
from apps.ventes.services import (
    DevisImpossible,
    accepter_devis,
    encaisser_devis,
    etablir_devis,
    refuser_devis,
)
from tests.conftest import tva


@pytest.fixture
def verre(tunis):
    """Verre à commander : un prix, pas de stock."""
    article = Article.objects.create(reference="VER-T", libelle="Verre progressif", famille="verre")
    PrixArticle.objects.create(
        article=article, pays=tunis.pays, prix_vente_ttc=Decimal("180.000"), tva=tva(tunis.pays, 7)
    )
    return article


@pytest.fixture
def ordonnance(tunis, societe, creer_utilisateur):
    prescription = Prescription(
        client=societe,
        type="lunettes",
        date_prescription=date(2026, 9, 1),
        prescripteur="Dr Trabelsi",
        magasin_saisie=tunis,
        saisie_par=creer_utilisateur("saisie"),
    )
    prescription.mesures = {"od": {"sphere": "-1.00"}, "og": {"sphere": "-1.25"}}
    prescription.save()
    return prescription


def devis_monture(tunis, monture, societe, auteur, **extra):
    return etablir_devis(
        magasin=tunis,
        auteur=auteur,
        client=societe,
        lignes=[{"article": monture, "quantite": 1}],
        **extra,
    )


def test_devis_avec_ordonnance_et_verres_sans_stock(
    tunis, monture, verre, societe, ordonnance, creer_utilisateur
):
    devis = etablir_devis(
        magasin=tunis,
        auteur=creer_utilisateur("opticien"),
        client=societe,
        prescription=ordonnance,
        lignes=[
            {"article": monture, "quantite": 1, "remise_pct": Decimal("10")},
            {"article": verre, "quantite": 1, "oeil": "od"},
            {"article": verre, "quantite": 1, "oeil": "og"},
        ],
    )
    assert devis.numero.startswith("T01-D")
    assert devis.statut == Devis.Statut.EN_COURS
    # 289,500 × 0,90 + 2 × 180,000
    assert devis.total_ttc == Decimal("620.550")
    assert devis.devise == "TND"
    assert sorted(devis.lignes.values_list("oeil", flat=True)) == ["", "od", "og"]
    assert devis.valable_jusqu_au - date.today() >= timedelta(days=29)


def test_ordonnance_d_un_autre_client_refusee(tunis, monture, ordonnance, creer_utilisateur):
    autre = Client.objects.create(nom="Ben Ali", prenom="Sami", magasin_origine=tunis)
    with pytest.raises(DevisImpossible, match="autre client"):
        devis_monture(tunis, monture, autre, creer_utilisateur("o"), prescription=ordonnance)


def test_encaisse_au_prix_du_devis_meme_si_le_tarif_a_change(
    tunis, monture, societe, creer_utilisateur
):
    opticien = creer_utilisateur("opticien")
    devis = devis_monture(tunis, monture, societe, opticien)
    PrixArticle.objects.filter(article=monture).update(prix_vente_ttc=Decimal("320.000"))

    with pytest.raises(DevisImpossible, match="ne couvrent pas"):
        encaisser_devis(
            devis=devis, vendeur=opticien, paiements=[{"mode": "carte", "montant": Decimal("320")}]
        )
    vente = encaisser_devis(
        devis=devis, vendeur=opticien, paiements=[{"mode": "carte", "montant": Decimal("289.500")}]
    )
    assert vente.numero.startswith("T01-T")
    assert (vente.total_ttc, vente.client) == (Decimal("289.500"), societe)
    devis.refresh_from_db()
    assert (devis.statut, devis.vente) == (Devis.Statut.ENCAISSE, vente)
    with pytest.raises(DevisImpossible, match="déjà encaissé"):
        encaisser_devis(
            devis=devis, vendeur=opticien, paiements=[{"mode": "carte", "montant": Decimal("1")}]
        )


def test_devis_expire_ni_accepte_ni_encaisse(tunis, monture, societe, creer_utilisateur):
    opticien = creer_utilisateur("opticien")
    devis = devis_monture(tunis, monture, societe, opticien)
    Devis.tous.filter(pk=devis.pk).update(valable_jusqu_au=date.today() - timedelta(days=2))
    with pytest.raises(DevisImpossible, match="expiré"):
        accepter_devis(devis=devis)
    with pytest.raises(DevisImpossible, match="expiré"):
        encaisser_devis(
            devis=devis, vendeur=opticien, paiements=[{"mode": "carte", "montant": Decimal("1")}]
        )
    with pytest.raises(DevisImpossible, match="déjà passée"):
        devis_monture(
            tunis, monture, societe, opticien, valable_jusqu_au=date.today() - timedelta(days=1)
        )


def test_devis_refuse_n_est_plus_encaissable(tunis, monture, societe, creer_utilisateur):
    opticien = creer_utilisateur("opticien")
    devis = devis_monture(tunis, monture, societe, opticien)
    accepter_devis(devis=devis)
    refuser_devis(devis=devis)
    with pytest.raises(DevisImpossible, match="déjà refusé"):
        encaisser_devis(
            devis=devis, vendeur=opticien, paiements=[{"mode": "carte", "montant": Decimal("1")}]
        )


def test_droits_des_roles_sur_les_devis(db):
    def permissions(role):
        return set(Group.objects.get(name=role).permissions.values_list("codename", flat=True))

    assert {"add_devis", "change_devis"} <= permissions("Vendeur")
    assert {"add_devis", "change_devis"} <= permissions("Opticien")
    assert "view_devis" in permissions("Comptable")
    assert "add_devis" not in permissions("Comptable")


def test_parcours_devis_par_l_api(tunis, monture, societe, ordonnance, affecter, client_de, reseau):
    vendeur = affecter(
        "vendeur",
        "ventes.view_devis",
        "ventes.add_devis",
        "ventes.change_devis",
        "ventes.add_vente",
        "ventes.view_vente",
        "crm.view_client",
        portee="magasin",
        magasin=tunis,
    )
    api = client_de(vendeur)
    corps = {
        "magasin": str(tunis.public_id),
        "client": str(societe.public_id),
        "lignes": [{"article": str(monture.public_id), "quantite": 1}],
    }
    # Le vendeur n'accède pas aux ordonnances, ni aux remises.
    avec_ordonnance = {**corps, "prescription": str(ordonnance.public_id)}
    assert api.post("/api/v1/devis/", avec_ordonnance, format="json").status_code == 403
    remise = {**corps, "lignes": [{**corps["lignes"][0], "remise_pct": "5"}]}
    assert api.post("/api/v1/devis/", remise, format="json").status_code == 403

    cree = api.post("/api/v1/devis/", corps, format="json")
    assert cree.status_code == 201, cree.json()
    devis = cree.json()
    assert (devis["total_ttc"], devis["statut"], devis["vente"]) == ("289.500", "en_cours", None)
    assert api.get("/api/v1/devis/", {"client": str(societe.public_id)}).json()["count"] == 1

    url = f"/api/v1/devis/{devis['id']}/"
    assert api.post(url + "accepter/").json()["statut"] == "accepte"
    paiement = {"paiements": [{"mode": "especes", "montant": "289.500"}]}
    ticket = api.post(url + "encaisser/", paiement, format="json")
    assert ticket.status_code == 201, ticket.json()
    assert ticket.json()["numero"].startswith("T01-T")
    assert api.get(url).json()["vente"] == ticket.json()["numero"]

    # Un opticien voit l'ordonnance du devis ; un vendeur d'un autre magasin ne voit pas le devis.
    opticien = affecter(
        "opticien",
        "ventes.view_devis",
        "ventes.add_devis",
        "crm.view_client",
        "optique.view_prescription",
        portee="magasin",
        magasin=tunis,
    )
    avec = client_de(opticien).post("/api/v1/devis/", avec_ordonnance, format="json")
    assert avec.status_code == 201, avec.json()
    assert avec.json()["prescription"]["date_prescription"] == "2026-09-01"
    assert api.get(f"/api/v1/devis/{avec.json()['id']}/").json()["prescription"] is None
    ailleurs = affecter("lille", "ventes.view_devis", portee="magasin", magasin=reseau["lille"])
    assert client_de(ailleurs).get(url).status_code == 404
