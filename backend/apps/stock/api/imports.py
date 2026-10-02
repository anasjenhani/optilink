from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.reseau.models import Magasin, Pays

from ..imports import FichierIllisible, importer_catalogue, importer_stock, lire_tableau


class ImportSaisieSerializer(serializers.Serializer):
    fichier = serializers.FileField(help_text="Excel (.xlsx) ou CSV, ligne d'en-tête en premier.")
    apercu = serializers.BooleanField(
        default=False, help_text="Contrôle le fichier sans rien enregistrer."
    )


class ImportCatalogueSaisieSerializer(ImportSaisieSerializer):
    pays = serializers.CharField(
        default="TN", help_text="Code du pays des colonnes prix_ttc et tva."
    )


class ImportStockSaisieSerializer(ImportSaisieSerializer):
    magasin = serializers.UUIDField()
    piece = serializers.CharField(
        required=False, allow_blank=True, max_length=60, help_text="N° du bon de livraison."
    )


class ErreurImportSerializer(serializers.Serializer):
    ligne = serializers.IntegerField()
    message = serializers.CharField()


class RapportImportSerializer(serializers.Serializer):
    apercu = serializers.BooleanField()
    lignes = serializers.IntegerField()
    crees = serializers.IntegerField()
    modifies = serializers.IntegerField()
    erreurs = ErreurImportSerializer(many=True)


class _Import(APIView):
    parser_classes = [MultiPartParser]

    def _repondre(self, rapport):
        code = status.HTTP_400_BAD_REQUEST if rapport.erreurs else status.HTTP_200_OK
        return Response(RapportImportSerializer(rapport).data, status=code)

    def _lire(self, fichier):
        try:
            return lire_tableau(fichier), None
        except FichierIllisible as erreur:
            return None, Response({"fichier": [str(erreur)]}, status=status.HTTP_400_BAD_REQUEST)


class ImportCatalogueView(_Import):
    """Crée ou met à jour les articles du catalogue, leur fiche et leur prix, depuis un fichier.

    Tout ou rien : à la moindre ligne en erreur, aucun article n'est enregistré.
    """

    permissions_requises = {
        "post": [
            "stock.add_article",
            "stock.change_article",
            "stock.add_prixarticle",
            "stock.change_prixarticle",
        ]
    }

    @extend_schema(
        request={"multipart/form-data": ImportCatalogueSaisieSerializer},
        responses={200: RapportImportSerializer, 400: RapportImportSerializer},
    )
    def post(self, request):
        saisie = ImportCatalogueSaisieSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        donnees = saisie.validated_data
        pays = get_object_or_404(Pays, code=donnees["pays"].upper())
        lignes, erreur = self._lire(donnees["fichier"])
        if erreur:
            return erreur
        return self._repondre(importer_catalogue(lignes, pays=pays, apercu=donnees["apercu"]))


class ImportStockView(_Import):
    """Entrées de stock d'un magasin depuis un fichier (bon de livraison d'un fournisseur).

    Tout ou rien : à la moindre ligne en erreur, aucune entrée n'est enregistrée.
    """

    permissions_requises = {"post": "stock.add_mouvementstock"}

    @extend_schema(
        request={"multipart/form-data": ImportStockSaisieSerializer},
        responses={200: RapportImportSerializer, 400: RapportImportSerializer},
    )
    def post(self, request):
        saisie = ImportStockSaisieSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        donnees = saisie.validated_data
        magasin = get_object_or_404(Magasin.objects.all(), public_id=donnees["magasin"])
        if not request.user.has_perm("stock.add_mouvementstock", magasin):
            raise PermissionDenied("Pas de droit de saisie de stock sur ce magasin.")
        lignes, erreur = self._lire(donnees["fichier"])
        if erreur:
            return erreur
        rapport = importer_stock(
            lignes,
            magasin=magasin,
            utilisateur=request.user,
            piece=donnees.get("piece", ""),
            apercu=donnees["apercu"],
        )
        return self._repondre(rapport)
