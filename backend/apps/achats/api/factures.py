"""API des factures achat (factures fournisseurs)."""

import uuid

from django.db.models import Prefetch, Q, Sum
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.reseau.models import Magasin

from ..factures import (
    FactureImpossible,
    bons_a_facturer,
    calculer_facture,
    controler,
    enregistrer_facture,
    timbre_par_defaut,
)
from ..models import BonReception, FactureAchat, Fournisseur, LigneReception
from .serializers import BonReceptionListeSerializer

DECIMAL = {"max_digits": 14, "decimal_places": 3}


class FactureAchatSaisieSerializer(serializers.Serializer):
    magasin = serializers.UUIDField()
    fournisseur = serializers.UUIDField()
    reference_fournisseur = serializers.CharField(max_length=60, required=False, allow_blank=True)
    date_reference = serializers.DateField(required=False)
    date_entree = serializers.DateField(required=False)
    bons = serializers.ListField(child=serializers.UUIDField(), allow_empty=True)
    taux_remise_ex = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=0, max_value=100, default=0
    )
    frais_supplementaires = serializers.DecimalField(**DECIMAL, min_value=0, default=0)
    timbre_fiscal = serializers.DecimalField(
        max_digits=10, decimal_places=3, min_value=0, required=False, allow_null=True
    )
    ajustement = serializers.DecimalField(max_digits=10, decimal_places=3, default=0)
    observation = serializers.CharField(required=False, allow_blank=True)


class BonFactureSerializer(BonReceptionListeSerializer):
    class Meta(BonReceptionListeSerializer.Meta):
        fields = BonReceptionListeSerializer.Meta.fields + [
            "total_remise",
            "remise_ex",
            "total_fodec",
            "total_tva",
        ]


class LigneFactureSerializer(serializers.ModelSerializer):
    bon = serializers.CharField(source="bon.numero")
    article = serializers.UUIDField(source="article.public_id")
    famille = serializers.CharField(source="article.famille")
    code = serializers.SerializerMethodField(help_text="Code-barres, sinon référence.")
    etui = serializers.BooleanField(source="article.etui_special")
    montant_ht = serializers.SerializerMethodField()
    montant_remise = serializers.SerializerMethodField()

    class Meta:
        model = LigneReception
        fields = [
            "bon",
            "article",
            "famille",
            "code",
            "designation",
            "etui",
            "quantite",
            "prix_achat_ht",
            "montant_ht",
            "taux_remise",
            "montant_remise",
            "net_ht",
            "taux_tva",
            "montant_ttc",
            "numero_serie",
        ]

    def get_code(self, ligne) -> str:
        return ligne.article.code_barres or ligne.article.reference

    def get_montant_ht(self, ligne) -> str:
        return str(ligne.prix_achat_ht * ligne.quantite)

    def get_montant_remise(self, ligne) -> str:
        return str(ligne.prix_achat_ht * ligne.quantite - ligne.net_ht)


class FactureAchatListeSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    magasin = serializers.CharField(source="magasin.nom", read_only=True)
    fournisseur = serializers.CharField(source="fournisseur.nom", read_only=True)
    fournisseur_code = serializers.IntegerField(source="fournisseur.code", read_only=True)
    paiement_libelle = serializers.CharField(source="get_paiement_display", read_only=True)
    cree_par = serializers.SerializerMethodField()
    nombre_bons = serializers.SerializerMethodField()

    class Meta:
        model = FactureAchat
        fields = [
            "id",
            "numero",
            "magasin",
            "date_entree",
            "fournisseur",
            "fournisseur_code",
            "reference_fournisseur",
            "date_reference",
            "total_net_ht",
            "total_tva",
            "total_ttc",
            "paiement",
            "paiement_libelle",
            "nombre_bons",
            "cree_par",
            "cree_le",
        ]

    def get_cree_par(self, facture) -> str:
        return facture.cree_par.get_full_name() or facture.cree_par.get_username()

    def get_nombre_bons(self, facture) -> int:
        return len(facture.bons.all())


class FactureAchatSerializer(FactureAchatListeSerializer):
    devise = serializers.CharField(source="magasin.pays.devise", read_only=True)
    bons = BonFactureSerializer(many=True, read_only=True)
    lignes = serializers.SerializerMethodField()
    detail_tva = serializers.SerializerMethodField()

    class Meta(FactureAchatListeSerializer.Meta):
        fields = FactureAchatListeSerializer.Meta.fields + [
            "devise",
            "taux_remise_ex",
            "total_ht",
            "total_remise",
            "remise_ex",
            "total_fodec",
            "frais_supplementaires",
            "timbre_fiscal",
            "ajustement",
            "observation",
            "bons",
            "lignes",
            "detail_tva",
        ]

    def get_lignes(self, facture) -> list[dict]:
        lignes = [
            ligne
            for bon in facture.bons.all()
            for ligne in bon.lignes.all()
            if not ligne.non_conforme
        ]
        return LigneFactureSerializer(lignes, many=True).data

    def get_detail_tva(self, facture) -> list[dict]:
        _, tva = calculer_facture(
            facture.bons.all(),
            pays=facture.magasin.pays,
            taux_remise_ex=facture.taux_remise_ex,
        )
        return [{k: str(v) for k, v in t.items()} for t in tva]


def _texte(totaux):
    return {k: str(v) for k, v in totaux.items()}


class FactureAchatViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Factures achat : liste, détail, BL à facturer, aperçu des totaux et saisie."""

    lookup_field = "public_id"
    permissions_requises = {
        "list": "achats.view_factureachat",
        "retrieve": "achats.view_factureachat",
        "create": "achats.add_factureachat",
        "a_facturer": "achats.add_factureachat",
        "apercu": "achats.add_factureachat",
    }
    FILTRES = {
        "numero": "numero__icontains",
        "fournisseur": "fournisseur__nom__icontains",
        "reference_fournisseur": "reference_fournisseur__icontains",
        "paiement": "paiement",
        "du": "date_entree__gte",
        "au": "date_entree__lte",
        "magasin": "magasin__public_id",
    }

    def get_serializer_class(self):
        return FactureAchatListeSerializer if self.action == "list" else FactureAchatSerializer

    def get_queryset(self):
        lignes = LigneReception.objects.select_related("article", "bon")
        factures = (
            FactureAchat.objects.select_related("magasin__pays", "fournisseur", "cree_par")
            .prefetch_related(
                Prefetch(
                    "bons",
                    queryset=BonReception.objects.select_related(
                        "magasin__pays", "fournisseur", "cree_par"
                    )
                    .prefetch_related(Prefetch("lignes", queryset=lignes))
                    .annotate(
                        total_articles=Sum("lignes__quantite", filter=Q(lignes__non_conforme=False))
                    )
                    .order_by("date_bl", "sequence"),
                )
            )
            .order_by("-annee", "-sequence")
        )
        if self.action == "list":
            for cle, critere in self.FILTRES.items():
                valeur = self.request.query_params.get(cle, "").strip()
                if valeur:
                    factures = factures.filter(**{critere: valeur})
        return factures

    def list(self, request, *args, **kwargs):
        reponse = super().list(request, *args, **kwargs)
        totaux = self.filter_queryset(self.get_queryset()).aggregate(
            total_net_ht=Sum("total_net_ht"), total_tva=Sum("total_tva"), total_ttc=Sum("total_ttc")
        )
        if isinstance(reponse.data, dict):
            reponse.data["totaux"] = {cle: str(v or 0) for cle, v in totaux.items()}
        return reponse

    def _magasin(self, identifiant, droit="achats.add_factureachat"):
        try:
            uuid.UUID(str(identifiant))
        except ValueError:
            raise ValidationError({"magasin": "Identifiant invalide."}) from None
        magasin = Magasin.objects.select_related("pays").filter(public_id=identifiant).first()
        if magasin is None:
            raise ValidationError({"magasin": "Magasin inconnu ou hors de votre périmètre."})
        if not self.request.user.has_perm(droit, magasin):
            raise PermissionDenied("Pas de droit sur les factures achat de ce magasin.")
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
        responses={200: OpenApiTypes.OBJECT},
    )
    @action(detail=False, methods=["get"], url_path="a-facturer")
    def a_facturer(self, request):
        """BL de ce fournisseur dans ce magasin pas encore facturés (« Importer BL »)."""
        magasin = self._magasin(request.query_params.get("magasin", ""))
        fournisseur = self._fournisseur(request.query_params.get("fournisseur", ""))
        bons = (
            bons_a_facturer(magasin, fournisseur)
            .select_related("magasin", "fournisseur", "cree_par")
            .prefetch_related("lignes__article")
            .annotate(total_articles=Sum("lignes__quantite", filter=Q(lignes__non_conforme=False)))
        )
        return Response(
            {
                "timbre_fiscal": str(timbre_par_defaut(fournisseur, magasin.pays)),
                "bons": BonFactureSerializer(bons, many=True).data,
            }
        )

    @extend_schema(request=FactureAchatSaisieSerializer, responses={200: OpenApiTypes.OBJECT})
    @action(detail=False, methods=["post"])
    def apercu(self, request):
        """Totaux, TVA et lignes de la facture en cours de saisie, sans l'enregistrer."""
        donnees = self._saisie(request)
        magasin = self._magasin(donnees["magasin"])
        fournisseur = self._fournisseur(donnees["fournisseur"])
        try:
            bons = controler(magasin, fournisseur, donnees["bons"]) if donnees["bons"] else []
        except FactureImpossible as erreur:
            return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        timbre = donnees.get("timbre_fiscal")
        totaux, tva = calculer_facture(
            bons,
            pays=magasin.pays,
            taux_remise_ex=donnees["taux_remise_ex"],
            frais=donnees["frais_supplementaires"],
            timbre=timbre_par_defaut(fournisseur, magasin.pays) if timbre is None else timbre,
            ajustement=donnees["ajustement"],
        )
        lignes = [ligne for bon in bons for ligne in bon.lignes.all() if not ligne.non_conforme]
        return Response(
            {
                **_texte(totaux),
                "detail_tva": [_texte(t) for t in tva],
                "lignes": LigneFactureSerializer(lignes, many=True).data,
            }
        )

    def _saisie(self, request):
        saisie = FactureAchatSaisieSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        return saisie.validated_data

    @extend_schema(request=FactureAchatSaisieSerializer, responses={201: FactureAchatSerializer})
    def create(self, request):
        donnees = self._saisie(request)
        magasin = self._magasin(donnees["magasin"])
        fournisseur = self._fournisseur(donnees["fournisseur"])
        if not donnees.get("date_reference"):
            raise ValidationError({"date_reference": "Date de la facture fournisseur obligatoire."})
        try:
            facture = enregistrer_facture(
                magasin=magasin,
                fournisseur=fournisseur,
                reference_fournisseur=donnees.get("reference_fournisseur", ""),
                date_reference=donnees["date_reference"],
                date_entree=donnees.get("date_entree"),
                bons=donnees["bons"],
                taux_remise_ex=donnees["taux_remise_ex"],
                frais=donnees["frais_supplementaires"],
                timbre=donnees.get("timbre_fiscal"),
                ajustement=donnees["ajustement"],
                observation=donnees.get("observation", ""),
                auteur=request.user,
            )
        except FactureImpossible as erreur:
            return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        facture = self.get_queryset().get(pk=facture.pk)
        return Response(FactureAchatSerializer(facture).data, status=status.HTTP_201_CREATED)
