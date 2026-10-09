import uuid

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.achats.models import Fournisseur
from apps.crm.models import Client
from apps.reseau.models import Magasin
from apps.stock.models import Article

from ..models import DossierSav, Vente
from ..sav import SavImpossible, changer_etape, ouvrir_dossier


def _nom(utilisateur):
    return utilisateur.get_full_name() or utilisateur.get_username()


class EvenementSavSerializer(serializers.Serializer):
    etape = serializers.CharField()
    etape_libelle = serializers.CharField(source="get_etape_display")
    commentaire = serializers.CharField()
    le = serializers.DateTimeField()
    par = serializers.SerializerMethodField()

    def get_par(self, evenement) -> str:
        return _nom(evenement.par)


class DossierSavSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    magasin = serializers.CharField(source="magasin.public_id")
    magasin_nom = serializers.CharField(source="magasin.nom")
    client = serializers.CharField(source="client.public_id")
    client_nom = serializers.CharField(source="client.__str__")
    client_telephone = serializers.CharField(source="client.telephone")
    vente = serializers.SerializerMethodField()
    vente_numero = serializers.SerializerMethodField()
    article = serializers.SerializerMethodField()
    fournisseur = serializers.SerializerMethodField()
    fournisseur_nom = serializers.SerializerMethodField()
    motif_libelle = serializers.CharField(source="get_motif_display")
    etape_libelle = serializers.CharField(source="get_etape_display")
    est_ouvert = serializers.BooleanField()
    en_retard = serializers.SerializerMethodField()
    cree_par = serializers.SerializerMethodField()
    evenements = EvenementSavSerializer(many=True)

    class Meta:
        model = DossierSav
        fields = [
            "id",
            "numero",
            "magasin",
            "magasin_nom",
            "client",
            "client_nom",
            "client_telephone",
            "vente",
            "vente_numero",
            "article",
            "designation",
            "motif",
            "motif_libelle",
            "description",
            "sous_garantie",
            "fournisseur",
            "fournisseur_nom",
            "etape",
            "etape_libelle",
            "est_ouvert",
            "en_retard",
            "retour_prevu_le",
            "solution",
            "cree_le",
            "cree_par",
            "evenements",
        ]

    def get_vente(self, dossier) -> str | None:
        return str(dossier.vente.public_id) if dossier.vente else None

    def get_vente_numero(self, dossier) -> str | None:
        return dossier.vente.numero if dossier.vente else None

    def get_article(self, dossier) -> str | None:
        return str(dossier.article.public_id) if dossier.article else None

    def get_fournisseur(self, dossier) -> str | None:
        return str(dossier.fournisseur.public_id) if dossier.fournisseur else None

    def get_fournisseur_nom(self, dossier) -> str | None:
        return dossier.fournisseur.nom if dossier.fournisseur else None

    def get_en_retard(self, dossier) -> bool:
        return dossier.en_retard(timezone.localdate())

    def get_cree_par(self, dossier) -> str:
        return _nom(dossier.cree_par)


class OuvertureSavSerializer(serializers.Serializer):
    magasin = serializers.UUIDField()
    client = serializers.UUIDField()
    vente = serializers.UUIDField(required=False, allow_null=True)
    article = serializers.UUIDField(required=False, allow_null=True)
    designation = serializers.CharField(max_length=200)
    motif = serializers.ChoiceField(choices=DossierSav.Motif.choices)
    description = serializers.CharField(required=False, allow_blank=True)
    sous_garantie = serializers.BooleanField(required=False, default=False)
    retour_prevu_le = serializers.DateField(required=False, allow_null=True)


class EtapeSavSerializer(serializers.Serializer):
    etape = serializers.ChoiceField(choices=DossierSav.Etape.choices)
    commentaire = serializers.CharField(required=False, allow_blank=True, max_length=300)
    fournisseur = serializers.UUIDField(required=False, allow_null=True)
    retour_prevu_le = serializers.DateField(required=False, allow_null=True)
    solution = serializers.CharField(required=False, allow_blank=True, max_length=300)


class DossierSavViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """Dossiers SAV : ce que les clients rapportent après la vente, et leur suivi.

    Filtres : ``etape`` (``ouverts`` pour tous les dossiers en cours), ``retard=1`` pour ceux
    dont le retour prévu est dépassé, ``client``, ``q`` (n°, client, désignation).
    """

    serializer_class = DossierSavSerializer
    lookup_field = "public_id"
    permissions_requises = {
        "list": "ventes.view_dossiersav",
        "retrieve": "ventes.view_dossiersav",
        "create": "ventes.add_dossiersav",
        "etape": "ventes.change_dossiersav",
    }

    def get_queryset(self):
        dossiers = DossierSav.objects.select_related(
            "magasin", "client", "vente", "article", "fournisseur", "cree_par"
        ).prefetch_related("evenements__par")
        if self.action != "list":
            return dossiers
        parametres = self.request.query_params
        etape = parametres.get("etape", "")
        if etape == "ouverts":
            dossiers = dossiers.filter(etape__in=DossierSav.OUVERTES)
        elif etape:
            dossiers = dossiers.filter(etape=etape)
        if parametres.get("retard") == "1":
            dossiers = dossiers.filter(
                etape__in=DossierSav.EN_ATTENTE, retour_prevu_le__lt=timezone.localdate()
            )
        if parametres.get("client"):
            dossiers = dossiers.filter(client__public_id=self._uuid(parametres["client"], "client"))
        texte = parametres.get("q", "").strip()
        if texte:
            dossiers = dossiers.filter(
                Q(numero__icontains=texte)
                | Q(designation__icontains=texte)
                | Q(client__nom__icontains=texte)
                | Q(client__prenom__icontains=texte)
                | Q(client__telephone__icontains=texte)
            )
        return dossiers

    @staticmethod
    def _uuid(valeur, champ):
        try:
            return uuid.UUID(str(valeur))
        except ValueError:
            raise ValidationError({champ: "Identifiant invalide."}) from None

    @extend_schema(
        parameters=[
            OpenApiParameter("etape", OpenApiTypes.STR),
            OpenApiParameter("retard", OpenApiTypes.STR),
            OpenApiParameter("client", OpenApiTypes.UUID),
            OpenApiParameter("q", OpenApiTypes.STR),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(request=OuvertureSavSerializer, responses={201: DossierSavSerializer})
    def create(self, request):
        saisie = OuvertureSavSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        d = saisie.validated_data
        magasin = Magasin.objects.select_related("pays").filter(public_id=d["magasin"]).first()
        if magasin is None:
            raise ValidationError({"magasin": "Magasin inconnu ou hors de votre périmètre."})
        if not request.user.has_perm("ventes.add_dossiersav", magasin):
            raise PermissionDenied("Pas de droit d'ouvrir un dossier SAV dans ce magasin.")
        client = Client.objects.filter(public_id=d["client"]).first()
        if client is None:
            raise ValidationError({"client": "Client inconnu."})
        vente = None
        if d.get("vente"):
            vente = Vente.objects.filter(public_id=d["vente"]).first()
            if vente is None:
                raise ValidationError({"vente": "Visite inconnue ou hors de votre périmètre."})
        article = None
        if d.get("article"):
            article = Article.objects.filter(public_id=d["article"]).first()
            if article is None:
                raise ValidationError({"article": "Article inconnu."})
        try:
            dossier = ouvrir_dossier(
                magasin=magasin,
                client=client,
                vente=vente,
                article=article,
                designation=d["designation"],
                motif=d["motif"],
                description=d.get("description", ""),
                sous_garantie=d["sous_garantie"],
                retour_prevu_le=d.get("retour_prevu_le"),
                utilisateur=request.user,
            )
        except SavImpossible as erreur:
            return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            DossierSavSerializer(self.get_queryset().get(pk=dossier.pk)).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(request=EtapeSavSerializer, responses={200: DossierSavSerializer})
    @action(detail=True, methods=["post"])
    def etape(self, request, public_id=None):
        """Passe le dossier à une autre étape ; « rendu » ou « annulé » le clôture."""
        dossier = self.get_object()
        saisie = EtapeSavSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        d = saisie.validated_data
        fournisseur = None
        if d.get("fournisseur"):
            fournisseur = get_object_or_404(Fournisseur, public_id=d["fournisseur"])
        try:
            changer_etape(
                dossier,
                d["etape"],
                utilisateur=request.user,
                commentaire=d.get("commentaire", ""),
                fournisseur=fournisseur,
                retour_prevu_le=d.get("retour_prevu_le"),
                solution=d.get("solution", ""),
            )
        except SavImpossible as erreur:
            return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(DossierSavSerializer(self.get_queryset().get(pk=dossier.pk)).data)
