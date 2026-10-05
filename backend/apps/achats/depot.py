"""Dépôt central : la marchandise des fournisseurs y est reçue, contrôlée et facturée.

Quand la société d'un magasin a un dépôt central, les BL des articles de stock, les factures
achat et les bons retour se saisissent au dépôt. Un magasin saisit seulement le BL des verres
commandés pour ses clients ; ce BL reste géré par le dépôt (facture, bon retour). Une société
sans dépôt garde tout au magasin.
"""

from apps.reseau.models import Magasin


def depot_de(magasin):
    """Dépôt central actif de la société du magasin (le magasin lui-même s'il en est un)."""
    if magasin.est_depot:
        return magasin
    return (
        Magasin.tous.filter(societe_id=magasin.societe_id, type=Magasin.Type.DEPOT, est_actif=True)
        .order_by("code")
        .first()
    )


def magasins_geres(magasin):
    """Magasins dont les BL sont facturés ici : le magasin, et pour un dépôt toute sa société."""
    if magasin.est_depot:
        return list(Magasin.tous.filter(societe_id=magasin.societe_id).values_list("pk", flat=True))
    return [magasin.pk]


def autre_depot(magasin):
    """Dépôt central où se saisissent les achats de ce magasin, s'il n'est pas lui-même ce dépôt."""
    depot = depot_de(magasin)
    return depot if depot is not None and depot.pk != magasin.pk else None
