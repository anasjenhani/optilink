"""Administration du serveur : onglets horizontaux par domaine métier."""


def test_onglets_de_l_administration(creer_utilisateur, client_de):
    anas = creer_utilisateur("anas")
    anas.is_staff = anas.is_superuser = True
    anas.save()
    navigateur = client_de(anas)

    accueil = navigateur.get("/admin/")
    assert accueil.status_code == 200
    assert [o["libelle"] for o in accueil.context["onglets"]] == [
        "Ventes",
        "Stock et achats",
        "Caisse et banque",
        "RH",
        "Alertes et reporting",
        "Réseau",
        "Sécurité",
    ]
    assert 'class="onglets"' in accueil.content.decode()

    caisse = navigateur.get("/admin/", {"onglet": "caisse"})
    assert [app["app_label"] for app in caisse.context["app_list"]] == ["tresorerie"]
    assert caisse.context["title"] == "Caisse et banque"
    page = caisse.content.decode()
    assert 'class="bandeau"' in page
    assert 'href="/admin/tresorerie/cloturecaisse/"' in page
    assert 'href="/admin/tresorerie/comptetresorerie/add/"' in page

    liste = navigateur.get("/admin/tresorerie/cloturecaisse/")
    actifs = [o["libelle"] for o in liste.context["onglets"] if o["actif"]]
    assert actifs == ["Caisse et banque"]


def test_onglets_limites_aux_droits(affecter, client_de):
    rh = affecter("rh", "rh.view_employe", portee="reseau")
    rh.is_staff = True
    rh.save()
    onglets = client_de(rh).get("/admin/").context["onglets"]
    assert [o["libelle"] for o in onglets] == ["RH", "Alertes et reporting"]
