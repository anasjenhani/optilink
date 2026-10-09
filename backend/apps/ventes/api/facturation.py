from django.db.models import Count
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_field
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.crm.models import Client
from apps.reseau.models import Magasin

from .. import facturation
from ..models import ClotureMois, FactureGroupee, LigneVente, Vente
from ..services import FactureImpossible


class DetailTvaSerializer(serializers.Serializer):
    taux = serializers.DecimalField(max_digits=5, decimal_places=2)
    total_ht = serializers.DecimalField(max_digits=14, decimal_places=3)
    total_tva = serializers.DecimalField(max_digits=14, decimal_places=3)
    total_ttc = serializers.DecimalField(max_digits=14, decimal_places=3)


class VenteAFacturerSerializer(serializers.Serializer):
    id = serializers.UUIDField(source="public_id")
    numero = serializers.CharField()
    livree_le = serializers.DateTimeField()
    client = serializers.SerializerMethodField()
    client_id = serializers.SerializerMethodField()
    total_ht = serializers.DecimalField(max_digits=14, decimal_places=3)
    total_tva = serializers.DecimalField(max_digits=14, decimal_places=3)
    total_ttc = serializers.DecimalField(max_digits=14, decimal_places=3)
    reste_a_payer = serializers.DecimalField(max_digits=14, decimal_places=3)

    def get_client(self, vente) -> str | None:
        return str(vente.client) if vente.client else None

    def get_client_id(self, vente) -> str | None:
        return str(vente.client.public_id) if vente.client else None


class VenteFactureeSerializer(serializers.Serializer):
    numero = serializers.CharField()
    livree_le = serializers.DateTimeField()
    total_ttc = serializers.DecimalField(max_digits=14, decimal_places=3)


class LigneFactureGroupeeSerializer(serializers.ModelSerializer):
    vente = serializers.CharField(source="vente.numero")

    class Meta:
        model = LigneVente
        fields = [
            "vente",
            "libelle",
            "quantite",
            "prix_unitaire_ttc",
            "remise_pct",
            "taux_tva",
            "total_ttc",
        ]


class FactureGroupeeSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    magasin = serializers.CharField(source="magasin.code", read_only=True)
    magasin_nom = serializers.CharField(source="magasin.nom", read_only=True)
    type_libelle = serializers.CharField(source="get_type_display", read_only=True)
    client = serializers.SerializerMethodField()
    emise_par = serializers.CharField(source="emise_par.get_username", read_only=True)
    nombre_ventes = serializers.SerializerMethodField()

    class Meta:
        model = FactureGroupee
        fields = [
            "id",
            "numero",
            "type",
            "type_libelle",
            "magasin",
            "magasin_nom",
            "client",
            "client_nom",
            "client_adresse",
            "client_matricule_fiscal",
            "du",
            "au",
            "cree_le",
            "emise_par",
            "devise",
            "total_ht",
            "total_tva",
            "total_ttc",
            "timbre_fiscal",
            "net_a_payer",
            "mode_paiement_timbre",
            "nombre_ventes",
        ]

    def get_client(self, facture) -> str | None:
        return str(facture.client.public_id) if facture.client else None

    def get_nombre_ventes(self, facture) -> int:
        nombre = getattr(facture, "nombre_ventes", None)
        return facture.ventes.count() if nombre is None else nombre


class FactureGroupeeDetailSerializer(FactureGroupeeSerializer):
    ventes = serializers.SerializerMethodField()
    detail_tva = serializers.SerializerMethodField()
    lignes = serializers.SerializerMethodField()

    class Meta(FactureGroupeeSerializer.Meta):
        fields = FactureGroupeeSerializer.Meta.fields + ["ventes", "detail_tva", "lignes"]

    @extend_schema_field(VenteFactureeSerializer(many=True))
    def get_ventes(self, facture):
        ventes = facture.ventes.order_by("livree_le", "sequence")
        return VenteFactureeSerializer(ventes, many=True).data

    @extend_schema_field(DetailTvaSerializer(many=True))
    def get_detail_tva(self, facture):
        detail = facturation.detail_tva(facture.ventes.all(), facture.magasin.pays.decimales)
        return DetailTvaSerializer(detail, many=True).data

    @extend_schema_field(LigneFactureGroupeeSerializer(many=True))
    def get_lignes(self, facture):
        # La récapitulative du mois ne détaille pas les articles : elle peut en compter des
        # milliers. Le détail par taux de TVA suffit.
        if facture.type == FactureGroupee.Type.MENSUELLE:
            return []
        lignes = (
            LigneVente.objects.filter(vente__facture_groupee=facture)
            .select_related("vente")
            .order_by("vente__livree_le", "vente__sequence", "pk")
        )
        return LigneFactureGroupeeSerializer(lignes, many=True).data


class FactureGroupeeSaisieSerializer(serializers.Serializer):
    magasin = serializers.UUIDField()
    ventes = serializers.ListField(child=serializers.UUIDField(), min_length=1)
    client = serializers.UUIDField(required=False, allow_null=True)
    client_nom = serializers.CharField(required=False, allow_blank=True, max_length=200)
    client_adresse = serializers.CharField(required=False, allow_blank=True, max_length=320)
    client_matricule_fiscal = serializers.CharField(required=False, allow_blank=True, max_length=30)
    mode_paiement_timbre = serializers.CharField(required=False, allow_blank=True, max_length=20)


def _magasin(request, identifiant, permission):
    magasin = Magasin.objects.select_related("pays").filter(public_id=identifiant).first()
    if magasin is None:
        raise ValidationError({"magasin": "Magasin inconnu ou hors de votre périmètre."})
    if not request.user.has_perm(permission, magasin):
        raise PermissionDenied("Pas de droit sur la facturation de ce magasin.")
    return magasin


def _date(request, nom):
    valeur = request.query_params.get(nom)
    if not valeur:
        return None
    champ = serializers.DateField()
    try:
        return champ.to_internal_value(valeur)
    except serializers.ValidationError:
        raise ValidationError({nom: "Date invalide (AAAA-MM-JJ)."}) from None


class FactureGroupeeViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Factures groupées (plusieurs visites ou ventes comptoir) et récapitulatives du mois."""

    serializer_class = FactureGroupeeSerializer
    lookup_field = "public_id"
    permissions_requises = {
        "list": "ventes.view_facturegroupee",
        "retrieve": "ventes.view_facturegroupee",
        "create": "ventes.add_facturegroupee",
        "a_facturer": "ventes.add_facturegroupee",
    }

    def get_queryset(self):
        factures = FactureGroupee.objects.select_related(
            "magasin__pays", "client", "emise_par"
        ).annotate(nombre_ventes=Count("ventes"))
        parametres = self.request.query_params
        if parametres.get("magasin"):
            factures = factures.filter(magasin__public_id=parametres["magasin"])
        if parametres.get("type"):
            factures = factures.filter(type=parametres["type"])
        if parametres.get("client"):
            factures = factures.filter(client__public_id=parametres["client"])
        if parametres.get("numero"):
            factures = factures.filter(numero__icontains=parametres["numero"])
        return factures

    def get_serializer_class(self):
        if self.action == "retrieve":
            return FactureGroupeeDetailSerializer
        return FactureGroupeeSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter("magasin", OpenApiTypes.UUID),
            OpenApiParameter("type", OpenApiTypes.STR, enum=FactureGroupee.Type.values),
            OpenApiParameter("client", OpenApiTypes.UUID),
            OpenApiParameter("numero", OpenApiTypes.STR),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        parameters=[
            OpenApiParameter("magasin", OpenApiTypes.UUID, required=True),
            OpenApiParameter("client", OpenApiTypes.UUID),
            OpenApiParameter(
                "comptoir",
                OpenApiTypes.BOOL,
                description="true : ventes comptoir ; false : visites (lunettes, lentilles).",
            ),
            OpenApiParameter("du", OpenApiTypes.DATE),
            OpenApiParameter("au", OpenApiTypes.DATE),
        ],
        responses=VenteAFacturerSerializer(many=True),
    )
    @action(detail=False, url_path="a-facturer", pagination_class=None)
    def a_facturer(self, request):
        """Ventes livrées et soldées, sans facture, dans un mois encore ouvert."""
        if not request.query_params.get("magasin"):
            raise ValidationError({"magasin": "Choisir le magasin."})
        magasin = _magasin(request, request.query_params["magasin"], "ventes.add_facturegroupee")
        client = None
        if request.query_params.get("client"):
            client = get_object_or_404(Client, public_id=request.query_params["client"])
        comptoir = {"true": True, "false": False}.get(request.query_params.get("comptoir", ""))
        ventes = facturation.ventes_a_facturer(
            magasin,
            client=client,
            du=_date(request, "du"),
            au=_date(request, "au"),
            comptoir=comptoir,
        )
        return Response(VenteAFacturerSerializer(ventes, many=True).data)

    @extend_schema(
        request=FactureGroupeeSaisieSerializer, responses={201: FactureGroupeeDetailSerializer}
    )
    def create(self, request):
        saisie = FactureGroupeeSaisieSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        donnees = saisie.validated_data
        magasin = _magasin(request, donnees["magasin"], "ventes.add_facturegroupee")
        ventes = list(Vente.objects.filter(public_id__in=donnees["ventes"]))
        if len(ventes) != len(set(donnees["ventes"])):
            raise ValidationError({"ventes": "Vente inconnue ou hors de votre périmètre."})
        client = None
        if donnees.get("client"):
            client = Client.objects.filter(public_id=donnees["client"]).first()
            if client is None:
                raise ValidationError({"client": "Client inconnu."})
        try:
            facture = facturation.facturer_ensemble(
                magasin=magasin,
                ventes=ventes,
                emetteur=request.user,
                client=client,
                client_nom=donnees.get("client_nom", ""),
                client_adresse=donnees.get("client_adresse", ""),
                client_matricule_fiscal=donnees.get("client_matricule_fiscal", ""),
                mode_paiement_timbre=donnees.get("mode_paiement_timbre", ""),
            )
        except FactureImpossible as erreur:
            return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        facture = self.get_queryset().get(pk=facture.pk)
        return Response(
            FactureGroupeeDetailSerializer(facture).data, status=status.HTTP_201_CREATED
        )


class ClotureMoisSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    magasin = serializers.CharField(source="magasin.public_id", read_only=True)
    magasin_nom = serializers.CharField(source="magasin.nom", read_only=True)
    facture = serializers.SerializerMethodField()
    facture_numero = serializers.SerializerMethodField()
    total_ttc = serializers.SerializerMethodField()
    cloture_par = serializers.CharField(source="cloture_par.get_username", read_only=True)

    class Meta:
        model = ClotureMois
        fields = [
            "id",
            "magasin",
            "magasin_nom",
            "annee",
            "mois",
            "cree_le",
            "cloture_par",
            "facture",
            "facture_numero",
            "total_ttc",
        ]

    def get_facture(self, cloture) -> str | None:
        return str(cloture.facture.public_id) if cloture.facture else None

    def get_facture_numero(self, cloture) -> str | None:
        return cloture.facture.numero if cloture.facture else None

    def get_total_ttc(self, cloture) -> str:
        return str(cloture.facture.total_ttc) if cloture.facture else "0"


class PreparationClotureSerializer(serializers.Serializer):
    annee = serializers.IntegerField()
    mois = serializers.IntegerField()
    cloture = ClotureMoisSerializer(allow_null=True)
    ventes = VenteAFacturerSerializer(many=True)
    detail_tva = DetailTvaSerializer(many=True)
    total_ht = serializers.DecimalField(max_digits=14, decimal_places=3)
    total_tva = serializers.DecimalField(max_digits=14, decimal_places=3)
    total_ttc = serializers.DecimalField(max_digits=14, decimal_places=3)


class ClotureMoisSaisieSerializer(serializers.Serializer):
    magasin = serializers.UUIDField()
    annee = serializers.IntegerField(min_value=2000, max_value=2100)
    mois = serializers.IntegerField(min_value=1, max_value=12)


class ClotureMoisViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Clôture du mois : préparation (ce qui reste à facturer), puis facture récapitulative."""

    serializer_class = ClotureMoisSerializer
    pagination_class = None
    permissions_requises = {
        "list": "ventes.view_cloturemois",
        "preparation": "ventes.view_cloturemois",
        "create": "ventes.add_cloturemois",
    }

    def get_queryset(self):
        clotures = ClotureMois.objects.select_related("magasin", "facture", "cloture_par")
        if self.request.query_params.get("magasin"):
            clotures = clotures.filter(magasin__public_id=self.request.query_params["magasin"])
        return clotures

    @extend_schema(parameters=[OpenApiParameter("magasin", OpenApiTypes.UUID)])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        parameters=[
            OpenApiParameter("magasin", OpenApiTypes.UUID, required=True),
            OpenApiParameter("annee", OpenApiTypes.INT, required=True),
            OpenApiParameter("mois", OpenApiTypes.INT, required=True),
        ],
        responses=PreparationClotureSerializer,
    )
    @action(detail=False)
    def preparation(self, request):
        """Ventes du mois restées sans facture et leur TVA : ce que la clôture récapitulera."""
        saisie = ClotureMoisSaisieSerializer(data=request.query_params)
        saisie.is_valid(raise_exception=True)
        donnees = saisie.validated_data
        magasin = _magasin(request, donnees["magasin"], "ventes.view_cloturemois")
        resultat = facturation.preparer_cloture(magasin, donnees["annee"], donnees["mois"])
        return Response(PreparationClotureSerializer(resultat).data)

    @extend_schema(request=ClotureMoisSaisieSerializer, responses={201: ClotureMoisSerializer})
    def create(self, request):
        saisie = ClotureMoisSaisieSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        donnees = saisie.validated_data
        magasin = _magasin(request, donnees["magasin"], "ventes.add_cloturemois")
        try:
            cloture = facturation.cloturer_mois(
                magasin=magasin,
                annee=donnees["annee"],
                mois=donnees["mois"],
                utilisateur=request.user,
            )
        except FactureImpossible as erreur:
            return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        cloture = self.get_queryset().get(pk=cloture.pk)
        return Response(ClotureMoisSerializer(cloture).data, status=status.HTTP_201_CREATED)
