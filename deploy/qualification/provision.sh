#!/usr/bin/env bash
# Installe OptiLink en qualification sur Ubuntu 24.04 : appelé par « vagrant up » (Vagrantfile),
# ou à la main sur un serveur déjà installé : sudo OPTILINK_IP=192.168.1.50 bash provision.sh
# Relançable sans risque : les secrets et le certificat déjà créés sont gardés.
set -euo pipefail

SOURCE=${OPTILINK_SOURCE:-/vagrant}
CIBLE=/opt/optilink
IP=${OPTILINK_IP:?OPTILINK_IP manquant}
NOM=$(hostname)
COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.qualif.yml)
export DEBIAN_FRONTEND=noninteractive

echo "== Système : fuseau horaire, mises à jour, outils"
timedatectl set-timezone Africa/Tunis
apt-get update -q
apt-get upgrade -yq
apt-get install -yq ca-certificates curl openssl rsync ufw

if ! command -v docker >/dev/null; then
    echo "== Docker, depuis son dépôt officiel"
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    . /etc/os-release
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
        > /etc/apt/sources.list.d/docker.list
    apt-get update -q
    apt-get install -yq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

echo "== Code OptiLink dans ${CIBLE}"
mkdir -p "$CIBLE"
rsync -a --delete \
    --exclude .git --exclude .vagrant --exclude node_modules --exclude .env \
    --exclude certs --exclude sauvegardes \
    "$SOURCE"/ "$CIBLE"/
cd "$CIBLE"

secret() { openssl rand -base64 48 | tr -dc 'A-Za-z0-9' | head -c "$1"; }

if [ ! -f .env ]; then
    echo "== Secrets de qualification (.env), générés une seule fois"
    (umask 077; cat > .env) <<ENV
DJANGO_SECRET_KEY=$(secret 60)
DJANGO_ALLOWED_HOSTS=${IP},${NOM},localhost
DJANGO_CSRF_TRUSTED_ORIGINS=https://${IP},https://${NOM}
DB_NAME=optilink
DB_USER=optilink
DB_PASSWORD=$(secret 32)
POSTGRES_ADMIN_PASSWORD=$(secret 32)
REDIS_PASSWORD=$(secret 32)
PRESCRIPTIONS_CLES=$(openssl rand 32 | base64 | tr '+/' '-_')
DEVIS_VALIDITE_JOURS=30
MFA_OBLIGATOIRE=1
COMPTES_INACTIFS_JOURS=90
SESSION_DUREE_SECONDES=36000
ENV
fi

if [ ! -f certs/optilink.crt ]; then
    echo "== Certificat HTTPS auto-signé pour ${IP} et ${NOM}"
    mkdir -p certs
    openssl req -x509 -newkey rsa:2048 -nodes -days 825 -subj "/CN=${NOM}" \
        -addext "subjectAltName=IP:${IP},DNS:${NOM}" \
        -keyout certs/optilink.key -out certs/optilink.crt 2>/dev/null
    chmod 644 certs/optilink.crt
fi
mkdir -p sauvegardes

echo "== Pare-feu : SSH, HTTP et HTTPS seulement"
ufw allow OpenSSH >/dev/null
ufw allow 80/tcp >/dev/null
ufw allow 443/tcp >/dev/null
ufw --force enable >/dev/null

echo "== Construction et démarrage d'OptiLink (plusieurs minutes la première fois)"
"${COMPOSE[@]}" up -d --build

echo "== Attente du démarrage"
for _ in $(seq 60); do
    if curl -fsk "https://localhost/api/v1/sante/" >/dev/null 2>&1; then
        echo
        echo "OptiLink est prêt : https://${IP}"
        echo "Créer le premier compte administrateur : vagrant ssh, puis"
        echo "  cd ${CIBLE} && sudo ${COMPOSE[*]} exec backend python manage.py createsuperuser"
        exit 0
    fi
    sleep 5
done
echo "OptiLink ne répond pas encore. Voir : cd ${CIBLE} && sudo ${COMPOSE[*]} logs" >&2
exit 1
