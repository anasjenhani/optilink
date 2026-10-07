#!/bin/sh
# Crée le dépôt central avec les mêmes réglages que le magasin El Wahat
# (société, pays, adresse, code postal, ville, téléphone, nombre de péniches).
# À lancer sur le serveur :  sh scripts/creer-depot.sh
# Sans risque si on le relance : un dépôt déjà créé n'est pas dupliqué.
cd "$(dirname "$0")/.." || exit 1
MODELE="${MODELE:-wahat}"   # nom (ou partie du nom) du magasin modèle
CODE="${CODE:-DEP}"         # code du dépôt (sert aussi aux numéros : DEP-TR2026-…)
NOM="${NOM:-Dépôt central}"
docker compose -f docker-compose.yml -f docker-compose.qualif.yml exec -T \
  -e MODELE="$MODELE" -e CODE="$CODE" -e NOM="$NOM" backend python manage.py shell <<'PY'
import os, sys
from apps.reseau.models import Magasin

modeles = Magasin.tous.filter(nom__icontains=os.environ["MODELE"], type=Magasin.Type.MAGASIN)
if modeles.count() != 1:
    print("Magasin modèle introuvable ou ambigu :", [str(m) for m in Magasin.tous.all()])
    sys.exit(1)
modele = modeles.get()
deja = Magasin.tous.filter(societe=modele.societe, type=Magasin.Type.DEPOT).first()
if deja:
    print(f"Un dépôt central existe déjà pour {modele.societe} : {deja}")
    sys.exit(0)
if Magasin.tous.filter(code=os.environ["CODE"]).exists():
    print(f"Le code {os.environ['CODE']} est déjà pris. Relancez avec CODE=AUTRE sh scripts/creer-depot.sh")
    sys.exit(1)
depot = Magasin.tous.create(
    code=os.environ["CODE"],
    nom=os.environ["NOM"],
    type=Magasin.Type.DEPOT,
    societe=modele.societe,
    pays=modele.pays,
    adresse=modele.adresse,
    code_postal=modele.code_postal,
    ville=modele.ville,
    telephone=modele.telephone,
    nombre_peniches=modele.nombre_peniches,
    est_actif=True,
)
print(f"Dépôt créé : {depot} (société {depot.societe}, copié de {modele})")
PY
