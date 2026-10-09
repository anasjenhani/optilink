"""Règlements fournisseurs : solder les factures achat, avances, retenue à la source, échéancier."""

from datetime import date
from decimal import Decimal

import pytest

from apps.achats.models import FactureAchat, Fournisseur
from apps.reseau.models import Magasin

DROITS = (
    "achats.view_reglementfournisseur",
    "achats.add_reglementfournisseur",
    "achats.change_reglementfournisseur",
    "achats.delete_reglementfournisseur",
)
URL = "/api/v1/reglements-fournisseurs/"


@pytest.fixture
def finance(affecter, tunis):
    return affecter("finance", *DROITS, portee="magasin", magasin=tunis)


@pytest.fixture
def api(client_de, finance):
    return client_de(finance)


@pytest.fixture
def optical(tunis):
    return Fournisseur.objects.create(nom="Optical Line Trading", pays=tunis.pays)


def facture(magasin, fournisseur, total, auteur, sequence):
    return FactureAchat.tous.create(
        magasin=magasin,
        numero=f"{magasin.code}-FA2026-{sequence:06d}",
        annee=2026,
        sequence=sequence,
        fournisseur=fournisseur,
        date_entree=date(2026, 9, sequence),
        reference_fournisseur=f"26/{sequence}",
        date_reference=date(2026, 9, sequence),
        total_ttc=Decimal(total),
        cree_par=auteur,
    )


def regler(api, tunis, fournisseur, montant, lignes=(), **autres):
    return api.post(
        URL,
        {
            "magasin": str(tunis.public_id),
            "fournisseur": str(fournisseur.public_id),
            "date_reglement": "2026-10-01",
            "mode": "virement",
            "montant": montant,
            "lignes": [{"facture": str(f.public_id), "montant": m} for f, m in lignes],
            **autres,
        },
        format="json",
    )


def situation(api, tunis, fournisseur):
    return api.get(
        URL + "situation/",
        {"magasin": str(tunis.public_id), "fournisseur": str(fournisseur.public_id)},
    ).json()


def test_reglement_avec_retenue_solde_les_factures(api, tunis, optical, finance):
    f1 = facture(tunis, optical, "1190.000", finance, 1)
    f2 = facture(tunis, optical, "500.000", finance, 2)
    assert situation(api, tunis, optical)["total_reste"] == "1690.000"

    # 1 % de retenue sur 1 690 : 16,900 gardés pour l'État, 1 673,100 versés.
    reponse = regler(
        api,
        tunis,
        optical,
        "1673.100",
        [(f1, "1190.000"), (f2, "500.000")],
        taux_retenue="1",
        retenue="16.900",
    )
    assert reponse.status_code == 201, reponse.json()
    reglement = reponse.json()
    assert reglement["numero"].startswith("T01-RF2026")
    assert (reglement["total_regle"], reglement["disponible"]) == ("1690.000", "0.000")
    assert reglement["statut"] == "debite"
    f1.refresh_from_db()
    assert f1.paiement == FactureAchat.Paiement.PAYE
    assert situation(api, tunis, optical)["factures"] == []

    # Annulé : les factures redeviennent à régler.
    assert api.delete(f"{URL}{reglement['id']}/").status_code == 204
    f1.refresh_from_db()
    assert f1.paiement == FactureAchat.Paiement.NON_PAYE


def test_avance_puis_imputation(api, tunis, optical, finance):
    avance = regler(api, tunis, optical, "300.000").json()
    assert avance["disponible"] == "300.000"
    f1 = facture(tunis, optical, "500.000", finance, 1)
    point = situation(api, tunis, optical)
    assert point["total_avances"] == "300.000"

    trop = api.post(
        f"{URL}{avance['id']}/imputer/",
        {"le": "2026-10-05", "lignes": [{"facture": str(f1.public_id), "montant": "400.000"}]},
        format="json",
    )
    assert trop.status_code == 400
    ok = api.post(
        f"{URL}{avance['id']}/imputer/",
        {"le": "2026-10-05", "lignes": [{"facture": str(f1.public_id), "montant": "300.000"}]},
        format="json",
    )
    assert ok.status_code == 200, ok.json()
    assert ok.json()["disponible"] == "0.000"
    f1.refresh_from_db()
    assert f1.paiement == FactureAchat.Paiement.PARTIEL
    assert situation(api, tunis, optical)["factures"][0]["reste"] == "200.000"

    # On ne règle pas plus que ce qui reste dû sur une facture.
    assert regler(api, tunis, optical, "250.000", [(f1, "250.000")]).status_code == 400


def test_echeancier_des_cheques_et_traites(api, tunis, optical, finance):
    f1 = facture(tunis, optical, "800.000", finance, 1)
    assert (
        regler(api, tunis, optical, "800.000", [(f1, "800.000")], mode="traite").status_code == 400
    )
    traite = regler(
        api,
        tunis,
        optical,
        "800.000",
        [(f1, "800.000")],
        mode="traite",
        reference="TR-0042",
        echeance="2026-12-31",
    ).json()
    assert traite["statut"] == "a_echoir"
    echeancier = api.get(URL, {"statut": "a_echoir"}).json()["results"]
    assert [r["reference"] for r in echeancier] == ["TR-0042"]

    assert api.post(f"{URL}{traite['id']}/debiter/", {"le": "2026-09-01"}).status_code == 400
    debite = api.post(f"{URL}{traite['id']}/debiter/", {"le": "2026-12-31"})
    assert debite.json()["statut"] == "debite"
    assert api.get(URL, {"statut": "a_echoir"}).json()["results"] == []


def test_droits_et_perimetre(affecter, client_de, tunis, optical, finance):
    lecteur = affecter(
        "responsable", "achats.view_reglementfournisseur", portee="magasin", magasin=tunis
    )
    assert regler(client_de(lecteur), tunis, optical, "100.000").status_code == 403

    lac = Magasin.tous.create(code="T02", nom="Lac", societe=tunis.societe, pays=tunis.pays)
    autre = client_de(affecter("finance-lac", *DROITS, portee="magasin", magasin=lac))
    regler(client_de(finance), tunis, optical, "100.000")
    assert autre.get(URL).json()["count"] == 0
    assert regler(autre, tunis, optical, "100.000").status_code == 400
