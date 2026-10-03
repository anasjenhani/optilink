from rest_framework import viewsets

from ..models import Magasin, Societe
from .serializers import MagasinSerializer, SocieteSerializer


class MagasinViewSet(viewsets.ReadOnlyModelViewSet):
    """Magasins visibles par l'utilisateur connecté (filtrés par son périmètre)."""

    serializer_class = MagasinSerializer
    lookup_field = "public_id"
    filterset_fields = ["est_actif", "societe__code"]

    def get_queryset(self):
        # Appelé à chaque requête : le filtre de périmètre doit être évalué maintenant,
        # jamais à l'import du module.
        return Magasin.objects.select_related("societe", "pays")


class SocieteViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SocieteSerializer
    lookup_field = "public_id"
    queryset = Societe.objects.all()
