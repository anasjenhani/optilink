"""RH : fiches employés, présence du jour, demandes de congé et solde."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.utils import timezone

from apps.rh import services
from apps.rh.models import DemandeConge, Employe
from apps.securite.models import Affectation, Utilisateur

CONGES = "/api/v1/rh/conges/"


def il_y_a_mois(n):
    """Le 1er du mois, ``n`` mois plus tôt : exactement ``n`` mois travaillés aujourd'hui."""
    aujourd_hui = timezone.localdate()
    mois = aujourd_hui.year * 12 + aujourd_hui.month - 1 - n
    return date(mois // 12, mois % 12 + 1, 1)


def lundi_prochain(semaines=1):
    aujourd_hui = timezone.localdate()
    return aujourd_hui + timedelta(days=7 * semaines - aujourd_hui.weekday())


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
    """Vendeuse embauchée il y a 6 mois, reliée à son compte : 6 jours acquis."""
    return Employe.objects.create(
        magasin=tunis,
        utilisateur=equipe["vendeur"],
        nom="Ben Ali",
        prenom="Salma",
        poste="Vendeuse",
        date_embauche=il_y_a_mois(6),
    )


def test_fiche_employe_et_matricule(tunis, equipe, client_de):
    client = client_de(equipe["rh"])
    corps = {
        "magasin": str(tunis.public_id),
        "nom": "Trabelsi",
        "prenom": "Karim",
        "poste": "Opticien",
        "date_embauche": str(il_y_a_mois(12)),
        "solde_conges_initial": "3.0",
        "utilisateur": "responsable",
    }
    reponse = client.post("/api/v1/rh/employes/", corps, format="json")
    assert reponse.status_code == 201, reponse.json()
    fiche = reponse.json()
    assert fiche["matricule"] == "T01-E001"
    assert fiche["solde"] == {
        "acquis": "15.0",
        "pris": "0.0",
        "en_attente": "0.0",
        "disponible": "15.0",
    }
    deuxieme = client.post("/api/v1/rh/employes/", corps | {"utilisateur": None}, format="json")
    assert deuxieme.json()["matricule"] == "T01-E002"
    responsable = client_de(equipe["responsable"])
    assert responsable.post("/api/v1/rh/employes/", corps, format="json").status_code == 403


def test_jours_ouvrables():
    # Du lundi 5 au lundi 12 octobre 2026 : le dimanche 11 ne compte pas.
    assert services.jours_ouvrables(date(2026, 10, 5), date(2026, 10, 12)) == 7


def test_l_employe_demande_le_responsable_accepte(salma, equipe, client_de):
    vendeuse = client_de(equipe["vendeur"])
    espace = vendeuse.get("/api/v1/rh/mon-espace/").json()
    assert espace["employe"]["solde"]["disponible"] == "6.0"

    debut = lundi_prochain()
    corps = {"type": "annuel", "debut": str(debut), "fin": str(debut + timedelta(days=3))}
    reponse = vendeuse.post("/api/v1/rh/mon-espace/demander/", corps, format="json")
    assert reponse.status_code == 201, reponse.json()
    solde = reponse.json()["employe"]["solde"]
    assert (solde["en_attente"], solde["disponible"]) == ("4.0", "2.0")

    # La vendeuse n'a pas accès aux congés des autres.
    assert vendeuse.get(CONGES).status_code == 403

    responsable = client_de(equipe["responsable"])
    attente = responsable.get(CONGES + "?statut=demandee").json()["results"]
    assert [(d["employe_nom"], d["jours"]) for d in attente] == [("Salma Ben Ali", "4.0")]
    url = f"{CONGES}{attente[0]['id']}/"
    assert responsable.post(url + "refuser/", {}, format="json").status_code == 400
    accepte = responsable.post(url + "accepter/", {}, format="json")
    assert accepte.json()["statut"] == "acceptee"
    assert accepte.json()["decidee_par"] == "responsable"
    solde = services.solde(salma)
    assert (solde["pris"], solde["disponible"]) == (Decimal("4.0"), Decimal("2.0"))


def test_solde_insuffisant_et_chevauchement(salma, equipe, client_de):
    vendeuse = client_de(equipe["vendeur"])
    debut = lundi_prochain()
    trop = {"type": "annuel", "debut": str(debut), "fin": str(debut + timedelta(days=13))}
    reponse = vendeuse.post("/api/v1/rh/mon-espace/demander/", trop, format="json")
    assert reponse.status_code == 400 and "Solde insuffisant" in reponse.json()["detail"]

    # Un congé maladie ne puise pas dans le solde, mais deux congés ne se chevauchent pas.
    maladie = trop | {"type": "maladie"}
    assert (
        vendeuse.post("/api/v1/rh/mon-espace/demander/", maladie, format="json").status_code == 201
    )
    un_jour = {"type": "annuel", "debut": str(debut), "fin": str(debut)}
    reponse = vendeuse.post("/api/v1/rh/mon-espace/demander/", un_jour, format="json")
    assert reponse.status_code == 400 and "couvre déjà" in reponse.json()["detail"]


def test_on_ne_decide_pas_de_ses_propres_conges(tunis, equipe, client_de):
    karim = Employe.objects.create(
        magasin=tunis,
        utilisateur=equipe["responsable"],
        nom="Trabelsi",
        prenom="Karim",
        poste="Responsable",
        date_embauche=il_y_a_mois(12),
    )
    client = client_de(equipe["responsable"])
    debut = lundi_prochain()
    corps = {
        "employe": str(karim.public_id),
        "type": "annuel",
        "debut": str(debut),
        "fin": str(debut),
    }
    demande = client.post(CONGES, corps, format="json").json()
    reponse = client.post(f"{CONGES}{demande['id']}/accepter/", {}, format="json")
    assert reponse.status_code == 400 and "propres congés" in reponse.json()["detail"]
    rh = client_de(equipe["rh"])
    assert rh.post(f"{CONGES}{demande['id']}/accepter/", {}, format="json").status_code == 200


def test_annulation(salma, equipe, client_de):
    vendeuse = client_de(equipe["vendeur"])
    debut = lundi_prochain()
    corps = {"type": "annuel", "debut": str(debut), "fin": str(debut + timedelta(days=1))}
    demande = vendeuse.post("/api/v1/rh/mon-espace/demander/", corps, format="json").json()
    numero = demande["conges"][0]["id"]
    reponse = vendeuse.post(f"/api/v1/rh/mon-espace/{numero}/annuler/")
    assert reponse.status_code == 200
    assert reponse.json()["conges"][0]["statut"] == "annulee"
    assert reponse.json()["employe"]["solde"]["disponible"] == "6.0"

    # Un congé accepté et commencé ne s'annule plus.
    commence = DemandeConge.tous.create(
        employe=salma,
        magasin=salma.magasin,
        type="annuel",
        debut=timezone.localdate(),
        fin=timezone.localdate(),
        jours=1,
        statut="acceptee",
        demandee_par=equipe["vendeur"],
    )
    reponse = vendeuse.post(f"/api/v1/rh/mon-espace/{commence.public_id}/annuler/")
    assert reponse.status_code == 400


def test_feuille_de_presence(tunis, salma, equipe, client_de):
    autre = Employe.objects.create(
        magasin=tunis, nom="Mejri", prenom="Amine", poste="Opticien", date_embauche=il_y_a_mois(3)
    )
    aujourd_hui = timezone.localdate()
    DemandeConge.tous.create(
        employe=autre,
        magasin=tunis,
        type="maladie",
        debut=aujourd_hui,
        fin=aujourd_hui,
        jours=1,
        statut="acceptee",
        demandee_par=equipe["rh"],
    )
    client = client_de(equipe["responsable"])
    url = f"/api/v1/rh/presence/?magasin={tunis.public_id}&date={aujourd_hui}"
    feuille = {ligne["nom"]: ligne for ligne in client.get(url).json()}
    assert feuille["Amine Mejri"]["conge"] == "Congé maladie"
    assert feuille["Salma Ben Ali"]["pointage"] is None

    corps = {
        "magasin": str(tunis.public_id),
        "date": str(aujourd_hui),
        "lignes": [
            {"employe": str(salma.public_id), "statut": "retard", "arrivee": "09:25"},
        ],
    }
    reponse = client.post("/api/v1/rh/presence/", corps, format="json")
    assert reponse.status_code == 200, reponse.json()
    ligne = next(x for x in reponse.json() if x["nom"] == "Salma Ben Ali")
    assert ligne["pointage"]["statut"] == "retard" and ligne["pointage"]["arrivee"] == "09:25:00"

    # Nouvelle saisie du même jour : la ligne est remplacée, pas doublée.
    corps["lignes"][0] = {"employe": str(salma.public_id), "statut": "present"}
    client.post("/api/v1/rh/presence/", corps, format="json")
    assert salma.pointages.count() == 1 and salma.pointages.get().statut == "present"

    en_conge = corps | {"lignes": [{"employe": str(autre.public_id), "statut": "present"}]}
    assert client.post("/api/v1/rh/presence/", en_conge, format="json").status_code == 400
    demain = corps | {"date": str(aujourd_hui + timedelta(days=1))}
    assert client.post("/api/v1/rh/presence/", demain, format="json").status_code == 400
    vendeur = client_de(equipe["vendeur"])
    assert vendeur.get(url).status_code == 403


def test_employe_d_un_autre_magasin(reseau, salma, equipe, client_de):
    lille = reseau["lille"]
    ailleurs = Employe.tous.create(
        magasin=lille, nom="Martin", prenom="Paul", poste="Vendeur", date_embauche=il_y_a_mois(2)
    )
    responsable = client_de(equipe["responsable"])
    noms = [e["nom"] for e in responsable.get("/api/v1/rh/employes/").json()]
    assert noms == ["Ben Ali"]
    corps = {
        "employe": str(ailleurs.public_id),
        "type": "maladie",
        "debut": "2026-11-02",
        "fin": "2026-11-02",
    }
    assert responsable.post(CONGES, corps, format="json").status_code == 400
    assert client_de(equipe["vendeur"]).get("/api/v1/rh/mon-espace/").status_code == 200
    assert client_de(equipe["rh"]).get("/api/v1/rh/mon-espace/").status_code == 404
