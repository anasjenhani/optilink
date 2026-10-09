#!/bin/sh
# Sauvegarde quotidienne de la base de qualification, à SAUVEGARDE_HEURE heures,
# gardée SAUVEGARDE_JOURS jours dans /sauvegardes (dossier ./sauvegardes du serveur).
set -eu
heure=${SAUVEGARDE_HEURE:-2}
jours=${SAUVEGARDE_JOURS:-7}

while true; do
    h=$(date +%H); m=$(date +%M); s=$(date +%S)
    maintenant=$(( ${h#0} * 3600 + ${m#0} * 60 + ${s#0} ))
    attente=$(( (heure * 3600 - maintenant + 86400) % 86400 ))
    [ "$attente" -eq 0 ] && attente=86400
    sleep "$attente"

    fichier="/sauvegardes/${PGDATABASE}-$(date +%Y-%m-%d).dump"
    if pg_dump --format=custom --file="$fichier.partiel" && mv "$fichier.partiel" "$fichier"; then
        echo "$(date) sauvegarde faite : $fichier"
        find /sauvegardes -name "${PGDATABASE}-*.dump" -mtime +"$jours" -delete
    else
        rm -f "$fichier.partiel"
        echo "$(date) ÉCHEC de la sauvegarde" >&2
    fi
done
