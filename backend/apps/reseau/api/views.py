from rest_framework import viewsets

from ..models import Magasin, Societe, Ville
from .serializers import MagasinSerializer, SocieteSerializer, VilleSerializer


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


class VilleViewSet(viewsets.ReadOnlyModelViewSet):
    """Villes proposées sur les fiches ; la liste se tient dans /admin/ (Réseau › Villes)."""

    serializer_class = VilleSerializer
    pagination_class = None
    # Toute personne qui remplit une fiche choisit sa ville : la liste n'a rien de confidentiel.
    permissions_requises = {"list": []}
    filterset_fields = {"pays__code": ["exact"]}

    def get_queryset(self):
        return Ville.objects.filter(est_active=True).select_related("pays")
