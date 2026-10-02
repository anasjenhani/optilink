from rest_framework import viewsets

from ..models import Magasin
from .serializers import MagasinSerializer


class MagasinViewSet(viewsets.ReadOnlyModelViewSet):
    """Magasins visibles par l'utilisateur connecté (filtrés par son périmètre)."""

    serializer_class = MagasinSerializer
    lookup_field = "public_id"
    filterset_fields = ["est_actif", "region__code"]

    def get_queryset(self):
        # Appelé à chaque requête : le filtre de périmètre doit être évalué maintenant,
        # jamais à l'import du module.
        return Magasin.objects.select_related("region", "pays")
