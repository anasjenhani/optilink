"""Fiche utilisateur dans l'administration : affectations et état du compte."""

from django.contrib.auth.models import Group

from apps.reseau.models import Societe
from apps.securite.models import Affectation, Utilisateur


def _admin(creer_utilisateur, client_de):
    anas = creer_utilisateur("anas")
    anas.is_staff = anas.is_superuser = True
    anas.save()
    return client_de(anas)


def test_la_societe_suit_le_magasin_de_l_affectation(creer_utilisateur, client_de, tunis):
    navigateur = _admin(creer_utilisateur, client_de)
    molka = Utilisateur.objects.create_user("molka", first_name="Molka", last_name="B")
    vendeur = Group.objects.get(name="Vendeur")
    url = f"/admin/securite/utilisateur/{molka.pk}/change/"
    page = navigateur.get(url)
    assert "securite/affectations.js" in page.content.decode()
    donnees = {
        "username": "molka",
        "first_name": "Molka",
        "last_name": "B",
        "email": "",
        "is_active": "on",
        "affectations-TOTAL_FORMS": "1",
        "affectations-INITIAL_FORMS": "0",
        "affectations-0-role": str(vendeur.pk),
        "affectations-0-portee": "magasin",
        "affectations-0-magasin": str(tunis.pk),
        # Une société différente envoyée avec un magasin n'est pas gardée : elle suit le magasin.
        "affectations-0-societe": str(Societe.objects.create(raison_sociale="Autre").pk),
        "affectations-0-debut": "2026-10-07",
    }
    reponse = navigateur.post(url, donnees)
    assert reponse.status_code == 302, reponse.context and reponse.context["errors"]
    affectation = Affectation.objects.get(utilisateur=molka)
    assert (affectation.magasin, affectation.societe) == (tunis, None)

    inline = navigateur.get(url).context["inline_admin_formsets"][0].formset.forms[0]
    assert inline.initial["societe"] == tunis.societe_id


def test_la_liste_des_utilisateurs_montre_l_etat_et_les_profils(
    creer_utilisateur, client_de, tunis
):
    navigateur = _admin(creer_utilisateur, client_de)
    sabrine = Utilisateur.objects.create_user("sabrine", is_active=False)
    vendeur = Group.objects.get(name="Vendeur")
    Affectation.objects.create(utilisateur=sabrine, role=vendeur, portee="magasin", magasin=tunis)
    page = navigateur.get("/admin/securite/utilisateur/").content.decode()
    assert "column-is_active" in page and 'alt="False"' in page
    assert "Vendeur (T01)" in page
