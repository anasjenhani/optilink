from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from apps.reseau.models import Magasin
from apps.stock.api.imports import ImportSaisieSerializer, RapportImportSerializer, _Import

from ..imports import importer_clients


class ImportClientsSaisieSerializer(ImportSaisieSerializer):
    magasin = serializers.UUIDField(help_text="Magasin d'origine des clients importés.")


class ImportClientsView(_Import):
    """Fiches clients depuis l'export d'un autre logiciel ; mise à jour par ancien n° de fiche.

    Tout ou rien : à la moindre ligne en erreur, aucun client n'est enregistré.
    """

    permissions_requises = {"post": ["crm.add_client", "crm.change_client"]}

    @extend_schema(
        request={"multipart/form-data": ImportClientsSaisieSerializer},
        responses={200: RapportImportSerializer, 400: RapportImportSerializer},
    )
    def post(self, request):
        saisie = ImportClientsSaisieSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        donnees = saisie.validated_data
        magasin = get_object_or_404(Magasin.objects.all(), public_id=donnees["magasin"])
        if not request.user.has_perm("crm.add_client", magasin):
            raise PermissionDenied("Pas de droit de création de client sur ce magasin.")
        lignes, jeton, refus = self._lire(donnees, "clients", magasin.pk)
        if refus:
            return refus
        rapport = importer_clients(lignes, magasin=magasin, apercu=donnees["apercu"])
        return self._rapport(rapport, jeton)
