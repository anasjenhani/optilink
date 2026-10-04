"""Familles d'articles : montures, verres et lentilles ont leur fiche ; les divers n'en ont pas."""

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.achats.models import Fournisseur
from apps.stock.models import Article, Lentille, Monture, PrixArticle, Verre
from tests.conftest import tva


@pytest.fixture
def catalogue(tunis, monture):
    Monture.objects.create(
        article=monture,
        marque="Ray-Ban",
        modele="RB5154",
        couleur="écaille",
        type="cerclee",
        calibre=51,
        pont=21,
        branche=145,
    )
    verre = Article.objects.create(
        reference="VER-1", libelle="Verre progressif", famille="verre", sur_commande=True
    )
    Verre.objects.create(
        article=verre,
        marque="Essilor",
        gamme="Varilux Comfort",
        geometrie="progressif",
        indice=Decimal("1.600"),
        matiere="organique",
        traitements="antireflet",
    )
    lentille = Article.objects.create(reference="LEN-1", libelle="Lentilles", famille="lentille")
    Lentille.objects.create(
        article=lentille,
        marque="Acuvue",
        modele="Oasys",
        renouvellement="bimensuelle",
        type="torique",
        rayon=Decimal("8.6"),
        diametre=Decimal("14.5"),
        puissance=Decimal("-2.25"),
        cylindre=Decimal("-0.75"),
        axe=180,
        lentilles_par_boite=6,
    )
    etui = Article.objects.create(reference="DIV-1", libelle="Étui rigide", famille="divers")
    labo = Fournisseur.objects.create(nom="Fournisseur test", pays=tunis.pays)
    Article.objects.update(fournisseur=labo)
    for article in (verre, lentille, etui):
        PrixArticle.objects.create(
            article=article,
            pays=tunis.pays,
            prix_vente_ttc=Decimal("10.000"),
            tva=tva(tunis.pays, 19),
        )
    return {
        nom: Article.objects.get(pk=article.pk)
        for nom, article in {
            "monture": monture,
            "verre": verre,
            "lentille": lentille,
            "divers": etui,
        }.items()
    }


@pytest.fixture
def api(affecter, client_de, tunis):
    return client_de(affecter("vendeur", "stock.view_article", portee="magasin", magasin=tunis))


def test_chaque_famille_decrite_par_sa_fiche(api, tunis, catalogue):
    reponse = api.get("/api/v1/articles/", {"magasin": str(tunis.public_id)})
    assert reponse.status_code == 200
    par_reference = {a["reference"]: a for a in reponse.json()["results"]}
    assert par_reference["MON-T"]["description"] == "Ray-Ban RB5154 · écaille · 51□21-145 · Cerclée"
    assert par_reference["VER-1"]["description"] == (
        "Essilor Varilux Comfort · Progressif · indice 1.600 · Organique · antireflet"
    )
    assert par_reference["LEN-1"]["description"] == (
        "Acuvue Oasys · Bimensuelle · Torique · R 8.6 · Ø 14.5 · -2.25 (-0.75 à 180°) · boîte de 6"
    )
    assert par_reference["VER-1"]["caracteristiques"]["indice"] == "1.600"
    assert par_reference["MON-T"]["caracteristiques"]["calibre"] == 51
    assert (par_reference["DIV-1"]["caracteristiques"], par_reference["DIV-1"]["description"]) == (
        None,
        "",
    )


def test_recherche_par_marque_modele_ou_gamme(api, catalogue):
    def references(**params):
        return sorted(
            a["reference"] for a in api.get("/api/v1/articles/", params).json()["results"]
        )

    assert references(recherche="varilux") == ["VER-1"]
    assert references(recherche="oasys") == ["LEN-1"]
    assert references(marque="ray-ban") == ["MON-T"]
    assert references(famille="divers") == ["DIV-1"]


def test_une_fiche_va_avec_sa_famille(catalogue):
    with pytest.raises(ValidationError, match="famille « monture »"):
        Monture(article=catalogue["divers"], marque="X").full_clean()
    verre = catalogue["verre"]
    verre.famille = Article.Famille.MONTURE
    with pytest.raises(ValidationError, match="reste dans cette famille"):
        verre.full_clean()
    etui = catalogue["divers"]
    etui.famille = Article.Famille.MONTURE
    etui.full_clean()  # sans fiche, on peut encore reclasser l'article


def test_creation_d_une_monture_dans_l_administration(creer_utilisateur, tunis):
    from django.test import Client as Navigateur
    from django_otp import DEVICE_ID_SESSION_KEY
    from django_otp.plugins.otp_totp.models import TOTPDevice

    admin = creer_utilisateur("admin")
    admin.is_staff = admin.is_superuser = True
    admin.save()
    navigateur = Navigateur()
    navigateur.force_login(admin)
    session = navigateur.session
    session[DEVICE_ID_SESSION_KEY] = TOTPDevice.objects.create(
        user=admin, name="t", confirmed=True
    ).persistent_id
    session.save()

    labo = Fournisseur.objects.create(nom="Nano Vista", pays=tunis.pays)
    vide = {"TOTAL_FORMS": "0", "INITIAL_FORMS": "0", "MIN_NUM_FORMS": "0", "MAX_NUM_FORMS": "1"}
    formulaire = {
        "reference": "MON-9",
        "libelle": "Monture enfant",
        "famille": "monture",
        "fournisseur": str(labo.pk),
        "est_actif": "on",
        **{f"monture-{k}": v for k, v in {**vide, "TOTAL_FORMS": "1"}.items()},
        "monture-0-marque": "Nano",
        "monture-0-genre": "enfant",
        "monture-0-calibre": "44",
        **{f"verre-{k}": v for k, v in vide.items()},
        **{f"lentille-{k}": v for k, v in vide.items()},
        **{f"prix-{k}": v for k, v in {**vide, "MAX_NUM_FORMS": "1000"}.items()},
    }
    reponse = navigateur.post("/admin/stock/article/add/", formulaire)
    assert reponse.status_code == 302, reponse.content.decode()[:3000]
    fiche = Article.objects.get(reference="MON-9").monture
    assert (fiche.marque, fiche.genre, fiche.calibre) == ("Nano", "enfant", 44)


def test_fournisseur_et_code_barres(api, tunis, catalogue):
    from django.db import IntegrityError, transaction

    essilor = Fournisseur.objects.create(nom="Essilor Tunisie", pays=tunis.pays)
    verre = catalogue["verre"]
    verre.fournisseur, verre.reference_fournisseur = essilor, "VX-COMF-16"
    verre.save()
    monture = catalogue["monture"]
    monture.code_barres = "8053672000001"
    monture.save()

    def references(**params):
        return [a["reference"] for a in api.get("/api/v1/articles/", params).json()["results"]]

    assert references(fournisseur=str(essilor.public_id)) == ["VER-1"]
    assert references(fournisseur="pas-un-uuid") == []
    assert references(recherche="vx-comf-16") == ["VER-1"]
    assert references(recherche="8053672000001") == ["MON-T"]
    assert api.get(f"/api/v1/articles/{verre.public_id}/").json()["fournisseur"] == (
        "Essilor Tunisie"
    )
    # Deux articles sans code-barres, oui ; deux avec le même, non.
    Article.objects.create(reference="DIV-2", libelle="Chiffon", famille="divers")
    with pytest.raises(IntegrityError), transaction.atomic():
        Article.objects.create(
            reference="MON-2", libelle="Autre", famille="monture", code_barres="8053672000001"
        )


def test_articles_par_type_de_vente(api, catalogue):
    solaire = Article.objects.create(reference="SOL-1", libelle="Solaire", famille="monture")
    Monture.objects.create(article=solaire, marque="Ray-Ban", solaire=True)
    Article.objects.create(reference="MON-2", libelle="Sans fiche", famille="monture")

    def references(type_vente):
        reponse = api.get("/api/v1/articles/", {"type_vente": type_vente})
        return sorted(a["reference"] for a in reponse.json()["results"])

    assert references("optique") == ["MON-2", "MON-T", "VER-1"]
    assert references("solaire") == ["SOL-1"]
    # Avec les lentilles, on vend aussi leurs produits (solutions, étuis…).
    assert references("lentille") == ["DIV-1", "LEN-1"]
    assert references("produit") == ["DIV-1"]
