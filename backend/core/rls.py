"""Row-Level Security PostgreSQL : le cloisonnement par magasin appliqué par la base elle-même.

Le filtre applicatif (``ParMagasinManager``) reste la première barrière ; la base refuse en plus
toute ligne hors périmètre, même si une requête oublie le filtre ou passe par le manager ``tous``.

Pendant une requête HTTP, le middleware pose la variable de session ``app.perimetre`` :
``*`` (tout le réseau), ``-`` (aucun magasin) ou la liste des identifiants (``3,7``). Hors requête
(tâches Celery, migrations, commandes), elle est vide et la base n'ajoute aucun filtre.
"""

from contextlib import contextmanager

from django.db import connection

from core.perimetre import perimetre_actuel

VARIABLE = "app.perimetre"
TOUT = "*"
AUCUN = "-"


def valeur(ids):
    if ids is None:
        return TOUT
    if not ids:
        return AUCUN
    return ",".join(str(i) for i in sorted(ids))


def poser(ids):
    _ecrire(valeur(ids))


def effacer():
    _ecrire("")


@contextmanager
def voir_aussi(magasin_ids):
    """Élargit le périmètre de la base à quelques magasins, le temps d'une lecture précise
    (le stock du dépôt quand un magasin prépare son réassort), puis le rétablit."""
    ids = perimetre_actuel()
    if ids is None:
        yield
        return
    poser(ids | frozenset(magasin_ids))
    try:
        yield
    finally:
        poser(ids)


def _ecrire(texte):
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config(%s, %s, false)", [VARIABLE, texte])


FONCTION = f"""
CREATE OR REPLACE FUNCTION optilink_magasin_visible(magasin bigint) RETURNS boolean
LANGUAGE sql STABLE AS $$
    SELECT CASE coalesce(current_setting('{VARIABLE}', true), '')
        WHEN '' THEN true
        WHEN '{TOUT}' THEN true
        WHEN '{AUCUN}' THEN false
        ELSE magasin = ANY (string_to_array(current_setting('{VARIABLE}', true), ',')::bigint[])
    END
$$;
"""


def activer(table, condition):
    """SQL qui active la RLS sur ``table`` ; FORCE l'applique aussi au propriétaire de la table."""
    return f"""
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS perimetre_magasin ON {table};
CREATE POLICY perimetre_magasin ON {table} USING ({condition}) WITH CHECK ({condition});
"""


def desactiver(table):
    return f"""
DROP POLICY IF EXISTS perimetre_magasin ON {table};
ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;
ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;
"""
