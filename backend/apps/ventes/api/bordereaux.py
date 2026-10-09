import uuid
from decimal import Decimal

from django.db.models import Prefetch
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.crm.models import Organisme
from apps.reseau.models import Magasin

from .. import bordereaux
from ..models import BordereauPec, LigneVente, PriseEnCharge


class LigneFactureSerializer(serializers.Serializer):
    libelle = serializers.CharField()
    quantite = serializers.IntegerField()
    total_ttc = serializers.DecimalField(max_digits=14, decimal_places=3)


class PecBordereauSerializer(serializers.ModelSerializer):
    """Une prise en charge, avec ce qu'il faut pour sa facture à l'organisme."""

    id = serializers.UUIDField(source="public_id", read_only=True)
    vente_numero = serializers.CharField(source="vente.numero")
    vente_date = serializers.DateTimeField(source="vente.cree_le")
    vente_total_ttc = serializers.DecimalField(
        source="vente.total_ttc", max_digits=14, decimal_places=3
    )
    client = serializers.SerializerMethodField()
    numero_affilie = serializers.SerializerMethodField()
    statut_libelle = serializers.CharField(source="get_statut_display")
    lignes = serializers.SerializerMethodField()

    class Meta:
        model = PriseEnCharge
        fields = [
            "id",
            "vente_numero",
            "vente_date",
            "vente_total_ttc",
            "client",
            "numero_affilie",
            "numero_dossier",
            "montant",
            "montant_regle",
            "motif_rejet",
            "statut",
            "statut_libelle",
            "lignes",
        ]

    def get_client(self, pec) -> str | None:
        return str(pec.vente.client) if pec.vente.client else None

    def get_numero_affilie(self, pec) -> str:
        return pec.vente.client.numero_affilie if pec.vente.client else ""

    def get_lignes(self, pec) -> LigneFactureSerializer(many=True):
        return LigneFactureSerializer(pec.vente.lignes.all(), many=True).data


class BordereauSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    magasin = serializers.CharField(source="magasin.public_id")
    magasin_nom = serializers.CharField(source="magasin.nom")
    devise = serializers.CharField(source="magasin.pays.devise")
    decimales = serializers.IntegerField(source="magasin.pays.decimales")
    organisme = serializers.CharField(source="organisme.public_id")
    organisme_nom = serializers.CharField(source="organisme.nom")
    organisme_type = serializers.CharField(source="organisme.get_type_display")
    statut_libelle = serializers.CharField(source="get_statut_display")
    mode_reglement_libelle = serializers.CharField(source="get_mode_reglement_display")
    total = serializers.SerializerMethodField()
    total_regle = serializers.SerializerMethodField()
    cree_par = serializers.SerializerMethodField()
    prises_en_charge = PecBordereauSerializer(many=True)

    class Meta:
        model = BordereauPec
        fields = [
            "id",
            "numero",
            "magasin",
            "magasin_nom",
            "devise",
            "decimales",
            "organisme",
            "organisme_nom",
            "organisme_type",
            "statut",
            "statut_libelle",
            "envoye_le",
            "regle_le",
            "mode_reglement",
            "mode_reglement_libelle",
            "reference_reglement",
            "observation",
            "total",
            "total_regle",
            "cree_le",
            "cree_par",
            "prises_en_charge",
        ]

    def get_total(self, bordereau) -> str:
        return str(sum((p.montant for p in bordereau.prises_en_charge.all()), Decimal("0.000")))

    def get_total_regle(self, bordereau) -> str | None:
        if bordereau.statut != BordereauPec.Statut.REGLE:
            return None
        regle = (p.montant_regle or Decimal("0") for p in bordereau.prises_en_charge.all())
        return str(sum(regle, Decimal("0.000")))

    def get_cree_par(self, bordereau) -> str:
        return bordereau.cree_par.get_full_name() or bordereau.cree_par.get_username()


class PreparationSerializer(serializers.Serializer):
    magasin = serializers.UUIDField()
    organisme = serializers.UUIDField()
    prises_en_charge = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)
    observation = serializers.CharField(required=False, allow_blank=True, max_length=300)


class ModificationSerializer(serializers.Serializer):
    prises_en_charge = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)
    observation = serializers.CharField(required=False, allow_blank=True, max_length=300)


class EnvoiSerializer(serializers.Serializer):
    le = serializers.DateField()


class LigneReglementBordereauSerializer(serializers.Serializer):
    prise_en_charge = serializers.UUIDField()
    montant_regle = serializers.DecimalField(max_digits=14, decimal_places=3)
    motif_rejet = serializers.CharField(required=False, allow_blank=True, max_length=200)


class ReglementBordereauSerializer(serializers.Serializer):
    le = serializers.DateField()
    mode = serializers.ChoiceField(choices=BordereauPec.Mode.choices)
    reference = serializers.CharField(required=False, allow_blank=True, max_length=60)
    lignes = LigneReglementBordereauSerializer(many=True, required=False)


def _pecs():
    return PriseEnCharge.objects.select_related("vente__client").prefetch_related(
        Prefetch("vente__lignes", queryset=LigneVente.objects.order_by("pk"))
    )


class BordereauPecViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Bordereaux CNAM, assurances et conventions : envoi groupé des prises en charge d'un
    magasin à un organisme, puis saisie de son règlement.

    En préparation, on ajoute ou retire des prises en charge, ou on abandonne le bordereau ;
    envoyé, il attend le règlement ; réglé, il ne change plus.
    """

    serializer_class = BordereauSerializer
    lookup_field = "public_id"
    http_method_names = ["get", "post", "patch", "delete"]
    filterset_fields = ["statut"]
    permissions_requises = {
        "list": "ventes.view_bordereaupec",
        "retrieve": "ventes.view_bordereaupec",
        "a_envoyer": "ventes.add_bordereaupec",
        "create": "ventes.add_bordereaupec",
        "partial_update": "ventes.add_bordereaupec",
        "destroy": "ventes.add_bordereaupec",
        "envoyer": "ventes.change_bordereaupec",
        "regler": "ventes.change_bordereaupec",
    }

    def get_queryset(self):
        return BordereauPec.objects.select_related(
            "magasin__pays", "organisme", "cree_par"
        ).prefetch_related(Prefetch("prises_en_charge", queryset=_pecs().order_by("cree_le")))

    def _magasin(self, identifiant):
        magasin = Magasin.objects.select_related("pays").filter(public_id=identifiant).first()
        if magasin is None:
            raise ValidationError({"magasin": "Magasin inconnu ou hors de votre périmètre."})
        if not self.request.user.has_perm("ventes.add_bordereaupec", magasin):
            raise PermissionDenied("Pas de droit sur les bordereaux de ce magasin.")
        return magasin

    def _organisme(self, identifiant):
        organisme = Organisme.objects.filter(public_id=identifiant).first()
        if organisme is None:
            raise ValidationError({"organisme": "Organisme inconnu."})
        return organisme

    def _prises_en_charge(self, identifiants):
        pecs = list(
            PriseEnCharge.objects.filter(public_id__in=identifiants).select_related("vente")
        )
        if len(pecs) != len(set(identifiants)):
            raise ValidationError(
                {"prises_en_charge": "Prise en charge inconnue ou hors de votre périmètre."}
            )
        return pecs

    def _repondre(self, bordereau, code=status.HTTP_200_OK):
        return Response(BordereauSerializer(self.get_queryset().get(pk=bordereau.pk)).data, code)

    def _bordereau(self, permission):
        bordereau = self.get_object()
        if not self.request.user.has_perm(permission, bordereau):
            raise PermissionDenied("Pas de droit sur les bordereaux de ce magasin.")
        return bordereau

    @extend_schema(
        parameters=[
            OpenApiParameter("magasin", OpenApiTypes.UUID, required=True),
            OpenApiParameter("organisme", OpenApiTypes.UUID, required=True),
        ],
        responses=PecBordereauSerializer(many=True),
    )
    @action(detail=False, methods=["get"], url_path="a-envoyer")
    def a_envoyer(self, request):
        """Prises en charge du magasin pour cet organisme qui ne sont dans aucun bordereau."""
        for champ in ("magasin", "organisme"):
            try:
                uuid.UUID(request.query_params.get(champ, ""))
            except ValueError:
                raise ValidationError({champ: "Identifiant invalide."}) from None
        magasin = self._magasin(request.query_params["magasin"])
        organisme = self._organisme(request.query_params["organisme"])
        pecs = _pecs().filter(
            pk__in=bordereaux.prises_en_charge_a_envoyer(magasin, organisme).values("pk")
        )
        return Response(PecBordereauSerializer(pecs.order_by("cree_le"), many=True).data)

    @extend_schema(request=PreparationSerializer, responses={201: BordereauSerializer})
    def create(self, request):
        saisie = PreparationSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        d = saisie.validated_data
        try:
            bordereau = bordereaux.preparer(
                magasin=self._magasin(d["magasin"]),
                organisme=self._organisme(d["organisme"]),
                prises_en_charge=self._prises_en_charge(d["prises_en_charge"]),
                observation=d.get("observation", ""),
                utilisateur=request.user,
            )
        except bordereaux.BordereauImpossible as erreur:
            return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        return self._repondre(bordereau, status.HTTP_201_CREATED)

    @extend_schema(request=ModificationSerializer, responses=BordereauSerializer)
    def partial_update(self, request, public_id=None):
        """Change les prises en charge d'un bordereau encore en préparation."""
        bordereau = self._bordereau("ventes.add_bordereaupec")
        saisie = ModificationSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        d = saisie.validated_data
        try:
            bordereaux.modifier(
                bordereau,
                prises_en_charge=self._prises_en_charge(d["prises_en_charge"]),
                observation=d.get("observation"),
            )
        except bordereaux.BordereauImpossible as erreur:
            return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        return self._repondre(bordereau)

    def destroy(self, request, public_id=None):
        """Abandonne un bordereau en préparation."""
        try:
            bordereaux.supprimer(self._bordereau("ventes.add_bordereaupec"))
        except bordereaux.BordereauImpossible as erreur:
            return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=EnvoiSerializer, responses=BordereauSerializer)
    @action(detail=True, methods=["post"])
    def envoyer(self, request, public_id=None):
        bordereau = self._bordereau("ventes.change_bordereaupec")
        saisie = EnvoiSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        try:
            bordereaux.envoyer(bordereau, le=saisie.validated_data["le"])
        except bordereaux.BordereauImpossible as erreur:
            return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        return self._repondre(bordereau)

    @extend_schema(request=ReglementBordereauSerializer, responses=BordereauSerializer)
    @action(detail=True, methods=["post"])
    def regler(self, request, public_id=None):
        """Saisit le règlement de l'organisme ; les lignes absentes sont réglées en entier."""
        bordereau = self._bordereau("ventes.change_bordereaupec")
        saisie = ReglementBordereauSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        d = saisie.validated_data
        pecs = {p.public_id: p.pk for p in bordereau.prises_en_charge.all()}
        lignes = {}
        for ligne in d.get("lignes", []):
            if ligne["prise_en_charge"] not in pecs:
                raise ValidationError({"lignes": "Une ligne n'est pas dans ce bordereau."})
            lignes[pecs[ligne["prise_en_charge"]]] = (
                ligne["montant_regle"],
                ligne.get("motif_rejet", ""),
            )
        try:
            bordereaux.regler(
                bordereau,
                le=d["le"],
                mode=d["mode"],
                reference=d.get("reference", ""),
                lignes=lignes,
            )
        except bordereaux.BordereauImpossible as erreur:
            return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        return self._repondre(bordereau)
