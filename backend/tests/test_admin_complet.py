"""/admin/ : « Ajouter » d'un bon retour et d'un transfert, dépenses de caisse, consultations."""

from decimal import Decimal

from apps.achats.models import BonRetour, Fournisseur
from apps.crm.models import Organisme
from apps.reseau.models import Magasin
from apps.stock.models import MouvementStock, TransfertStock, stock_disponible
from apps.tresorerie.models import DepenseCaisse


def _admin(creer_utilisateur, client_de):
    anas = creer_utilisateur("anas")
    anas.is_staff = anas.is_superuser = True
    anas.save()
    return anas, client_de(anas)


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


def test_ajouter_un_bon_retour(creer_utilisateur, client_de, tunis, monture):
    _, navigateur = _admin(creer_utilisateur, client_de)
    optical = Fournisseur.objects.create(nom="Optical Line", pays=tunis.pays)
    assert (
        'href="/admin/achats/bonretour/add/"'
        in navigateur.get("/admin/achats/bonretour/").content.decode()
    )
    entete = {"magasin": tunis.pk, "fournisseur": optical.pk, "motif": "Défaut"}
    ligne = {"article": monture.reference, "quantite": "1", "prix_achat_ht": "100"}
    reponse = navigateur.post("/admin/achats/bonretour/add/", {**entete, **_lignes(ligne)})
    assert reponse.status_code == 302, reponse.context["entete"].errors
    bon = BonRetour.tous.get()
    assert (bon.lignes.count(), bon.lignes.get().taux_tva) == (1, Decimal("19"))
    assert stock_disponible(tunis, monture) == 2

    trop = navigateur.post(
        "/admin/achats/bonretour/add/", {**entete, **_lignes({**ligne, "quantite": "9"})}
    )
    assert "9 à renvoyer, 2 en stock" in trop.content.decode()
    assert BonRetour.tous.count() == 1


def test_ajouter_un_transfert(creer_utilisateur, client_de, tunis, monture):
    _, navigateur = _admin(creer_utilisateur, client_de)
    lac = Magasin.tous.create(code="T02", nom="Lac", societe=tunis.societe, pays=tunis.pays)
    assert (
        'href="/admin/stock/transfertstock/add/"'
        in navigateur.get("/admin/stock/transfertstock/").content.decode()
    )
    entete = {
        "depot_origine": tunis.depot_de_vente.pk,
        "depot_destination": lac.depot_de_vente.pk,
    }
    reponse = navigateur.post(
        "/admin/stock/transfertstock/add/",
        {**entete, **_lignes({"article": monture.reference, "quantite": "2"})},
    )
    assert reponse.status_code == 302, reponse.context["entete"].errors
    transfert = TransfertStock.tous.get()
    assert (transfert.destination, transfert.statut) == (lac, "envoye")
    assert stock_disponible(tunis, monture) == 1

    meme = navigateur.post(
        "/admin/stock/transfertstock/add/",
        {
            "depot_origine": tunis.depot_de_vente.pk,
            "depot_destination": tunis.depot_de_vente.pk,
            **_lignes({"article": "MON-T", "quantite": "1"}),
        },
    )
    assert "autre dépôt" in meme.content.decode()
    assert TransfertStock.tous.count() == 1


def test_depense_de_caisse_dans_l_admin(creer_utilisateur, client_de, tunis):
    anas, navigateur = _admin(creer_utilisateur, client_de)
    reponse = navigateur.post(
        "/admin/tresorerie/depensecaisse/add/",
        {"magasin": tunis.pk, "categorie": "divers", "motif": "Eau", "montant": "4.500"},
    )
    assert reponse.status_code == 302
    depense = DepenseCaisse.tous.get()
    assert (depense.saisie_par, depense.cloture) == (anas, None)
    page = f"/admin/tresorerie/depensecaisse/{depense.pk}/change/"
    assert "Enregistrer" in navigateur.get(page).content.decode()
    liste = navigateur.get("/admin/tresorerie/depensecaisse/").content.decode()
    assert "delete_selected" not in liste


def test_consultations_et_suppressions(creer_utilisateur, client_de, tunis):
    _, navigateur = _admin(creer_utilisateur, client_de)
    for page in ("ventes/priseencharge", "ventes/etapecommande", "achats/casseverre"):
        reponse = navigateur.get(f"/admin/{page}/")
        assert reponse.status_code == 200, page
        assert f'href="/admin/{page}/add/"' not in reponse.content.decode()
    organisme = Organisme.objects.create(nom="Mutuelle test", type="mutuelle", pays=tunis.pays)
    page = f"/admin/crm/organisme/{organisme.pk}/delete/"
    assert navigateur.post(page, {"post": "yes"}).status_code == 302
    assert not Organisme.objects.filter(pk=organisme.pk).exists()
    assert not MouvementStock.tous.exists()
