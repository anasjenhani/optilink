#!/bin/sh
# États de la base de qualification : photographier la base sous un nom, puis y revenir.
#
#   ./etats-base.sh sauver NOM ["commentaire"]   photographie la base actuelle
#   ./etats-base.sh lister                       liste les états enregistrés
#   ./etats-base.sh restaurer NOM                remet la base dans l'état NOM
#   ./etats-base.sh supprimer NOM                efface l'état NOM
#
# Les états sont rangés dans ./sauvegardes/etats (NOM.dump et NOM.txt). Avant chaque
# restauration, l'état courant est d'abord photographié sous « avant-restauration-<date> » :
# une restauration faite par erreur se défait donc en restaurant cette photo.
# À lancer dans le dossier optilink du serveur, OptiLink démarré.
set -eu

cd "$(dirname "$0")"
COMPOSE=${COMPOSE:-"docker compose -f docker-compose.yml -f docker-compose.qualif.yml"}
DOSSIER=sauvegardes/etats

valeur_env() {
    # Lit une valeur de .env (sans l'exécuter), sinon la valeur par défaut.
    v=$(grep -E "^$1=" .env 2>/dev/null | tail -n 1 | cut -d= -f2- | tr -d '"'"'"'\r')
    echo "${v:-$2}"
}
BASE=$(valeur_env DB_NAME optilink)
COMPTE=$(valeur_env DB_USER optilink)

nom_valide() {
    case "$1" in
        "" | *[!A-Za-z0-9_.-]*)
            echo "Nom invalide : lettres, chiffres, point, tiret et souligné seulement (ex. avant-test-caisse)." >&2
            exit 1 ;;
    esac
}

psql_admin() {
    $COMPOSE exec -T postgres psql -v ON_ERROR_STOP=1 -U postgres -d postgres -q "$@"
}

sauver() {
    nom_valide "$1"
    mkdir -p "$DOSSIER"
    if [ -e "$DOSSIER/$1.dump" ]; then
        echo "L'état « $1 » existe déjà. Choisissez un autre nom ou supprimez-le d'abord." >&2
        exit 1
    fi
    if ! $COMPOSE exec -T postgres pg_dump -U postgres --format=custom "$BASE" > "$DOSSIER/$1.dump.partiel"; then
        rm -f "$DOSSIER/$1.dump.partiel"
        echo "Échec : la base n'a pas pu être photographiée (OptiLink est-il démarré ?)." >&2
        exit 1
    fi
    mv "$DOSSIER/$1.dump.partiel" "$DOSSIER/$1.dump"
    printf '%s\t%s\n' "$(date '+%Y-%m-%d %H:%M')" "${2:-}" > "$DOSSIER/$1.txt"
    echo "État « $1 » enregistré ($(du -h "$DOSSIER/$1.dump" | cut -f1))."
}

lister() {
    if ! ls "$DOSSIER"/*.dump > /dev/null 2>&1; then
        echo "Aucun état enregistré. Pour en créer un : ./etats-base.sh sauver NOM"
        return
    fi
    printf '%-38s %-17s %s\n' "NOM" "DATE" "COMMENTAIRE"
    for f in $(ls -t "$DOSSIER"/*.dump); do
        nom=$(basename "$f" .dump)
        date=$(cut -f1 "$DOSSIER/$nom.txt" 2>/dev/null || echo "?")
        commentaire=$(cut -f2- "$DOSSIER/$nom.txt" 2>/dev/null || true)
        printf '%-38s %-17s %s\n' "$nom" "$date" "$commentaire"
    done
}

restaurer() {
    nom_valide "$1"
    if [ ! -e "$DOSSIER/$1.dump" ]; then
        echo "L'état « $1 » n'existe pas. ./etats-base.sh lister montre ceux qui existent." >&2
        exit 1
    fi
    if [ "${OUI:-}" != "1" ]; then
        printf 'Remettre la base dans l'"'"'état « %s » ? Les données saisies depuis seront remplacées. [o/N] ' "$1"
        read -r reponse
        case "$reponse" in o | O | oui | OUI) ;; *) echo "Rien n'a été changé."; exit 0 ;; esac
    fi
    sauver "avant-restauration-$(date +%Y%m%d-%H%M%S)" "état avant la restauration de $1"

    echo "Arrêt de l'application le temps de la restauration…"
    $COMPOSE stop backend worker > /dev/null 2>&1
    trap '$COMPOSE start backend worker > /dev/null 2>&1' EXIT
    psql_admin -c "DROP DATABASE IF EXISTS \"$BASE\" WITH (FORCE)"
    psql_admin -c "CREATE DATABASE \"$BASE\" OWNER \"$COMPTE\""
    $COMPOSE exec -T postgres pg_restore -U postgres --dbname="$BASE" --exit-on-error < "$DOSSIER/$1.dump"
    # Les sessions ouvertes pointent vers l'ancienne base : chacun se reconnecte.
    $COMPOSE exec -T redis sh -c 'redis-cli ${REDIS_PASSWORD:+-a "$REDIS_PASSWORD"} --no-auth-warning FLUSHALL' > /dev/null 2>&1 || true
    echo "Base remise dans l'état « $1 ». Redémarrage de l'application…"
}

supprimer() {
    nom_valide "$1"
    if [ ! -e "$DOSSIER/$1.dump" ]; then
        echo "L'état « $1 » n'existe pas." >&2
        exit 1
    fi
    rm -f "$DOSSIER/$1.dump" "$DOSSIER/$1.txt"
    echo "État « $1 » supprimé."
}

case "${1:-}" in
    sauver) sauver "${2:-}" "${3:-}" ;;
    lister) lister ;;
    restaurer) restaurer "${2:-}" ;;
    supprimer) supprimer "${2:-}" ;;
    *) sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
