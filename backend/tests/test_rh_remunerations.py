"""RH : acomptes (avances sur salaire) et primes, repris par la paie du mois."""

from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.utils import timezone

from apps.rh.models import Acompte, Employe
from apps.securite.models import Affectation, Utilisateur

from .test_rh import il_y_a_mois

ACOMPTES = "/api/v1/rh/acomptes/"
PRIMES = "/api/v1/rh/primes/"


def ce_mois():
    return timezone.localdate().replace(day=1)


@pytest.fixture
def equipe(tunis):
    def membre(nom, profil=None, **perimetre):
        utilisateur = Utilisateur.objects.create_user(nom)
        if profil:
            Affectation.objects.create(
                utilisateur=utilisateur,
                role=Group.objects.get(name=profil),
                **(perimetre or {"portee": "magasin", "magasin": tunis}),
            )
        return utilisateur

    return {
        "rh": membre("rh", "Ressources Humaines", portee="reseau"),
        "responsable": membre("responsable", "Responsable de magasin"),
        "vendeur": membre("vendeur", "Vendeur"),
    }


@pytest.fixture
def salma(tunis, equipe):
    """Vendeuse à 1 200 DT : 600 DT d'acompte possibles par mois."""
    return Employe.objects.create(
        magasin=tunis,
        utilisateur=equipe["vendeur"],
        nom="Ben Ali",
        prenom="Salma",
        poste="Vendeuse",
        date_embauche=il_y_a_mois(6),
        salaire_base=Decimal("1200.000"),
    )


def test_acompte_demande_accorde_verse(salma, equipe, client_de):
    vendeuse = client_de(equipe["vendeur"])
    reponse = vendeuse.post(
        "/api/v1/rh/mon-espace/demander-acompte/",
        {"montant": "400", "motif": "Rentrée scolaire"},
        format="json",
    )
    assert reponse.status_code == 201, reponse.json()
    acompte = reponse.json()["acomptes"][0]
    assert (acompte["statut"], acompte["mois"]) == ("demande", str(ce_mois()))

    # Le plafond (50 % du salaire) compte aussi les demandes en attente.
    trop = vendeuse.post(
        "/api/v1/rh/mon-espace/demander-acompte/", {"montant": "250"}, format="json"
    )
    assert trop.status_code == 400 and "il reste 200.000" in trop.json()["detail"]

    # Le responsable voit la demande mais ne décide pas : ce sont les RH.
    responsable = client_de(equipe["responsable"])
    url = f"{ACOMPTES}{acompte['id']}/"
    assert responsable.get(ACOMPTES).json()["results"][0]["employe_nom"] == "Salma Ben Ali"
    assert responsable.post(url + "accorder/", {}, format="json").status_code == 403

    rh = client_de(equipe["rh"])
    assert rh.post(url + "verser/", {"mode": "especes"}, format="json").status_code == 400
    assert rh.post(url + "accorder/", {}, format="json").json()["statut"] == "accorde"
    sans_ref = rh.post(url + "verser/", {"mode": "virement"}, format="json")
    assert sans_ref.status_code == 400
    verse = rh.post(url + "verser/", {"mode": "virement", "reference": "VIR-88"}, format="json")
    assert verse.json()["statut"] == "verse" and verse.json()["verse_le"] is not None
    assert rh.post(url + "annuler/").status_code == 400


def test_employe_annule_sa_demande_d_acompte(tunis, salma, equipe, client_de):
    vendeuse = client_de(equipe["vendeur"])
    demande = vendeuse.post(
        "/api/v1/rh/mon-espace/demander-acompte/", {"montant": "300"}, format="json"
    )
    acompte = demande.json()["acomptes"][0]["id"]
    url = f"/api/v1/rh/mon-espace/{acompte}/annuler-acompte/"

    # Un collègue ne retire pas la demande de Salma, même avec sa propre fiche.
    Employe.objects.create(
        magasin=tunis,
        utilisateur=equipe["responsable"],
        nom="Trabelsi",
        prenom="Karim",
        poste="Responsable",
        date_embauche=il_y_a_mois(6),
    )
    assert client_de(equipe["responsable"]).post(url).status_code == 404
    assert vendeuse.post("/api/v1/rh/mon-espace/pas-un-id/annuler-acompte/").status_code == 404

    reponse = vendeuse.post(url)
    assert reponse.status_code == 200, reponse.json()
    assert reponse.json()["acomptes"][0]["statut"] == "annule"
    assert Acompte.objects.get(public_id=acompte).statut == Acompte.Statut.ANNULE
    assert vendeuse.post(url).status_code == 400

    # Une fois accordé par les RH, l'employé ne l'annule plus.
    acomptes = vendeuse.post(
        "/api/v1/rh/mon-espace/demander-acompte/", {"montant": "300"}, format="json"
    ).json()["acomptes"]
    nouveau = next(a["id"] for a in acomptes if a["statut"] == "demande")
    client_de(equipe["rh"]).post(f"{ACOMPTES}{nouveau}/accorder/", {}, format="json")
    refus = vendeuse.post(f"/api/v1/rh/mon-espace/{nouveau}/annuler-acompte/")
    assert refus.status_code == 400 and "déjà répondu" in refus.json()["detail"]
    assert Acompte.objects.get(public_id=nouveau).statut == Acompte.Statut.ACCORDE


def test_acompte_refuse_avec_motif(salma, equipe, client_de):
    demande = client_de(equipe["responsable"]).post(
        ACOMPTES, {"employe": str(salma.public_id), "montant": "100"}, format="json"
    )
    assert demande.status_code == 201, demande.json()
    assert demande.json()["demande_par"] == "responsable"
    url = f"{ACOMPTES}{demande.json()['id']}/refuser/"
    rh = client_de(equipe["rh"])
    assert rh.post(url, {}, format="json").status_code == 400
    refuse = rh.post(url, {"commentaire": "Déjà un acompte ce mois"}, format="json")
    assert refuse.json()["statut"] == "refuse"


def test_mois_passe_refuse(salma, equipe, client_de):
    reponse = client_de(equipe["rh"]).post(
        ACOMPTES,
        {"employe": str(salma.public_id), "montant": "100", "mois": str(il_y_a_mois(1))},
        format="json",
    )
    assert reponse.status_code == 400 and "passée" in reponse.json()["detail"]


def test_prime_proposee_puis_validee(salma, equipe, client_de):
    responsable = client_de(equipe["responsable"])
    corps = {
        "employe": str(salma.public_id),
        "type": "objectif",
        "montant": "150",
        "mois": str(ce_mois()),
        "motif": "Objectif de ventes de septembre atteint",
    }
    proposee = responsable.post(PRIMES, corps, format="json")
    assert proposee.status_code == 201, proposee.json()
    prime = proposee.json()
    assert (prime["statut"], prime["type_libelle"]) == ("proposee", "Prime d'objectif (ventes)")
    url = f"{PRIMES}{prime['id']}/valider/"
    assert responsable.post(url, {}, format="json").status_code == 403
    assert client_de(equipe["rh"]).post(url, {}, format="json").json()["statut"] == "validee"

    # La vendeuse voit sa prime validée dans son espace.
    espace = client_de(equipe["vendeur"]).get("/api/v1/rh/mon-espace/").json()
    assert [p["montant"] for p in espace["primes"]] == ["150.000"]
    assert client_de(equipe["vendeur"]).post(PRIMES, corps, format="json").status_code == 403


def test_pas_de_prime_pour_soi_meme(tunis, equipe, client_de):
    karim = Employe.objects.create(
        magasin=tunis,
        utilisateur=equipe["responsable"],
        nom="Trabelsi",
        prenom="Karim",
        poste="Responsable",
        date_embauche=il_y_a_mois(24),
    )
    corps = {
        "employe": str(karim.public_id),
        "type": "rendement",
        "montant": "300",
        "mois": str(ce_mois()),
    }
    reponse = client_de(equipe["responsable"]).post(PRIMES, corps, format="json")
    assert reponse.status_code == 400 and "soi-même" in reponse.json()["detail"]


def test_recapitulatif_du_mois_pour_la_paie(tunis, salma, equipe, client_de):
    rh = client_de(equipe["rh"])
    for montant, statut in (
        ("200", "verse"),
        ("50", "accorde"),
        ("80", "refuse"),
        ("30", "demande"),
    ):
        Acompte.tous.create(
            employe=salma,
            magasin=tunis,
            montant=Decimal(montant),
            mois=ce_mois(),
            statut=statut,
            demande_par=equipe["rh"],
        )
    prime = {
        "employe": str(salma.public_id),
        "type": "fete",
        "montant": "100",
        "mois": str(ce_mois()),
    }
    numero = client_de(equipe["responsable"]).post(PRIMES, prime, format="json").json()["id"]
    rh.post(f"{PRIMES}{numero}/valider/", {}, format="json")
    client_de(equipe["responsable"]).post(PRIMES, prime | {"montant": "40"}, format="json")

    recap = rh.get(f"/api/v1/rh/recap/?mois={timezone.localdate()}").json()
    assert [(r["nom"], r["salaire_base"], r["acomptes"], r["primes"]) for r in recap] == [
        ("Salma Ben Ali", "1200.000", "250.000", "100.000")
    ]
    assert client_de(equipe["responsable"]).get("/api/v1/rh/recap/").status_code == 200
    assert client_de(equipe["vendeur"]).get("/api/v1/rh/recap/").status_code == 403
