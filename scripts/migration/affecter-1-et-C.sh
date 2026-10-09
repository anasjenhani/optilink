#!/bin/sh
# Migration des utilisateurs de l'ancien logiciel (7 octobre 2026) : les 44 comptes importés
# depuis migration/optilink/utilisateurs.csv passent du magasin MAG001 au magasin « 1 » et
# reçoivent le même profil sur « C » (Central Achat).
# À lancer sur le serveur :  sh scripts/migration/affecter-1-et-C.sh
# Sans risque si on le relance : rien n'est créé en double.
cd "$(dirname "$0")/../.." || exit 1
docker compose -f docker-compose.yml -f docker-compose.qualif.yml exec -T backend python manage.py shell <<'PY'
from django.db import transaction
from apps.reseau.models import Magasin
from apps.securite.models import Affectation
IDS = ['aya', 'AZZA', 'BOUTHEINAKH', 'bouthour', 'douaa', 'eya', 'EYACH', 'eyag', 'FATMACH', 'hajer', 'hanen', 'helmi', 'ibtihel', 'IBTISSEM.BM', 'IMTITHEL', 'ines', 'Insaf', 'JAMILA', 'Khalil', 'khaliles', 'khouloud', 'majdi', 'MAJDIJ', 'meriam', 'MOHAMED', 'MOLKA', 'mouna', 'NAWRES', 'Nisrine', 'OLFA', 'rabeb', 'RABEB.B', 'RAFIK', 'RAMI', 'Rania', 'ROUAA.HAMDI', 'sabrine', 'Sana', 'sarra', 'siwar', 'SIWAR.A', 'wassef', 'yossra', 'youssef']
un = Magasin.tous.get(code__iexact="1")
c = Magasin.tous.get(code__iexact="C")
with transaction.atomic():
    deplacees = ajoutees = 0
    for a in Affectation.objects.filter(utilisateur__username__in=IDS, portee="magasin").exclude(magasin=c):
        if a.magasin_id != un.pk:
            a.magasin = un
            a.save(update_fields=["magasin"])
            deplacees += 1
        _, cree = Affectation.objects.get_or_create(
            utilisateur=a.utilisateur, role=a.role, portee="magasin", magasin=c,
            defaults={"debut": a.debut, "fin": a.fin},
        )
        ajoutees += cree
print(f"{deplacees} affectation(s) passée(s) sur 1, {ajoutees} ajoutée(s) sur C.")
PY
