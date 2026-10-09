from drf_spectacular.utils import extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.crm.models import Organisme

from ..models import PriseEnCharge, Vente
from ..services import PriseEnChargeImpossible, ajouter_prise_en_charge


class PriseEnChargeSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    vente = serializers.CharField(source="vente.public_id", read_only=True)
    vente_numero = serializers.CharField(source="vente.numero", read_only=True)
    magasin = serializers.CharField(source="vente.magasin.code", read_only=True)
    devise = serializers.CharField(source="vente.devise", read_only=True)
    client = serializers.SerializerMethodField()
    organisme = serializers.CharField(source="organisme.public_id", read_only=True)
    organisme_nom = serializers.CharField(source="organisme.nom", read_only=True)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    bordereau = serializers.SerializerMethodField()

    class Meta:
        model = PriseEnCharge
        fields = [
            "id",
            "vente",
            "vente_numero",
            "magasin",
            "devise",
            "client",
            "organisme",
            "organisme_nom",
            "montant",
            "numero_dossier",
            "statut",
            "statut_libelle",
            "bordereau",
            "montant_regle",
            "motif_rejet",
            "cree_le",
        ]
        read_only_fields = ["montant", "numero_dossier", "montant_regle", "motif_rejet"]

    def get_bordereau(self, pec) -> str | None:
        return pec.bordereau.numero if pec.bordereau else None

    def get_client(self, pec) -> str | None:
        client = pec.vente.client
        return str(client) if client else None


class PriseEnChargeSaisieSerializer(serializers.Serializer):
    vente = serializers.UUIDField()
    organisme = serializers.UUIDField()
    montant = serializers.DecimalField(max_digits=14, decimal_places=3)
    numero_dossier = serializers.CharField(required=False, allow_blank=True, max_length=60)


class StatutPriseEnChargeSerializer(serializers.Serializer):
    statut = serializers.ChoiceField(choices=PriseEnCharge.Statut.choices)


class PriseEnChargeViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Part des commandes prise en charge par la CNAM, une assurance ou une mutuelle.

    On la saisit sur une commande en cours ; son statut suit le dossier auprès de l'organisme
    (demandée, accordée, réglée, refusée). Refusée, elle redevient à la charge du client.
    """

    serializer_class = PriseEnChargeSerializer
    lookup_field = "public_id"
    filterset_fields = ["statut"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        # Les ventes visibles portent déjà le périmètre de magasins de l'utilisateur.
        return PriseEnCharge.objects.filter(vente__in=Vente.objects.all()).select_related(
            "vente__magasin", "vente__client", "organisme", "bordereau"
        )

    @extend_schema(request=PriseEnChargeSaisieSerializer, responses={201: PriseEnChargeSerializer})
    def create(self, request):
        saisie = PriseEnChargeSaisieSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        donnees = saisie.validated_data
        vente = Vente.objects.filter(public_id=donnees["vente"]).first()
        if vente is None:
            raise ValidationError({"vente": "Vente inconnue ou hors de votre périmètre."})
        if not request.user.has_perm("ventes.add_priseencharge", vente):
            raise PermissionDenied("Pas de droit de saisie de prise en charge dans ce magasin.")
        organisme = Organisme.objects.filter(public_id=donnees["organisme"]).first()
        if organisme is None:
            raise ValidationError({"organisme": "Organisme inconnu."})
        try:
            pec = ajouter_prise_en_charge(
                vente=vente,
                organisme=organisme,
                montant=donnees["montant"],
                numero_dossier=donnees.get("numero_dossier", ""),
                utilisateur=request.user,
            )
        except PriseEnChargeImpossible as erreur:
            return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        pec = self.get_queryset().get(pk=pec.pk)
        return Response(PriseEnChargeSerializer(pec).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=StatutPriseEnChargeSerializer, responses={200: PriseEnChargeSerializer})
    def partial_update(self, request, public_id=None):
        """Change seulement le statut du dossier auprès de l'organisme."""
        pec = self.get_object()
        saisie = StatutPriseEnChargeSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        statut = saisie.validated_data["statut"]
        if pec.bordereau is not None:
            return Response(
                {
                    "detail": f"Cette prise en charge est dans le bordereau {pec.bordereau} : "
                    "son règlement se saisit sur le bordereau."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        refusee = PriseEnCharge.Statut.REFUSEE
        if pec.statut == refusee and statut != refusee and pec.montant > pec.vente.reste_a_payer:
            # Le client a déjà réglé cette part entre-temps : on ne la compte pas deux fois.
            return Response(
                {"detail": "Le client a déjà réglé cette part : saisissez-en une autre."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        pec.statut = statut
        pec.save(update_fields=["statut", "modifie_le"])
        return Response(PriseEnChargeSerializer(pec).data)

    def update(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)
