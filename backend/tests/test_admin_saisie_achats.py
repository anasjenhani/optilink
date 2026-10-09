"""Saisie manuelle d'un bon de réception et d'une facture achat dans /admin/ (« Ajouter »)."""

from apps.achats.models import BonReception, FactureAchat, Fournisseur
from apps.stock.models import MouvementStock


def _admin(creer_utilisateur, client_de):
    anas = creer_utilisateur("anas")
    anas.is_staff = anas.is_superuser = True
    anas.save()
    return client_de(anas)


def _lignes(*lignes):
    donnees = {
        "lignes-TOTAL_FORMS": str(len(lignes)),
        "lignes-INITIAL_FORMS": "0",
        "lignes-MIN_NUM_FORMS": "1",
        "lignes-MAX_NUM_FORMS": "1000",
    }
    for i, ligne in enumerate(lignes):
        donnees.update({f"lignes-{i}-{cle}": valeur for cle, valeur in ligne.items()})
    return donnees


def test_ajouter_un_bon_puis_sa_facture(creer_utilisateur, client_de, tunis, monture):
    navigateur = _admin(creer_utilisateur, client_de)
    optical = Fournisseur.objects.create(nom="Optical Line", pays=tunis.pays)
    liste = navigateur.get("/admin/achats/bonreception/").content.decode()
    assert 'href="/admin/achats/bonreception/add/"' in liste
    assert navigateur.get("/admin/achats/bonreception/add/").status_code == 200

    entete = {
        "magasin": tunis.pk,
        "fournisseur": optical.pk,
        "numero_bl": "26/00426",
        "date_bl": "2026-09-11",
        "taux_remise_ex": "0",
    }
    ligne = {"article": monture.reference, "quantite": "2", "prix_achat_ht": "100"}
    vide = {"article": "", "quantite": "1", "prix_achat_ht": ""}
    reponse = navigateur.post("/admin/achats/bonreception/add/", {**entete, **_lignes(ligne, vide)})
    assert reponse.status_code == 302, reponse.context["entete"].errors
    bon = BonReception.tous.get()
    assert (bon.numero_bl, bon.total_net_ht, bon.lignes.count()) == ("26/00426", 200, 1)
    assert MouvementStock.objects.filter(article=monture, quantite=2).exists()

    # Le même BL est refusé, avec le message du service, sans rien enregistrer.
    deux_fois = navigateur.post("/admin/achats/bonreception/add/", {**entete, **_lignes(ligne)})
    assert "déjà enregistré" in deux_fois.content.decode()
    inconnu = navigateur.post(
        "/admin/achats/bonreception/add/",
        {**entete, "numero_bl": "X", **_lignes({**ligne, "article": "NEXISTEPAS"})},
    )
    assert "Article inconnu" in inconnu.content.decode()
    assert BonReception.tous.count() == 1

    liste = navigateur.get("/admin/achats/factureachat/").content.decode()
    assert 'href="/admin/achats/factureachat/add/"' in liste
    page = navigateur.get("/admin/achats/factureachat/add/").content.decode()
    assert "BL 26/00426" in page
    reponse = navigateur.post(
        "/admin/achats/factureachat/add/",
        {
            "magasin": tunis.pk,
            "fournisseur": optical.pk,
            "reference_fournisseur": "26/00487",
            "date_reference": "2026-09-30",
            "bons": [bon.pk],
            "taux_remise_ex": "0",
            "frais_supplementaires": "0",
            "timbre_fiscal": "1",
            "ajustement": "0",
        },
    )
    assert reponse.status_code == 302, reponse.context["entete"].errors
    facture = FactureAchat.tous.get()
    bon.refresh_from_db()
    assert (bon.facture, bon.etat) == (facture, "facture")
    assert facture.total_ttc == bon.total_ttc + 1


def test_ajouter_exige_le_droit(affecter, client_de, tunis):
    lecteur = affecter(
        "lecteur",
        "achats.view_bonreception",
        "achats.view_factureachat",
        portee="magasin",
        magasin=tunis,
    )
    lecteur.is_staff = True
    lecteur.save()
    navigateur = client_de(lecteur)
    assert "bonreception/add/" not in navigateur.get("/admin/achats/bonreception/").content.decode()
    assert navigateur.get("/admin/achats/bonreception/add/").status_code == 403
    assert navigateur.get("/admin/achats/factureachat/add/").status_code == 403
