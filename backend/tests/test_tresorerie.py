"""Trésorerie : clôture quotidienne de la caisse, vérifiée et validée par la finance."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.utils import timezone

from apps.securite.models import Affectation, Utilisateur
from apps.tresorerie.models import ClotureCaisse, DepenseCaisse
from apps.ventes.models import Avoir, Paiement, Vente

D = Decimal


@pytest.fixture
def equipe(tunis):
    def membre(nom, profil, **perimetre):
        utilisateur = Utilisateur.objects.create_user(nom)
        Affectation.objects.create(
            utilisateur=utilisateur,
            role=Group.objects.get(name=profil),
            **(perimetre or {"portee": "magasin", "magasin": tunis}),
        )
        return utilisateur

    return {
        "caissier": membre("caissier", "Caissier"),
        "finance": membre("finance", "Comptabilité & Finance", portee="reseau"),
        "vendeur": membre("vendeur", "Vendeur"),
    }


def encaisser(magasin, caissier, *paiements, il_y_a=timedelta(0)):
    numero = f"T{Vente.tous.count() + 1}"
    total = sum(D(m) for _, m in paiements)
    vente = Vente.tous.create(
        magasin=magasin,
        numero=numero,
        annee=2026,
        sequence=Vente.tous.count() + 1,
        vendeur=caissier,
        devise="TND",
        total_ht=total,
        total_tva=0,
        total_ttc=total,
    )
    for mode, montant in paiements:
        Paiement.objects.create(
            vente=vente,
            mode=mode,
            montant=D(montant),
            recu_par=caissier,
            recu_le=timezone.now() - il_y_a,
        )
    return vente


COMPTAGE = {
    "especes_comptees": "250.000",
    "cheques_comptes": "180.000",
    "nombre_cheques_comptes": 1,
    "cartes_comptees": "320.500",
    "fond_conserve": "50.000",
}


def situation(client, magasin):
    return client.get(f"/api/v1/tresorerie/clotures/situation/?magasin={magasin.public_id}")


def cloturer(client, magasin, **comptage):
    corps = COMPTAGE | comptage | {"magasin": str(magasin.public_id)}
    return client.post("/api/v1/tresorerie/clotures/", corps, format="json")


@pytest.fixture
def journee(tunis, equipe):
    """Une journée de caisse : espèces, chèque, carte, un remboursement et une dépense."""
    caissier = equipe["caissier"]
    encaisser(tunis, caissier, ("especes", "200.000"), ("carte", "320.500"))
    vente = encaisser(tunis, caissier, ("cheque", "180.000"), ("especes", "40.000"))
    Avoir.tous.create(
        magasin=tunis,
        numero="AV1",
        annee=2026,
        sequence=1,
        vente=vente,
        motif="Retour",
        devise="TND",
        total_ht=D("15"),
        total_tva=0,
        total_ttc=D("15"),
        montant_rembourse=D("15.000"),
        mode_remboursement="especes",
        emis_par=caissier,
    )
    DepenseCaisse.tous.create(
        magasin=tunis,
        categorie="fournitures",
        motif="Produit vitres",
        montant=D("12.500"),
        payee_le=timezone.now(),
        saisie_par=caissier,
    )


def test_situation_avant_comptage(tunis, equipe, journee, client_de):
    reponse = situation(client_de(equipe["caissier"]), tunis)
    assert reponse.status_code == 200
    s = reponse.json()
    assert (s["encaisse_especes"], s["rembourse_especes"], s["depenses"]) == (
        "240.000",
        "15.000",
        "12.500",
    )
    assert s["especes_attendues"] == "212.500"
    assert (s["cheques_attendus"], s["nombre_cheques"], s["cartes_attendues"]) == (
        "180.000",
        1,
        "320.500",
    )
    assert s["debut"] is None and s["cloture_rejetee"] is None


def test_cloture_ecarts_et_journee_suivante(tunis, equipe, journee, client_de):
    client = client_de(equipe["caissier"])
    reponse = cloturer(client, tunis)
    assert reponse.status_code == 201, reponse.json()
    c = reponse.json()
    assert c["numero"].startswith("T01-CL") and c["statut"] == "envoyee"
    assert (c["ecart_especes"], c["ecart_cheques"], c["ecart_cartes"]) == (
        "37.500",
        "0.000",
        "0.000",
    )
    assert c["especes_a_remettre"] == "200.000"
    assert DepenseCaisse.tous.get().cloture.numero == c["numero"]

    # Le lendemain : le fond laissé devient le fond initial, seule la nouvelle vente compte.
    encaisser(tunis, equipe["caissier"], ("especes", "30.000"))
    s = situation(client, tunis).json()
    assert (s["fond_initial"], s["encaisse_especes"], s["depenses"]) == (
        "50.000",
        "30.000",
        "0.000",
    )
    assert s["especes_attendues"] == "80.000" and s["debut"] is not None


def test_la_finance_valide(tunis, equipe, journee, client_de):
    numero = cloturer(client_de(equipe["caissier"]), tunis).json()["id"]
    finance = client_de(equipe["finance"])
    liste = finance.get("/api/v1/tresorerie/clotures/?statut=envoyee").json()["results"]
    assert [c["id"] for c in liste] == [numero]
    reponse = finance.post(f"/api/v1/tresorerie/clotures/{numero}/valider/", {}, format="json")
    assert reponse.status_code == 200
    assert reponse.json()["statut"] == "validee" and reponse.json()["verifiee_par"] == "finance"
    deuxieme = finance.post(f"/api/v1/tresorerie/clotures/{numero}/rejeter/", {}, format="json")
    assert deuxieme.status_code == 400


def test_rejet_puis_correction(tunis, equipe, journee, client_de):
    caissier = client_de(equipe["caissier"])
    numero = cloturer(caissier, tunis).json()["id"]
    finance = client_de(equipe["finance"])
    url = f"/api/v1/tresorerie/clotures/{numero}/"
    assert finance.post(url + "rejeter/", {}, format="json").status_code == 400  # sans motif
    reponse = finance.post(
        url + "rejeter/", {"commentaire": "Recomptez les espèces"}, format="json"
    )
    assert reponse.json()["statut"] == "rejetee"

    # Tant que la clôture rejetée n'est pas corrigée, pas de nouvelle clôture.
    assert situation(caissier, tunis).json()["cloture_rejetee"] == numero
    assert cloturer(caissier, tunis).status_code == 400

    corrige = caissier.post(
        url + "corriger/",
        COMPTAGE | {"especes_comptees": "212.500", "fond_conserve": "50.000"},
        format="json",
    )
    assert corrige.status_code == 200
    assert (corrige.json()["statut"], corrige.json()["ecart_especes"]) == ("envoyee", "0.000")
    assert finance.post(url + "valider/", {}, format="json").json()["statut"] == "validee"


def test_on_ne_valide_pas_sa_propre_cloture(tunis, equipe, journee, client_de, donner_profil):
    responsable = donner_profil("resp", "Administrateur Global")
    client = client_de(responsable)
    numero = cloturer(client, tunis).json()["id"]
    reponse = client.post(f"/api/v1/tresorerie/clotures/{numero}/valider/", {}, format="json")
    assert reponse.status_code == 400
    assert "autre personne" in reponse.json()["detail"]


def test_droits(tunis, equipe, journee, client_de):
    vendeur = client_de(equipe["vendeur"])
    assert situation(vendeur, tunis).status_code == 403
    assert cloturer(vendeur, tunis).status_code == 403
    numero = cloturer(client_de(equipe["caissier"]), tunis).json()["id"]
    caissier = client_de(equipe["caissier"])
    url = f"/api/v1/tresorerie/clotures/{numero}/valider/"
    assert caissier.post(url, {}, format="json").status_code == 403


def test_fond_superieur_aux_especes(tunis, equipe, journee, client_de):
    reponse = cloturer(client_de(equipe["caissier"]), tunis, fond_conserve="900.000")
    assert reponse.status_code == 400
    assert not ClotureCaisse.tous.exists()


def test_depense_de_caisse(tunis, equipe, client_de):
    client = client_de(equipe["caissier"])
    corps = {
        "magasin_id": str(tunis.public_id),
        "categorie": "transport",
        "motif": "Livraison d'une commande",
        "montant": "8.000",
    }
    reponse = client.post("/api/v1/tresorerie/depenses/", corps, format="json")
    assert reponse.status_code == 201, reponse.json()
    assert reponse.json()["saisie_par"] == "caissier" and reponse.json()["cloture"] is None
    assert situation(client, tunis).json()["depenses"] == "8.000"
    liste = client.get("/api/v1/tresorerie/depenses/?cloture__isnull=true").json()["results"]
    assert [d["motif"] for d in liste] == ["Livraison d'une commande"]


def test_caisse_d_un_autre_magasin(reseau, tunis, equipe, client_de):
    assert situation(client_de(equipe["caissier"]), reseau["lille"]).status_code == 404


@pytest.fixture
def donner_profil(tunis):
    def _donner(nom, profil):
        utilisateur = Utilisateur.objects.create_user(nom)
        Affectation.objects.create(
            utilisateur=utilisateur, role=Group.objects.get(name=profil), portee="reseau"
        )
        return utilisateur

    return _donner


def test_corriger_ou_supprimer_une_depense_avant_la_cloture(tunis, equipe, journee, client_de):
    client = client_de(equipe["caissier"])
    corps = {
        "magasin_id": str(tunis.public_id),
        "categorie": "transport",
        "motif": "Taxi",
        "montant": "8.000",
    }
    depense = client.post("/api/v1/tresorerie/depenses/", corps, format="json").json()
    url = f"/api/v1/tresorerie/depenses/{depense['id']}/"
    corrige = client.patch(url, {"montant": "6.500", "motif": "Taxi livraison"}, format="json")
    assert corrige.status_code == 200, corrige.json()
    assert (corrige.json()["montant"], corrige.json()["motif"]) == ("6.500", "Taxi livraison")
    assert client.delete(url).status_code == 204
    assert not DepenseCaisse.tous.filter(public_id=depense["id"]).exists()

    # Une fois la caisse clôturée, la dépense fait partie de la clôture.
    depense = client.post("/api/v1/tresorerie/depenses/", corps, format="json").json()
    assert cloturer(client, tunis).status_code == 201
    url = f"/api/v1/tresorerie/depenses/{depense['id']}/"
    refus = client.patch(url, {"montant": "1.000"}, format="json")
    assert refus.status_code == 400 and "clôture" in refus.json()["detail"]
    assert client.delete(url).status_code == 400
