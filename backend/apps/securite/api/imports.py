from drf_spectacular.utils import extend_schema

from apps.stock.api.imports import ImportSaisieSerializer, RapportImportSerializer, _Import

from ..imports import importer_utilisateurs


class ImportUtilisateursView(_Import):
    """Crée des comptes avec leurs profils ; mêmes contrôles que l'écran Accès et sécurité.

    Tout ou rien : à la moindre ligne en erreur, aucun compte n'est créé.
    """

    permissions_requises = {"post": ["securite.add_utilisateur", "securite.add_affectation"]}

    @extend_schema(
        request={"multipart/form-data": ImportSaisieSerializer},
        responses={200: RapportImportSerializer, 400: RapportImportSerializer},
    )
    def post(self, request):
        saisie = ImportSaisieSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        donnees = saisie.validated_data
        lignes, jeton, refus = self._lire(donnees, "utilisateurs", request.user.pk)
        if refus:
            return refus
        rapport = importer_utilisateurs(lignes, demandeur=request.user, apercu=donnees["apercu"])
        return self._rapport(rapport, jeton)
