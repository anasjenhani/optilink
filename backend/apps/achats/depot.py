"""Dépôt central : la marchandise des fournisseurs y est reçue, contrôlée et facturée.

Le dépôt central est rattaché à un magasin. Quand la société a un dépôt central, les BL des
articles de stock, les factures achat et les bons retour se saisissent au magasin qui l'abrite,
et les articles entrent dans le dépôt central. Un autre magasin saisit seulement le BL des
verres commandés pour ses clients ; ce BL reste géré au dépôt (facture, bon retour). Une
société sans dépôt central garde tout au magasin.

Les fonctions ci-dessous renvoient des magasins : le « dépôt » est le magasin qui l'abrite.
"""

from apps.reseau.models import Depot, Magasin


def depot_de(magasin):
    """Magasin qui abrite le dépôt central actif de la société (le magasin lui-même, s'il
    l'abrite)."""
    if magasin.est_depot:
        return magasin
    central = (
        Depot.objects.filter(
            magasin__societe_id=magasin.societe_id, type=Depot.Type.CENTRAL, est_actif=True
        )
        .select_related("magasin")
        .order_by("code")
        .first()
    )
    return Magasin.tous.get(pk=central.magasin_id) if central else None


def magasins_geres(magasin):
    """Magasins dont les BL sont facturés ici : le magasin, et pour un dépôt toute sa société."""
    if magasin.est_depot:
        return list(Magasin.tous.filter(societe_id=magasin.societe_id).values_list("pk", flat=True))
    return [magasin.pk]


def autre_depot(magasin):
    """Dépôt central où se saisissent les achats de ce magasin, s'il n'est pas lui-même ce dépôt."""
    depot = depot_de(magasin)
    return depot if depot is not None and depot.pk != magasin.pk else None
