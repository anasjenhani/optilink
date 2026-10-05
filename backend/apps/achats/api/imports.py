from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from apps.reseau.models import Magasin, Pays
from apps.stock.api.imports import ImportSaisieSerializer, RapportImportSerializer, _Import

from ..imports import importer_fournisseurs, importer_receptions


class ImportFournisseursSaisieSerializer(ImportSaisieSerializer):
    pays = serializers.CharField(default="TN", help_text="Pays par défaut des fournisseurs.")


class ImportReceptionsSaisieSerializer(ImportSaisieSerializer):
    magasin = serializers.UUIDField(help_text="Magasin qui reçoit la marchandise.")


class ImportFournisseursView(_Import):
    """Crée les fournisseurs (code attribué) ou met à jour ceux déjà créés.

    Tout ou rien : à la moindre ligne en erreur, aucun fournisseur n'est enregistré.
    """

    permissions_requises = {"post": ["achats.add_fournisseur", "achats.change_fournisseur"]}

    @extend_schema(
        request={"multipart/form-data": ImportFournisseursSaisieSerializer},
        responses={200: RapportImportSerializer, 400: RapportImportSerializer},
    )
    def post(self, request):
        saisie = ImportFournisseursSaisieSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        donnees = saisie.validated_data
        pays = get_object_or_404(Pays, code=donnees["pays"].upper())
        lignes, jeton, refus = self._lire(donnees, "fournisseurs", pays.code)
        if refus:
            return refus
        rapport = importer_fournisseurs(lignes, pays=pays, apercu=donnees["apercu"])
        return self._rapport(rapport, jeton)


class ImportReceptionsView(_Import):
    """Bons de réception d'un magasin : un bon par BL, une ligne par article reçu.

    Tout ou rien : à la moindre ligne en erreur, aucun bon n'est enregistré.
    """

    permissions_requises = {"post": "achats.add_bonreception"}

    @extend_schema(
        request={"multipart/form-data": ImportReceptionsSaisieSerializer},
        responses={200: RapportImportSerializer, 400: RapportImportSerializer},
    )
    def post(self, request):
        saisie = ImportReceptionsSaisieSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        donnees = saisie.validated_data
        magasin = get_object_or_404(Magasin.objects.all(), public_id=donnees["magasin"])
        if not request.user.has_perm("achats.add_bonreception", magasin):
            raise PermissionDenied("Pas de droit de réception sur ce magasin.")
        lignes, jeton, refus = self._lire(donnees, "receptions", magasin.pk)
        if refus:
            return refus
        rapport = importer_receptions(
            lignes, magasin=magasin, utilisateur=request.user, apercu=donnees["apercu"]
        )
        return self._rapport(rapport, jeton)
