"""Garde-fous posés dans PostgreSQL lui-même : Row-Level Security et journaux en ajout seul.

Ces tests contournent volontairement l'ORM (SQL brut, manager ``tous``) : c'est la base qui doit
refuser. Ils ne s'exécutent que sur PostgreSQL, avec un compte non super-utilisateur.
"""

import pytest
from auditlog.models import LogEntry
from django.db import DatabaseError, connection, transaction

from apps.reseau.models import Magasin
from apps.securite.models import EvenementSecurite
from core import rls

pytestmark = pytest.mark.skipif(
    connection.vendor != "postgresql", reason="garde-fous propres à PostgreSQL"
)


@pytest.fixture(autouse=True)
def perimetre_efface(db):
    yield
    rls.effacer()


def codes_visibles(table="reseau_magasin", colonne="code"):
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT {colonne} FROM {table} ORDER BY 1")
        return [ligne[0] for ligne in cursor.fetchall()]


def test_le_compte_applicatif_n_echappe_pas_a_la_rls(db):
    with connection.cursor() as cursor:
        cursor.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        assert cursor.fetchone() == (False, False)


def test_la_base_ne_montre_que_les_mouvements_du_perimetre(reseau):
    from apps.stock.models import Article, MouvementStock

    article = Article.objects.create(
        reference="P", libelle="P", famille="monture", prix_vente_ttc=10
    )
    for magasin in reseau.values():
        if isinstance(magasin, Magasin):
            MouvementStock.tous.create(
                magasin=magasin, article=article, quantite=1, type="reception"
            )

    def visibles():
        return codes_visibles(
            "stock_mouvementstock m JOIN reseau_magasin g ON g.id = m.magasin_id", "g.code"
        )

    rls.poser({reseau["lille"].id})
    assert visibles() == ["M01"]
    assert MouvementStock.tous.count() == 1

    rls.poser(None)
    assert visibles() == ["M01", "M02", "M03"]

    rls.poser(frozenset())
    assert visibles() == []

    rls.effacer()
    assert visibles() == ["M01", "M02", "M03"]


def test_magasins_lisibles_mais_modifiables_dans_le_perimetre_seulement(reseau):
    rls.poser({reseau["lille"].id})
    # Lecture ouverte : un client partagé pointe vers un magasin d'origine hors périmètre.
    assert codes_visibles() == ["M01", "M02", "M03"]
    with connection.cursor() as cursor:
        cursor.execute("UPDATE reseau_magasin SET nom = 'x'")
        assert cursor.rowcount == 1
    with pytest.raises(DatabaseError, match="row-level security"), transaction.atomic():
        Magasin.tous.create(code="M09", nom="Hors", region=reseau["nord"])


def test_ventes_et_lignes_cloisonnees(reseau):
    from apps.stock.models import Article, MouvementStock

    article = Article.objects.create(
        reference="A", libelle="A", famille="monture", prix_vente_ttc=10
    )
    for magasin in (reseau["lille"], reseau["nice"]):
        MouvementStock.tous.create(magasin=magasin, article=article, quantite=3, type="reception")

    rls.poser({reseau["nice"].id})
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM stock_mouvementstock")
        assert cursor.fetchone()[0] == 1
        cursor.execute("SELECT magasin_id FROM stock_mouvementstock")
        assert cursor.fetchone()[0] == reseau["nice"].id


def test_ecrire_hors_perimetre_est_refuse(reseau):
    from apps.stock.models import Article, MouvementStock

    article = Article.objects.create(
        reference="B", libelle="B", famille="monture", prix_vente_ttc=10
    )
    rls.poser({reseau["lille"].id})
    with pytest.raises(DatabaseError, match="row-level security"), transaction.atomic():
        MouvementStock.tous.create(
            magasin=reseau["nice"], article=article, quantite=1, type="reception"
        )
    MouvementStock.tous.create(
        magasin=reseau["lille"], article=article, quantite=1, type="reception"
    )


@pytest.mark.parametrize(
    "table", ["securite_evenementsecurite", "auditlog_logentry", "optique_accesprescription"]
)
def test_journaux_en_ajout_seul(reseau, table):
    from apps.crm.models import Client
    from apps.optique.models import AccesPrescription, Prescription
    from apps.securite.models import Utilisateur

    EvenementSecurite.objects.create(type=EvenementSecurite.Type.CONNEXION_REUSSIE)
    assert LogEntry.objects.exists()  # la création des magasins est journalisée
    opticien = Utilisateur.objects.create_user("opticien")
    client = Client.objects.create(nom="A", prenom="B", magasin_origine=reseau["lille"])
    prescription = Prescription(
        client=client,
        type="lunettes",
        date_prescription="2026-01-01",
        prescripteur="Dr",
        magasin_saisie=reseau["lille"],
        saisie_par=opticien,
    )
    prescription.mesures = {}
    prescription.save()
    AccesPrescription.objects.create(
        utilisateur=opticien, prescription=prescription, action="consultation"
    )
    for requete in (f"UPDATE {table} SET id = id", f"DELETE FROM {table}"):
        with pytest.raises(DatabaseError, match="ajout seul"), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(requete)


def test_le_middleware_vide_la_variable_apres_la_requete(creer_utilisateur, client_de, reseau):
    utilisateur = creer_utilisateur("vendeur", portee="magasin", magasin=reseau["lille"])
    reponse = client_de(utilisateur).get("/api/v1/magasins/")
    assert reponse.status_code == 200
    assert [m["code"] for m in reponse.json()["results"]] == ["M01"]
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('app.perimetre', true)")
        assert cursor.fetchone()[0] == ""
