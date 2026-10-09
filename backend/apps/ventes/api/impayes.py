import uuid

from django.db.models import Exists, OuterRef, Prefetch, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.crm.models import Client

from .. import impayes
from ..models import Paiement, PriseEnCharge, Vente
from ..services import VenteInvalide


class PaiementSuiviSerializer(serializers.Serializer):
    """Chèque, traite ou autre règlement d'un client, avec sa visite."""

    id = serializers.IntegerField(source="pk")
    mode = serializers.CharField()
    mode_libelle = serializers.CharField(source="get_mode_display")
    montant = serializers.DecimalField(max_digits=14, decimal_places=3)
    recu_le = serializers.DateTimeField()
    reference = serializers.CharField()
    banque = serializers.CharField()
    echeance = serializers.DateField()
    statut = serializers.CharField()
    statut_libelle = serializers.CharField(source="get_statut_display")
    impaye_le = serializers.DateField()
    motif_impaye = serializers.CharField()
    vente = serializers.UUIDField(source="vente.public_id")
    vente_numero = serializers.CharField(source="vente.numero")
    vente_reste = serializers.DecimalField(
        source="vente.reste_a_payer", max_digits=14, decimal_places=3
    )
    devise = serializers.CharField(source="vente.devise")
    magasin = serializers.CharField(source="vente.magasin.nom")
    client = serializers.SerializerMethodField()
    client_id = serializers.SerializerMethodField()
    client_telephone = serializers.SerializerMethodField()

    def get_client(self, paiement) -> str | None:
        return str(paiement.vente.client) if paiement.vente.client else None

    def get_client_id(self, paiement) -> str | None:
        return str(paiement.vente.client.public_id) if paiement.vente.client else None

    def get_client_telephone(self, paiement) -> str:
        return paiement.vente.client.telephone if paiement.vente.client else ""


class VenteDueSerializer(serializers.Serializer):
    """Visite remise au client qui n'est pas soldée : vente à crédit ou chèque impayé."""

    id = serializers.UUIDField(source="public_id")
    numero = serializers.CharField()
    cree_le = serializers.DateTimeField()
    livree_le = serializers.DateTimeField()
    magasin = serializers.CharField(source="magasin.nom")
    devise = serializers.CharField()
    total_ttc = serializers.DecimalField(max_digits=14, decimal_places=3)
    reste_a_payer = serializers.DecimalField(max_digits=14, decimal_places=3)
    a_credit = serializers.SerializerMethodField()
    credit_echeance = serializers.DateField()
    impayes = serializers.SerializerMethodField()
    client = serializers.SerializerMethodField()
    client_id = serializers.SerializerMethodField()
    client_telephone = serializers.SerializerMethodField()
    en_retard = serializers.SerializerMethodField()

    def get_a_credit(self, vente) -> bool:
        return vente.credit_accorde_par_id is not None

    def get_impayes(self, vente) -> int:
        return sum(1 for p in vente.paiements.all() if p.statut == Paiement.Statut.IMPAYE)

    def get_client(self, vente) -> str | None:
        return str(vente.client) if vente.client else None

    def get_client_id(self, vente) -> str | None:
        return str(vente.client.public_id) if vente.client else None

    def get_client_telephone(self, vente) -> str:
        return vente.client.telephone if vente.client else ""

    def get_en_retard(self, vente) -> bool:
        return bool(vente.credit_echeance and vente.credit_echeance < timezone.localdate())


class ClientListeNoireSerializer(serializers.Serializer):
    id = serializers.UUIDField(source="public_id")
    numero = serializers.IntegerField()
    nom = serializers.CharField(source="__str__")
    telephone = serializers.CharField()
    motif_liste_noire = serializers.CharField()
    liste_noire_le = serializers.DateField()


class ImpayeSerializer(serializers.Serializer):
    le = serializers.DateField()
    motif = serializers.CharField(max_length=200)
    liste_noire = serializers.BooleanField(default=True)


class ChangementSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=Paiement.Mode.choices)
    reference = serializers.CharField(required=False, allow_blank=True, max_length=60)
    banque = serializers.CharField(required=False, allow_blank=True, max_length=100)
    echeance = serializers.DateField(required=False, allow_null=True)


class MiseEnListeNoireSerializer(serializers.Serializer):
    client = serializers.UUIDField()
    motif = serializers.CharField(max_length=200)


def _uuid(valeur, champ):
    try:
        return uuid.UUID(str(valeur))
    except ValueError:
        raise ValidationError({champ: "Identifiant invalide."}) from None


class CreditClientViewSet(viewsets.GenericViewSet):
    """Crédit client et impayés : ventes non soldées, chèques et traites, liste noire."""

    queryset = Paiement.objects.none()
    serializer_class = PaiementSuiviSerializer
    pagination_class = None
    permissions_requises = {
        "ventes_dues": "ventes.view_vente",
        "paiements": "ventes.view_vente",
        "impaye": "ventes.gerer_impayes",
        "changer": "ventes.gerer_impayes",
        "liste_noire": "ventes.gerer_impayes",
        "retirer_liste_noire": "ventes.gerer_impayes",
    }

    def _ventes(self):
        ventes = Vente.objects.all()
        magasin = self.request.query_params.get("magasin")
        if magasin:
            ventes = ventes.filter(magasin__public_id=_uuid(magasin, "magasin"))
        client = self.request.query_params.get("client")
        if client:
            ventes = ventes.filter(client__public_id=_uuid(client, "client"))
        return ventes

    @extend_schema(
        parameters=[
            OpenApiParameter("magasin", OpenApiTypes.UUID),
            OpenApiParameter("client", OpenApiTypes.UUID),
        ],
        responses=VenteDueSerializer(many=True),
    )
    @action(detail=False, url_path="ventes-dues")
    def ventes_dues(self, request):
        """Visites remises au client et pas soldées : ventes à crédit, chèques impayés."""
        impaye = Paiement.objects.filter(vente=OuterRef("pk"), statut=Paiement.Statut.IMPAYE)
        ventes = (
            self._ventes()
            .filter(statut=Vente.Statut.LIVREE)
            .filter(Q(credit_accorde_par__isnull=False) | Exists(impaye))
            .select_related("magasin", "client")
            .prefetch_related(
                "paiements",
                Prefetch("prises_en_charge", queryset=PriseEnCharge.objects.all()),
            )
            .order_by("credit_echeance", "cree_le")
        )
        dues = [v for v in ventes if v.reste_a_payer > 0]
        return Response(VenteDueSerializer(dues, many=True).data)

    @extend_schema(
        parameters=[
            OpenApiParameter("magasin", OpenApiTypes.UUID),
            OpenApiParameter("client", OpenApiTypes.UUID),
            OpenApiParameter(
                "vue",
                OpenApiTypes.STR,
                enum=["portefeuille", "impayes", "cheques"],
                description=(
                    "portefeuille : chèques et traites à remettre à la banque, par échéance ; "
                    "impayes : revenus impayés ; cheques : tous les chèques et traites."
                ),
            ),
        ],
        responses=PaiementSuiviSerializer(many=True),
    )
    @action(detail=False)
    def paiements(self, request):
        """Chèques et traites des clients : échéancier, impayés, changements."""
        paiements = (
            Paiement.objects.filter(vente__in=self._ventes(), mode__in=Paiement.A_ECHEANCE)
            .select_related("vente__magasin", "vente__client")
            .prefetch_related("vente__paiements", "vente__prises_en_charge")
        )
        vue = request.query_params.get("vue", "cheques")
        if vue == "portefeuille":
            paiements = paiements.filter(
                statut=Paiement.Statut.ENCAISSE, echeance__gte=timezone.localdate()
            ).order_by("echeance", "pk")
        elif vue == "impayes":
            paiements = paiements.filter(statut=Paiement.Statut.IMPAYE).order_by("-impaye_le")
        else:
            paiements = paiements.order_by("-recu_le")[:500]
        return Response(PaiementSuiviSerializer(paiements, many=True).data)

    def _paiement(self, pk):
        paiement = get_object_or_404(
            Paiement.objects.select_related("vente__magasin", "vente__client"),
            pk=pk,
            vente__in=Vente.objects.all(),
        )
        if not self.request.user.has_perm("ventes.gerer_impayes", paiement.vente.magasin):
            raise PermissionDenied("Pas de droit sur les impayés de ce magasin.")
        return paiement

    def _reponse(self, paiement):
        paiement = (
            Paiement.objects.select_related("vente__magasin", "vente__client")
            .prefetch_related("vente__paiements", "vente__prises_en_charge")
            .get(pk=paiement.pk)
        )
        return Response(PaiementSuiviSerializer(paiement).data)

    @extend_schema(request=ImpayeSerializer, responses=PaiementSuiviSerializer)
    @action(detail=False, methods=["post"], url_path=r"paiements/(?P<pk>\d+)/impaye")
    def impaye(self, request, pk=None):
        """Chèque ou traite rejeté par la banque : son montant redevient dû."""
        paiement = self._paiement(pk)
        saisie = ImpayeSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        try:
            paiement = impayes.declarer_impaye(paiement, **saisie.validated_data)
        except VenteInvalide as erreur:
            return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        return self._reponse(paiement)

    @extend_schema(request=ChangementSerializer, responses=PaiementSuiviSerializer)
    @action(detail=False, methods=["post"], url_path=r"paiements/(?P<pk>\d+)/changer")
    def changer(self, request, pk=None):
        """Changement de chèque : le client paie autrement le même montant."""
        paiement = self._paiement(pk)
        saisie = ChangementSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        try:
            nouveau = impayes.changer_cheque(
                paiement, nouveau=saisie.validated_data, utilisateur=request.user
            )
        except VenteInvalide as erreur:
            return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        return self._reponse(nouveau)

    @extend_schema(methods=["get"], responses=ClientListeNoireSerializer(many=True), request=None)
    @extend_schema(
        methods=["post"],
        request=MiseEnListeNoireSerializer,
        responses=ClientListeNoireSerializer,
    )
    @action(detail=False, methods=["get", "post"], url_path="liste-noire")
    def liste_noire(self, request):
        """Clients en liste noire ; POST en ajoute un."""
        if request.method == "GET":
            clients = Client.objects.filter(liste_noire=True).order_by("-liste_noire_le", "nom")
            return Response(ClientListeNoireSerializer(clients, many=True).data)
        saisie = MiseEnListeNoireSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        client = get_object_or_404(Client, public_id=saisie.validated_data["client"])
        impayes.mettre_en_liste_noire(client, saisie.validated_data["motif"])
        return Response(ClientListeNoireSerializer(client).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses={204: None})
    @action(detail=False, methods=["delete"], url_path=r"liste-noire/(?P<client>[0-9a-f-]{36})")
    def retirer_liste_noire(self, request, client=None):
        """Retire un client de la liste noire."""
        impayes.retirer_de_la_liste_noire(get_object_or_404(Client, public_id=client))
        return Response(status=status.HTTP_204_NO_CONTENT)
