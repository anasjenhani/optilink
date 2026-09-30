import uuid

from django.db import models


class ModeleDeBase(models.Model):
    """Colonnes communes : identifiant public stable et horodatage."""

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
