def test_sante_repond_sans_authentification(client, db):
    reponse = client.get("/api/v1/sante/")
    assert reponse.status_code == 200
    assert reponse.json() == {"statut": "ok", "base_de_donnees": "ok", "cache": "ok"}
