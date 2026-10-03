"""Avoirs : retour d'articles, annulation d'une vente ou d'une commande, remboursement."""

from decimal import Decimal

import pytest
from django.contrib.auth.models import Group

from apps.stock.models import Article, PrixArticle, stock_disponible
from apps.ventes.models import Avoir, Vente
from apps.ventes.services import (
    AvoirImpossible,
    FactureImpossible,
    VenteInvalide,
    annuler_vente,
    emettre_avoir,
    enregistrer_vente,
    generer_facture,
    regler_commande,
)
from tests.conftest import peniche, tva


@pytest.fixture
def verre(tunis):
    article = Article.objects.create(
        reference="VER-A", libelle="Verre", famille="verre", sur_commande=True
    )
    PrixArticle.objects.create(
        article=article, pays=tunis.pays, prix_vente_ttc=Decimal("180.000"), tva=tva(tunis.pays, 7)
    )
    return article


def especes(montant):
    return [{"mode": "especes", "montant": Decimal(montant)}]


def vendre(tunis, monture, vendeur, quantite=2, **extra):
    return enregistrer_vente(
        magasin=tunis,
        vendeur=vendeur,
        lignes=[{"article": monture, "quantite": quantite}],
        paiements=especes(str(Decimal("289.500") * quantite)),
        **extra,
    )


def test_retour_partiel_rembourse_et_remet_en_stock(tunis, monture, creer_utilisateur):
    vendeur, responsable = creer_utilisateur("vendeur"), creer_utilisateur("responsable")
    vente = vendre(tunis, monture, vendeur)
    assert stock_disponible(tunis, monture) == 1
    ligne = vente.lignes.get()

    avoir = emettre_avoir(
        vente=vente,
        retours=[{"ligne_vente": ligne.pk, "quantite": 1}],
        motif="Ne convient pas",
        emetteur=responsable,
        mode_remboursement="especes",
    )
    assert avoir.numero.startswith("T01-A")
    assert (avoir.total_ttc, avoir.montant_rembourse) == (Decimal("289.500"), Decimal("289.500"))
    assert avoir.total_ht == Decimal("243.277")
    assert stock_disponible(tunis, monture) == 2
    vente.refresh_from_db()
    assert vente.statut == Vente.Statut.LIVREE

    with pytest.raises(AvoirImpossible, match="1 au plus"):
        emettre_avoir(
            vente=vente,
            retours=[{"ligne_vente": ligne.pk, "quantite": 2}],
            motif="x",
            emetteur=responsable,
            mode_remboursement="especes",
        )
    # Article défectueux : repris et remboursé, mais pas remis en stock. Tout est repris.
    emettre_avoir(
        vente=vente,
        retours=[{"ligne_vente": ligne.pk, "quantite": 1, "remis_en_stock": False}],
        motif="Charnière cassée",
        emetteur=responsable,
        mode_remboursement="carte",
    )
    assert stock_disponible(tunis, monture) == 2
    vente.refresh_from_db()
    assert vente.statut == Vente.Statut.ANNULEE


def test_motif_et_mode_de_remboursement_obligatoires(tunis, monture, creer_utilisateur):
    vente = vendre(tunis, monture, creer_utilisateur("vendeur"), quantite=1)
    ligne = {"ligne_vente": vente.lignes.get().pk, "quantite": 1}
    responsable = creer_utilisateur("responsable")
    with pytest.raises(AvoirImpossible, match="motif"):
        emettre_avoir(vente=vente, retours=[ligne], motif=" ", emetteur=responsable)
    with pytest.raises(AvoirImpossible, match="mode de remboursement"):
        emettre_avoir(vente=vente, retours=[ligne], motif="Erreur", emetteur=responsable)


def test_annulation_d_une_vente_facturee_corrige_la_facture(
    tunis, monture, societe, creer_utilisateur
):
    responsable = creer_utilisateur("responsable")
    vente = vendre(tunis, monture, creer_utilisateur("vendeur"), client=societe)
    facture = generer_facture(
        vente=vente, client=societe, emetteur=responsable, mode_paiement_timbre="especes"
    )
    avoir = annuler_vente(
        vente=vente, motif="Erreur de caisse", emetteur=responsable, mode_remboursement="especes"
    )
    assert (avoir.annulation, avoir.facture, avoir.client) == (True, facture, societe)
    assert avoir.total_ttc == Decimal("579.000")
    assert stock_disponible(tunis, monture) == 3
    with pytest.raises(AvoirImpossible, match="déjà annulée"):
        annuler_vente(vente=vente, motif="x", emetteur=responsable, mode_remboursement="especes")


def test_une_vente_avec_avoir_ne_se_facture_plus(tunis, monture, societe, creer_utilisateur):
    responsable = creer_utilisateur("responsable")
    vente = vendre(tunis, monture, creer_utilisateur("vendeur"))
    emettre_avoir(
        vente=vente,
        retours=[{"ligne_vente": vente.lignes.get().pk, "quantite": 1}],
        motif="Retour",
        emetteur=responsable,
        mode_remboursement="especes",
    )
    with pytest.raises(FactureImpossible, match="avoir"):
        generer_facture(
            vente=vente, client=societe, emetteur=responsable, mode_paiement_timbre="especes"
        )


def test_annulation_d_une_commande_rend_l_acompte(tunis, monture, verre, creer_utilisateur):
    vendeur, responsable = creer_utilisateur("vendeur"), creer_utilisateur("responsable")
    commande = enregistrer_vente(
        magasin=tunis,
        vendeur=vendeur,
        lignes=[{"article": monture, "quantite": 1}, {"article": verre, "quantite": 2}],
        paiements=especes("200.000"),
        commande=True,
        peniche=peniche(),
    )
    regler_commande(vente=commande, paiements=especes("50.000"), utilisateur=vendeur)
    with pytest.raises(AvoirImpossible, match="l'annuler plutôt"):
        emettre_avoir(
            vente=commande,
            retours=[{"ligne_vente": commande.lignes.first().pk, "quantite": 1}],
            motif="x",
            emetteur=responsable,
            mode_remboursement="especes",
        )
    # Même si on demande de ne rien remettre en stock, la monture n'a jamais quitté le magasin.
    avoir = annuler_vente(
        vente=commande,
        motif="Client a changé d'avis",
        emetteur=responsable,
        mode_remboursement="especes",
        remis_en_stock=False,
    )
    assert (avoir.total_ttc, avoir.montant_rembourse) == (Decimal("649.500"), Decimal("250.000"))
    assert stock_disponible(tunis, monture) == 3
    with pytest.raises(VenteInvalide, match="annulée"):
        regler_commande(vente=commande, paiements=especes("1"), utilisateur=vendeur)


def test_commande_annulee_sans_acompte_rien_a_rembourser(tunis, monture, verre, creer_utilisateur):
    commande = enregistrer_vente(
        magasin=tunis,
        vendeur=creer_utilisateur("vendeur"),
        lignes=[{"article": verre, "quantite": 2}],
        paiements=[],
        commande=True,
        peniche=peniche(),
    )
    avoir = annuler_vente(vente=commande, motif="Erreur", emetteur=creer_utilisateur("r"))
    assert (avoir.montant_rembourse, avoir.mode_remboursement) == (Decimal("0"), "")


def test_avoirs_reserves_aux_responsables(db):
    def permissions(role):
        return set(Group.objects.get(name=role).permissions.values_list("codename", flat=True))

    assert "add_avoir" in permissions("Responsable de magasin")
    assert "add_avoir" not in permissions("Vendeur")
    assert "add_avoir" not in permissions("Opticien")
    assert "view_avoir" in permissions("Comptabilité & Finance")


def test_parcours_avoir_par_l_api(tunis, monture, affecter, client_de, reseau):
    vendeur = affecter(
        "vendeur", "ventes.add_vente", "ventes.view_vente", portee="magasin", magasin=tunis
    )
    api = client_de(vendeur)
    vente = api.post(
        "/api/v1/ventes/",
        {
            "magasin": str(tunis.public_id),
            "lignes": [{"article": str(monture.public_id), "quantite": 2}],
            "paiements": [{"mode": "carte", "montant": "579.000"}],
        },
        format="json",
    ).json()
    ligne = vente["lignes"][0]
    assert (ligne["quantite_reprise"], ligne["quantite"]) == (0, 2)
    retour = {
        "vente": vente["id"],
        "lignes": [{"ligne": ligne["id"], "quantite": 1}],
        "motif": "Ne convient pas",
        "mode_remboursement": "carte",
    }
    assert api.post("/api/v1/avoirs/", retour, format="json").status_code == 403

    responsable = affecter(
        "responsable",
        "ventes.add_avoir",
        "ventes.view_avoir",
        "ventes.view_vente",
        portee="magasin",
        magasin=tunis,
    )
    gestion = client_de(responsable)
    avoir = gestion.post("/api/v1/avoirs/", retour, format="json")
    assert avoir.status_code == 201, avoir.json()
    assert (avoir.json()["montant_rembourse"], avoir.json()["vente"]) == (
        "289.500",
        vente["numero"],
    )
    relue = gestion.get(f"/api/v1/ventes/{vente['id']}/").json()
    assert relue["lignes"][0]["quantite_reprise"] == 1

    annulation = gestion.post(
        "/api/v1/avoirs/",
        {
            "vente": vente["id"],
            "annulation": True,
            "motif": "Erreur",
            "mode_remboursement": "carte",
        },
        format="json",
    )
    assert annulation.status_code == 201, annulation.json()
    assert annulation.json()["total_ttc"] == "289.500"
    assert gestion.get(f"/api/v1/ventes/{vente['id']}/").json()["statut"] == "annulee"

    ailleurs = affecter("lille", "ventes.view_avoir", portee="magasin", magasin=reseau["lille"])
    assert client_de(ailleurs).get("/api/v1/avoirs/").json()["count"] == 0
    assert Avoir.tous.count() == 2
