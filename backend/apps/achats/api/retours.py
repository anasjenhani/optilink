"""API des bons retour fournisseur (marchandise renvoyée, déduite de la facture achat)."""

import uuid

from django.db.models import Prefetch, Sum
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.reseau.models import Magasin
from apps.stock.models import Article

from ..models import BonRetour, Fournisseur, LigneReception, LigneRetour
from ..retours import RetourImpossible, enregistrer_retour, non_conformes_a_retourner

DECIMAL = {"max_digits": 12, "decimal_places": 3}


class LigneRetourSaisieSerializer(serializers.Serializer):
    ligne_reception = serializers.IntegerField(
        required=False, help_text="Ligne non conforme d'un bon de réception à renvoyer."
    )
    article = serializers.UUIDField(required=False, help_text="Article du stock à renvoyer.")
    quantite = serializers.IntegerField(min_value=1, required=False)
    prix_achat_ht = serializers.DecimalField(**DECIMAL, min_value=0, required=False)
    taux_remise = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=0, max_value=100, default=0
    )
    taux_tva = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=0, max_value=100, required=False
    )
    motif = serializers.CharField(max_length=200, required=False, allow_blank=True)

    def validate(self, donnees):
        if "ligne_reception" in donnees:
            return donnees
        manquants = [
            nom
            for nom in ("article", "quantite", "prix_achat_ht", "taux_tva")
            if nom not in donnees
        ]
        if manquants:
            raise serializers.ValidationError(
                f"Article du stock : {', '.join(manquants)} obligatoire(s)."
            )
        return donnees


class BonRetourSaisieSerializer(serializers.Serializer):
    magasin = serializers.UUIDField()
    fournisseur = serializers.UUIDField()
    date_retour = serializers.DateField(required=False)
    motif = serializers.CharField(max_length=200, required=False, allow_blank=True)
    observation = serializers.CharField(required=False, allow_blank=True)
    lignes = LigneRetourSaisieSerializer(many=True)


class NonConformeSerializer(serializers.ModelSerializer):
    bon = serializers.CharField(source="bon.numero")
    numero_bl = serializers.CharField(source="bon.numero_bl")
    date_bl = serializers.DateField(source="bon.date_bl")
    magasin = serializers.CharField(source="bon.magasin.nom")
    code = serializers.SerializerMethodField()

    class Meta:
        model = LigneReception
        fields = [
            "id",
            "bon",
            "numero_bl",
            "date_bl",
            "magasin",
            "code",
            "designation",
            "quantite",
            "prix_achat_ht",
            "taux_remise",
            "taux_tva",
            "net_ht",
            "montant_ttc",
            "motif",
        ]

    def get_code(self, ligne) -> str:
        return ligne.article.code_barres or ligne.article.reference


class LigneRetourSerializer(serializers.ModelSerializer):
    article = serializers.UUIDField(source="article.public_id")
    famille = serializers.CharField(source="article.famille")
    code = serializers.SerializerMethodField()
    bon_reception = serializers.SerializerMethodField(help_text="BL d'origine (non conforme).")

    class Meta:
        model = LigneRetour
        fields = [
            "article",
            "famille",
            "code",
            "designation",
            "quantite",
            "prix_achat_ht",
            "taux_remise",
            "taux_tva",
            "net_ht",
            "montant_ttc",
            "motif",
            "bon_reception",
        ]

    def get_code(self, ligne) -> str:
        return ligne.article.code_barres or ligne.article.reference

    def get_bon_reception(self, ligne) -> str:
        source = ligne.ligne_reception
        return f"{source.bon.numero} (BL {source.bon.numero_bl})" if source else ""


class BonRetourListeSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    magasin = serializers.CharField(source="magasin.nom", read_only=True)
    fournisseur = serializers.CharField(source="fournisseur.nom", read_only=True)
    fournisseur_code = serializers.IntegerField(source="fournisseur.code", read_only=True)
    etat_libelle = serializers.CharField(source="get_etat_display", read_only=True)
    facture = serializers.CharField(source="facture.numero", read_only=True, allow_null=True)
    total_articles = serializers.IntegerField(read_only=True)
    cree_par = serializers.SerializerMethodField()

    class Meta:
        model = BonRetour
        fields = [
            "id",
            "numero",
            "magasin",
            "date_retour",
            "fournisseur",
            "fournisseur_code",
            "motif",
            "etat",
            "etat_libelle",
            "facture",
            "total_articles",
            "total_ht",
            "total_remise",
            "total_net_ht",
            "total_fodec",
            "total_tva",
            "total_ttc",
            "cree_par",
            "cree_le",
        ]

    def get_cree_par(self, bon) -> str:
        return bon.cree_par.get_full_name() or bon.cree_par.get_username()


class BonRetourSerializer(BonRetourListeSerializer):
    devise = serializers.CharField(source="magasin.pays.devise", read_only=True)
    lignes = LigneRetourSerializer(many=True, read_only=True)

    class Meta(BonRetourListeSerializer.Meta):
        fields = BonRetourListeSerializer.Meta.fields + ["devise", "observation", "lignes"]


class BonRetourViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Bons retour fournisseur : liste, détail, non conformes à renvoyer et saisie."""

    lookup_field = "public_id"
    permissions_requises = {
        "list": "achats.view_bonretour",
        "retrieve": "achats.view_bonretour",
        "create": "achats.add_bonretour",
        "a_retourner": "achats.add_bonretour",
    }
    FILTRES = {
        "numero": "numero__icontains",
        "fournisseur": "fournisseur__nom__icontains",
        "etat": "etat",
        "du": "date_retour__gte",
        "au": "date_retour__lte",
        "magasin": "magasin__public_id",
    }

    def get_serializer_class(self):
        return BonRetourListeSerializer if self.action == "list" else BonRetourSerializer

    def get_queryset(self):
        lignes = LigneRetour.objects.select_related("article", "ligne_reception__bon")
        bons = (
            BonRetour.objects.select_related("magasin__pays", "fournisseur", "cree_par", "facture")
            .prefetch_related(Prefetch("lignes", queryset=lignes))
            .annotate(total_articles=Sum("lignes__quantite"))
            .order_by("-annee", "-sequence")
        )
        if self.action == "list":
            for cle, critere in self.FILTRES.items():
                valeur = self.request.query_params.get(cle, "").strip()
                if valeur:
                    bons = bons.filter(**{critere: valeur})
        return bons

    def list(self, request, *args, **kwargs):
        reponse = super().list(request, *args, **kwargs)
        totaux = self.filter_queryset(self.get_queryset()).aggregate(
            total_net_ht=Sum("total_net_ht"), total_tva=Sum("total_tva"), total_ttc=Sum("total_ttc")
        )
        if isinstance(reponse.data, dict):
            reponse.data["totaux"] = {cle: str(v or 0) for cle, v in totaux.items()}
        return reponse

    def _magasin(self, identifiant):
        try:
            uuid.UUID(str(identifiant))
        except ValueError:
            raise ValidationError({"magasin": "Identifiant invalide."}) from None
        magasin = Magasin.objects.select_related("pays").filter(public_id=identifiant).first()
        if magasin is None:
            raise ValidationError({"magasin": "Magasin inconnu ou hors de votre périmètre."})
        if not self.request.user.has_perm("achats.add_bonretour", magasin):
            raise PermissionDenied("Pas de droit sur les bons retour de ce magasin.")
        return magasin

    def _fournisseur(self, identifiant):
        try:
            return get_object_or_404(Fournisseur, public_id=uuid.UUID(str(identifiant)))
        except ValueError:
            raise ValidationError({"fournisseur": "Identifiant invalide."}) from None

    @extend_schema(
        parameters=[
            OpenApiParameter("magasin", OpenApiTypes.UUID, required=True),
            OpenApiParameter("fournisseur", OpenApiTypes.UUID, required=True),
        ],
        responses={200: NonConformeSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="a-retourner")
    def a_retourner(self, request):
        """Lignes non conformes des BL de ce fournisseur, pas encore renvoyées."""
        magasin = self._magasin(request.query_params.get("magasin", ""))
        fournisseur = self._fournisseur(request.query_params.get("fournisseur", ""))
        lignes = non_conformes_a_retourner(magasin, fournisseur)
        return Response(NonConformeSerializer(lignes, many=True).data)

    @extend_schema(request=BonRetourSaisieSerializer, responses={201: BonRetourSerializer})
    def create(self, request):
        saisie = BonRetourSaisieSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        donnees = saisie.validated_data
        magasin = self._magasin(donnees["magasin"])
        fournisseur = self._fournisseur(donnees["fournisseur"])
        articles = {
            a.public_id: a
            for a in Article.objects.filter(
                public_id__in=[x["article"] for x in donnees["lignes"] if "article" in x]
            )
        }
        lignes = []
        for ligne in donnees["lignes"]:
            if "ligne_reception" in ligne:
                lignes.append(
                    {"ligne_reception": ligne["ligne_reception"], "motif": ligne.get("motif", "")}
                )
                continue
            article = articles.get(ligne["article"])
            if article is None:
                raise ValidationError({"lignes": "Article inconnu."})
            lignes.append({**ligne, "article": article})
        try:
            bon = enregistrer_retour(
                magasin=magasin,
                fournisseur=fournisseur,
                lignes=lignes,
                auteur=request.user,
                date_retour=donnees.get("date_retour"),
                motif=donnees.get("motif", ""),
                observation=donnees.get("observation", ""),
            )
        except RetourImpossible as erreur:
            return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        bon = self.get_queryset().get(pk=bon.pk)
        return Response(BonRetourSerializer(bon).data, status=status.HTTP_201_CREATED)
