"""Corbeille : une suppression se restaure pendant le délai de grâce, puis s'efface."""

import datetime

from django.contrib.auth.models import Group, Permission
from django.utils import timezone

from apps.achats.models import Fournisseur
from apps.securite.corbeille import vider_expires
from apps.securite.models import ElementCorbeille
from apps.stock.models import Article, Monture
from apps.tresorerie.models import DepenseCaisse

CORBEILLE = ("securite.view_elementcorbeille", "securite.restaurer_elementcorbeille")


def _admin(creer_utilisateur, client_de):
    anas = creer_utilisateur("anas")
    anas.is_staff = anas.is_superuser = True
    anas.save()
    return client_de(anas)


def test_une_depense_supprimee_se_restaure(affecter, client_de, tunis, reseau):
    caissier = affecter(
        "caissier",
        "tresorerie.view_depensecaisse",
        "tresorerie.add_depensecaisse",
        *CORBEILLE,
        portee="magasin",
        magasin=tunis,
    )
    api = client_de(caissier)
    corps = {
        "magasin_id": str(tunis.public_id),
        "categorie": "divers",
        "motif": "Eau",
        "montant": "3",
    }
    depense = api.post("/api/v1/tresorerie/depenses/", corps, format="json").json()
    assert api.delete(f"/api/v1/tresorerie/depenses/{depense['id']}/").status_code == 204
    assert not DepenseCaisse.tous.exists()

    corbeille = api.get("/api/v1/corbeille/").json()["results"]
    assert [(e["type_libelle"], e["supprime_par"]) for e in corbeille] == [
        ("Dépense de caisse", "caissier")
    ]
    # Un caissier d'un autre magasin ne la voit pas.
    lille = affecter(
        "lille",
        "tresorerie.add_depensecaisse",
        *CORBEILLE,
        portee="magasin",
        magasin=reseau["lille"],
    )
    assert client_de(lille).get("/api/v1/corbeille/").json()["results"] == []
    assert (
        client_de(lille).post(f"/api/v1/corbeille/{corbeille[0]['id']}/restaurer/").status_code
        == 404
    )

    assert api.post(f"/api/v1/corbeille/{corbeille[0]['id']}/restaurer/").status_code == 204
    restauree = DepenseCaisse.tous.get()
    assert (str(restauree.public_id), restauree.motif) == (depense["id"], "Eau")
    assert not ElementCorbeille.objects.exists()
    # Vider définitivement exige son propre droit.
    assert api.delete(f"/api/v1/corbeille/{corbeille[0]['id']}/").status_code in (403, 404)


def test_admin_article_et_sa_fiche_monture(creer_utilisateur, client_de, monture):
    navigateur = _admin(creer_utilisateur, client_de)
    sans_stock = Article.objects.create(reference="MON-X", libelle="Monture X", famille="monture")
    Monture.objects.create(article=sans_stock, marque="Ray-Ban", categorie="optique")
    reponse = navigateur.post(f"/admin/stock/article/{sans_stock.pk}/delete/", {"post": "yes"})
    assert reponse.status_code == 302
    assert not Article.objects.filter(pk=sans_stock.pk).exists()
    element = ElementCorbeille.objects.get()
    assert (element.libelle, element.nombre_objets) == (str(sans_stock), 2)
    assert "Monture X" in navigateur.get("/admin/securite/elementcorbeille/").content.decode()

    navigateur.post(
        "/admin/securite/elementcorbeille/",
        {"action": "restaurer_elements", "_selected_action": [element.pk]},
    )
    article = Article.objects.get(pk=sans_stock.pk)
    assert (article.monture.marque, article.public_id) == ("Ray-Ban", sans_stock.public_id)
    assert not ElementCorbeille.objects.exists()


def test_restauration_refusee_si_un_doublon_existe(creer_utilisateur, client_de, tunis):
    navigateur = _admin(creer_utilisateur, client_de)
    profil = Group.objects.create(name="Stagiaire")
    profil.permissions.add(Permission.objects.get(codename="view_article"))
    navigateur.post(f"/admin/auth/group/{profil.pk}/delete/", {"post": "yes"})
    element = ElementCorbeille.objects.get()
    Group.objects.create(name="Stagiaire")
    page = navigateur.post(
        "/admin/securite/elementcorbeille/",
        {"action": "restaurer_elements", "_selected_action": [element.pk]},
        follow=True,
    ).content.decode()
    assert "rien n&#x27;a été restauré" in page or "doublon" in page
    assert ElementCorbeille.objects.filter(pk=element.pk).exists()

    # Sans doublon, le profil revient avec ses privilèges.
    Group.objects.filter(name="Stagiaire").delete()
    navigateur.post(
        "/admin/securite/elementcorbeille/",
        {"action": "restaurer_elements", "_selected_action": [element.pk]},
    )
    assert list(
        Group.objects.get(name="Stagiaire").permissions.values_list("codename", flat=True)
    ) == ["view_article"]


def test_la_corbeille_se_vide_apres_le_delai(creer_utilisateur, client_de, tunis):
    navigateur = _admin(creer_utilisateur, client_de)
    vieux = Fournisseur.objects.create(nom="Ancien", pays=tunis.pays)
    navigateur.post(f"/admin/achats/fournisseur/{vieux.pk}/delete/", {"post": "yes"})
    element = ElementCorbeille.objects.get()
    assert element.expire_le - element.supprime_le >= datetime.timedelta(days=29)
    assert vider_expires() == 0
    assert vider_expires(timezone.now() + datetime.timedelta(days=31)) == 1
    assert not ElementCorbeille.objects.exists()
