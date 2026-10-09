"""Corbeille : éléments supprimés, restaurables pendant le délai de grâce."""

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from ..corbeille import RestaurationImpossible, restaurer
from ..models import ElementCorbeille


class ElementCorbeilleSerializer(serializers.ModelSerializer):
    supprime_par = serializers.SerializerMethodField()
    jours_de_grace = serializers.SerializerMethodField()

    class Meta:
        model = ElementCorbeille
        fields = [
            "id",
            "type_libelle",
            "libelle",
            "nombre_objets",
            "supprime_par",
            "supprime_le",
            "expire_le",
            "jours_de_grace",
        ]

    def get_supprime_par(self, element) -> str:
        auteur = element.supprime_par
        return (auteur.get_full_name() or auteur.get_username()) if auteur else ""

    def get_jours_de_grace(self, element) -> int:
        return settings.CORBEILLE_JOURS


class CorbeilleViewSet(mixins.ListModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """Éléments supprimés que l'utilisateur a le droit de créer : il peut les
    restaurer ; « supprimer » ici efface définitivement, sans attendre la fin du délai."""

    serializer_class = ElementCorbeilleSerializer
    permissions_requises = {
        "list": "securite.view_elementcorbeille",
        "restaurer": "securite.restaurer_elementcorbeille",
        "destroy": "securite.delete_elementcorbeille",
    }

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ElementCorbeille.objects.none()
        elements = ElementCorbeille.objects.select_related("supprime_par")
        params = self.request.query_params
        recherche = params.get("recherche", "").strip()
        if recherche:
            elements = elements.filter(libelle__icontains=recherche)
        type_libelle = params.get("type", "").strip()
        if type_libelle:
            elements = elements.filter(type_libelle=type_libelle)
        utilisateur = self.request.user
        if utilisateur.is_superuser:
            return elements
        visibles = [e.pk for e in elements if utilisateur.has_perm(e.permission_ajout, e)]
        return elements.filter(pk__in=visibles)

    def get_object(self):
        # En plus du droit sur la corbeille : celui de créer ce type d'élément, ici.
        element = super().get_object()
        if not self.request.user.has_perm(element.permission_ajout, element):
            raise PermissionDenied("Vous n'avez pas le droit de créer ce type d'élément.")
        return element

    @extend_schema(request=None, responses={204: None})
    @action(detail=True, methods=["post"])
    def restaurer(self, request, pk=None):
        element = self.get_object()
        try:
            restaurer(element)
        except RestaurationImpossible as erreur:
            return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def perform_destroy(self, element):
        element.delete()
