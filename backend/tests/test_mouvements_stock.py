from datetime import datetime

import pytest
from django.utils import timezone

from apps.stock.models import Article, MouvementStock

URL = "/api/v1/mouvements-stock/"
LECTURE = ("stock.view_mouvementstock",)


@pytest.fixture
def mouvements(reseau, creer_utilisateur):
    monture = Article.objects.create(
        reference="MON-1", libelle="Monture titane", famille="monture", code_barres="321"
    )
    verre = Article.objects.create(reference="VER-1", libelle="Verre", famille="verre")
    magasinier = creer_utilisateur("magasinier")
    creer = MouvementStock.tous.create
    reception = creer(
        magasin=reseau["lille"],
        article=monture,
        quantite=5,
        type="reception",
        reference="BL-1",
        utilisateur=magasinier,
    )
    vente = creer(magasin=reseau["lille"], article=monture, quantite=-1, type="vente")
    arras = creer(magasin=reseau["arras"], article=verre, quantite=2, type="ajustement")
    # Dates fixées après coup : l'horodatage est posé à l'enregistrement.
    for mouvement, jour in ((reception, 1), (vente, 10), (arras, 20)):
        MouvementStock.tous.filter(pk=mouvement.pk).update(
            horodatage=timezone.make_aware(datetime(2026, 9, jour, 12))
        )
    return {"reception": reception, "vente": vente, "arras": arras}


def ids(reponse):
    assert reponse.status_code == 200, reponse.json()
    return [m["id"] for m in reponse.json()["results"]]


def test_liste_detaillee_plus_recents_d_abord(affecter, client_de, mouvements):
    api = client_de(affecter("controleur", *LECTURE, portee="reseau"))
    reponse = api.get(URL)
    m = mouvements
    assert ids(reponse) == [m["arras"].pk, m["vente"].pk, m["reception"].pk]
    reception = reponse.json()["results"][2]
    assert reception | {"horodatage": None} == {
        "id": m["reception"].pk,
        "magasin": str(m["reception"].magasin.public_id),
        "magasin_nom": "Lille",
        "article": str(m["reception"].article.public_id),
        "article_reference": "MON-1",
        "article_libelle": "Monture titane",
        "quantite": 5,
        "type": "reception",
        "type_libelle": "Réception",
        "reference": "BL-1",
        "utilisateur": "magasinier",
        "horodatage": None,
    }
    vente = reponse.json()["results"][1]
    assert (vente["type_libelle"], vente["utilisateur"]) == ("Vente", "")


def test_filtres(affecter, client_de, reseau, mouvements):
    api = client_de(affecter("controleur", *LECTURE, portee="reseau"))
    m = mouvements
    lille = str(reseau["lille"].public_id)
    assert ids(api.get(URL, {"magasin": lille})) == [m["vente"].pk, m["reception"].pk]
    assert ids(api.get(URL, {"article": "mon"})) == [m["vente"].pk, m["reception"].pk]
    assert ids(api.get(URL, {"article": "321"})) == [m["vente"].pk, m["reception"].pk]
    assert ids(api.get(URL, {"type": "ajustement"})) == [m["arras"].pk]
    assert ids(api.get(URL, {"du": "2026-09-10", "au": "2026-09-10"})) == [m["vente"].pk]
    assert ids(api.get(URL, {"du": "2026-09-05", "magasin": lille})) == [m["vente"].pk]
    assert api.get(URL, {"du": "hier"}).status_code == 400
    assert api.get(URL, {"magasin": "x"}).status_code == 400


def test_perimetre_et_droit(affecter, client_de, reseau, mouvements):
    lille = client_de(affecter("vlille", *LECTURE, portee="magasin", magasin=reseau["lille"]))
    assert ids(lille.get(URL)) == [mouvements["vente"].pk, mouvements["reception"].pk]
    sans_droit = client_de(affecter("vendeur", "stock.view_article", portee="reseau"))
    assert sans_droit.get(URL).status_code == 403


def test_mouvement_jamais_modifie_ni_supprime(affecter, client_de, mouvements):
    api = client_de(
        affecter(
            "chef",
            *LECTURE,
            "stock.change_mouvementstock",
            "stock.delete_mouvementstock",
            portee="reseau",
        )
    )
    url = f"{URL}{mouvements['reception'].pk}/"
    assert api.patch(url, {"quantite": 9}, format="json").status_code in (404, 405)
    assert api.delete(url).status_code in (404, 405)
