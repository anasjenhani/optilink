# Scripts

Tous les scripts à lancer à la main sont ici. Ils se lancent depuis le dossier `optilink` du
serveur (`cd /opt/optilink`), OptiLink démarré.

| Script | Sert à | Comment le lancer |
|---|---|---|
| `etats-base.sh` | Photographier la base de test sous un nom, puis y revenir pour rejouer un essai avec les mêmes données. | `./scripts/etats-base.sh sauver NOM`, `lister`, `restaurer NOM`, `supprimer NOM` |
| `provision-qualification.sh` | Installer un serveur de test complet (Docker, secrets, certificat, pare-feu) et démarrer OptiLink. Lancé tout seul par Vagrant ; se relance sans risque. | `sudo OPTILINK_SOURCE=. OPTILINK_IP=192.168.1.50 bash scripts/provision-qualification.sh` |
| `creer-depot.sh` | Créer le dépôt central d'une société en copiant les réglages d'un magasin (par défaut celui dont le nom contient « wahat »). Ne crée pas de doublon. | `sh scripts/creer-depot.sh` (ou `MODELE=aouina CODE=DEP2 sh scripts/creer-depot.sh`) |

## Migration depuis l'ancien logiciel

Les fichiers de données (exports de l'ancien logiciel et fichiers convertis) ne sont pas dans
le dépôt : ils restent dans les fichiers du projet, dossier `migration/`.

| Script | Sert à | Comment le lancer |
|---|---|---|
| `migration/convertir-i2s.py` | Convertir les exports CSV de l'ancien logiciel (I2S) au format d'import d'OptiLink : fournisseurs, brouillon d'utilisateurs, et un rapport des contrôles. | `python3 scripts/migration/convertir-i2s.py <dossier des exports> <dossier de sortie>` |
| `migration/affecter-1-et-C.sh` | Passer les 44 utilisateurs importés du magasin MAG001 au magasin « 1 », et leur donner le même profil sur « C ». Ne crée pas de doublon. | `sh scripts/migration/affecter-1-et-C.sh` |

## Scripts lancés automatiquement (à ne pas déplacer)

Ces scripts restent à leur place, car Docker les appelle par leur chemin :

| Script | Sert à |
|---|---|
| `backend/docker-entrypoint.sh` | Au démarrage du serveur d'application : applique les migrations de la base. |
| `docker/postgres/01-compte-applicatif.sh` | Au premier démarrage de PostgreSQL : crée le compte de l'application, soumis au cloisonnement par magasin. |
| `docker/sauvegarde.sh` | Chaque jour sur le serveur de test (heure SAUVEGARDE_HEURE) : sauvegarde de la base, gardée 7 jours. |
