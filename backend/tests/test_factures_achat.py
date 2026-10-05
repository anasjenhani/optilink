"""Factures achat : regrouper les BL d'un fournisseur, totaux, contrôles et droits."""

from datetime import date
from decimal import Decimal

import pytest

from apps.achats.models import BonReception, FactureAchat, Fournisseur
from apps.achats.receptions import enregistrer_reception


@pytest.fixture
def optical(tunis):
    return Fournisseur.objects.create(nom="Optical Line Trading", pays=tunis.pays)


@pytest.fixture
def comptable(affecter, tunis):
    return affecter(
        "comptable",
        "achats.view_factureachat",
        "achats.add_factureachat",
        portee="magasin",
        magasin=tunis,
    )


@pytest.fixture
def api(client_de, comptable):
    return client_de(comptable)


def recevoir(tunis, fournisseur, monture, auteur, numero_bl, prix, quantite=1, remise="20"):
    return enregistrer_reception(
        magasin=tunis,
        fournisseur=fournisseur,
        numero_bl=numero_bl,
        date_bl=date(2026, 9, 11),
        lignes=[
            {
                "article": monture,
                "quantite": quantite,
                "prix_achat_ht": Decimal(prix),
                "taux_remise": Decimal(remise),
                "taux_tva": Decimal("19"),
                "non_conforme": False,
                "motif": "",
            }
        ],
        auteur=auteur,
    )


def saisie(tunis, fournisseur, bons, **autres):
    return {
        "magasin": str(tunis.public_id),
        "fournisseur": str(fournisseur.public_id),
        "reference_fournisseur": "26/00487",
        "date_reference": "2026-08-10",
        "bons": [str(b.public_id) for b in bons],
        **autres,
    }


def test_facture_regroupe_les_bl_et_ajoute_le_timbre(api, tunis, optical, monture, comptable):
    bl1 = recevoir(tunis, optical, monture, comptable, "26/00426", "411.497")
    bl2 = recevoir(tunis, optical, monture, comptable, "26/00427", "408.417", quantite=2)
    autre = recevoir(
        tunis,
        Fournisseur.objects.create(nom="Autre", pays=tunis.pays),
        monture,
        comptable,
        "9",
        "1",
    )

    a_facturer = api.get(
        "/api/v1/factures-achat/a-facturer/",
        {"magasin": str(tunis.public_id), "fournisseur": str(optical.public_id)},
    ).json()
    assert [b["numero_bl"] for b in a_facturer["bons"]] == ["26/00426", "26/00427"]
    assert a_facturer["timbre_fiscal"] == "1.000"

    apercu = api.post(
        "/api/v1/factures-achat/apercu/", saisie(tunis, optical, [bl1, bl2]), format="json"
    ).json()
    # 411,497 + 2 × 408,417 = 1228,331 HT ; remise 20 % ; TVA 19 % ; timbre 1.
    assert (apercu["total_ht"], apercu["total_remise"], apercu["total_net_ht"]) == (
        "1228.331",
        "245.666",
        "982.665",
    )
    assert apercu["total_tva"] == "186.707"
    assert apercu["total_ttc"] == "1170.372"
    assert {"taux": "19.00", "base_ht": "982.665", "montant_tva": "186.707"} in apercu["detail_tva"]
    assert len(apercu["lignes"]) == 2 and apercu["lignes"][1]["montant_remise"] == "163.367"

    reponse = api.post("/api/v1/factures-achat/", saisie(tunis, optical, [bl1, bl2]), format="json")
    assert reponse.status_code == 201, reponse.json()
    facture = reponse.json()
    assert facture["numero"].startswith("T01-FA2026-")
    assert facture["total_ttc"] == "1170.372" and facture["paiement_libelle"] == "Non payé"
    assert [b["numero_bl"] for b in facture["bons"]] == ["26/00426", "26/00427"]
    bl1.refresh_from_db()
    assert (bl1.etat, bl1.numero_facture) == ("facture", "26/00487")

    # Un BL déjà facturé ne se refacture pas ; la même facture fournisseur non plus.
    deux_fois = api.post("/api/v1/factures-achat/", saisie(tunis, optical, [bl1]), format="json")
    assert "déjà saisie" in deux_fois.json()["detail"]
    deja = api.post(
        "/api/v1/factures-achat/",
        saisie(tunis, optical, [bl1], reference_fournisseur="26/00999"),
        format="json",
    )
    assert "déjà facturé" in deja.json()["detail"]
    # Un BL d'un autre fournisseur est refusé.
    melange = api.post(
        "/api/v1/factures-achat/",
        saisie(tunis, optical, [autre], reference_fournisseur="X"),
        format="json",
    )
    assert "n'est pas un BL de Optical Line Trading" in melange.json()["detail"]
    assert FactureAchat.objects.count() == 1


def test_remise_frais_et_ajustement(api, tunis, optical, monture, comptable):
    bl = recevoir(tunis, optical, monture, comptable, "BL-1", "1000", remise="0")
    reponse = api.post(
        "/api/v1/factures-achat/",
        saisie(
            tunis,
            optical,
            [bl],
            taux_remise_ex="10",
            frais_supplementaires="7",
            timbre_fiscal="0",
            ajustement="-0.010",
        ),
        format="json",
    )
    facture = reponse.json()
    # Net 1000 − 10 % = 900 ; TVA 171 ; + 7 de frais − 0,010 d'ajustement.
    assert (facture["remise_ex"], facture["total_net_ht"], facture["total_tva"]) == (
        "100.000",
        "900.000",
        "171.000",
    )
    assert facture["total_ttc"] == "1077.990"


def test_droits(client_de, affecter, tunis, optical, monture, comptable):
    bl = recevoir(tunis, optical, monture, comptable, "BL-1", "10")
    vendeur = client_de(
        affecter("vendeur", "achats.view_factureachat", portee="magasin", magasin=tunis)
    )
    reponse = vendeur.post("/api/v1/factures-achat/", saisie(tunis, optical, [bl]), format="json")
    assert reponse.status_code == 403
    assert BonReception.objects.get(pk=bl.pk).facture is None
