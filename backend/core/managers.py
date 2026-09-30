from django.db import models

from .perimetre import perimetre_actuel


class ParMagasinManager(models.Manager):
    """Manager par défaut des données de magasin : filtre sur le périmètre de la requête.

    ``champ`` désigne la colonne qui porte le magasin (``magasin_id`` en général,
    ``id`` pour la table des magasins elle-même). Déclarer aussi ``tous = models.Manager()``
    sur le modèle pour les rares lectures volontairement hors périmètre.
    """

    def __init__(self, champ="magasin_id"):
        super().__init__()
        self.champ = champ

    def deconstruct(self):
        manager_only, path, qs_class, args, kwargs = super().deconstruct()
        return manager_only, path, qs_class, (self.champ,), kwargs

    def get_queryset(self):
        queryset = super().get_queryset()
        ids = perimetre_actuel()
        if ids is None:
            return queryset
        return queryset.filter(**{f"{self.champ}__in": ids})
