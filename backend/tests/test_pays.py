"""Liste des pays du monde : la fiche d'un pays se remplit à partir de son code ISO numérique."""

import re

import pytest

from apps.reseau.admin import PaysForm
from apps.reseau.models import Pays
from apps.reseau.pays_du_monde import pays_du_monde

# Ce qu'un formulaire d'ajout vierge renvoie : les valeurs par défaut du modèle.
VIERGE = {
    "decimales": "2",
    "fuseau_horaire": "Africa/Tunis",
    "timbre_fiscal": "0",
    "libelle_identifiant_prescripteur": "Identifiant du prescripteur",
}


def test_liste_des_pays_du_monde():
    liste = pays_du_monde()
    assert len(liste) > 240
    assert len({p["code"] for p in liste.values()}) == len(liste)
    for numerique, p in liste.items():
        assert re.fullmatch(r"\d{3}", numerique) and re.fullmatch(r"[A-Z]{2}", p["code"])
        assert re.fullmatch(r"[A-Z]{3}", p["devise"]) and 0 <= p["decimales"] <= 4
    assert liste["788"] == {
        "code_numerique": "788",
        "code": "TN",
        "nom": "Tunisie",
        "devise": "TND",
        "decimales": 3,
        "indicatif_telephonique": "+216",
        "fuseau_horaire": "Africa/Tunis",
    }
    assert liste["100"]["devise"] == "EUR"  # Bulgarie, passée à l'euro en 2026


@pytest.mark.django_db
def test_pays_existants_ont_leur_code_numerique():
    assert dict(Pays.objects.values_list("code", "code_numerique")) == {"TN": "788", "FR": "250"}


@pytest.mark.django_db
def test_choisir_un_pays_remplit_la_fiche():
    formulaire = PaysForm(data=VIERGE | {"pays_du_monde": "414"})
    assert formulaire.is_valid(), formulaire.errors
    koweit = formulaire.save()
    assert (koweit.code_numerique, koweit.code, koweit.nom, koweit.devise) == (
        "414",
        "KW",
        "Koweït",
        "KWD",
    )
    assert (koweit.decimales, koweit.indicatif_telephonique, koweit.fuseau_horaire) == (
        3,
        "+965",
        "Asia/Kuwait",
    )


@pytest.mark.django_db
def test_ce_qui_est_tape_a_la_main_est_garde():
    formulaire = PaysForm(data=VIERGE | {"pays_du_monde": "504", "nom": "Royaume du Maroc"})
    assert formulaire.is_valid(), formulaire.errors
    maroc = formulaire.save()
    assert (maroc.nom, maroc.devise, maroc.code_numerique) == ("Royaume du Maroc", "MAD", "504")


@pytest.mark.django_db
def test_modifier_une_fiche_sans_changer_de_pays_ne_la_reecrit_pas():
    tunisie = Pays.objects.get(code="TN")
    tunisie.fuseau_horaire = "Europe/Paris"
    tunisie.save()
    donnees = {
        nom: getattr(tunisie, nom)
        for nom in (
            "code_numerique",
            "code",
            "nom",
            "devise",
            "decimales",
            "indicatif_telephonique",
            "fuseau_horaire",
            "libelle_identifiant_prescripteur",
        )
    }
    formulaire = PaysForm(
        data=donnees | {"pays_du_monde": "788", "timbre_fiscal": "1.500"}, instance=tunisie
    )
    assert formulaire.is_valid(), formulaire.errors
    formulaire.save()
    tunisie.refresh_from_db()
    assert (str(tunisie.timbre_fiscal), tunisie.fuseau_horaire) == ("1.500", "Europe/Paris")


@pytest.mark.django_db
def test_sans_pays_choisi_les_champs_sont_exiges():
    formulaire = PaysForm(data=VIERGE)
    assert not formulaire.is_valid()
    assert set(formulaire.errors) >= {"code_numerique", "code", "nom", "devise"}
    assert "liste" in formulaire.errors["code_numerique"][0]


@pytest.mark.django_db
def test_un_pays_ne_peut_etre_cree_deux_fois():
    formulaire = PaysForm(data=VIERGE | {"pays_du_monde": "788"})
    assert not formulaire.is_valid()
    assert "code_numerique" in formulaire.errors
