"""API des transferts de stock (dépôt central vers magasin)."""

import uuid

from django.db.models import Prefetch, Q, Sum
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.reseau.models import Magasin
from core.perimetre import perimetre_actuel

from ..models import Article, LigneTransfert, TransfertStock
from ..transferts import TransfertImpossible, envoyer_transfert, recevoir_transfert


class LigneTransfertSaisieSerializer(serializers.Serializer):
    article = serializers.UUIDField()
    quantite = serializers.IntegerField(min_value=1)


class TransfertSaisieSerializer(serializers.Serializer):
    magasin = serializers.UUIDField(help_text="Magasin de départ (le dépôt central en général).")
    destination = serializers.UUIDField()
    observation = serializers.CharField(required=False, allow_blank=True)
    lignes = LigneTransfertSaisieSerializer(many=True)


class LigneTransfertSerializer(serializers.ModelSerializer):
    article = serializers.UUIDField(source="article.public_id")
    reference = serializers.CharField(source="article.reference")
    code_barres = serializers.CharField(source="article.code_barres")
    libelle = serializers.CharField(source="article.libelle")
    famille = serializers.CharField(source="article.famille")

    class Meta:
        model = LigneTransfert
        fields = ["article", "reference", "code_barres", "libelle", "famille", "quantite"]


def _nom(utilisateur):
    if utilisateur is None:
        return ""
    return utilisateur.get_full_name() or utilisateur.get_username()


class TransfertListeSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    magasin = serializers.CharField(source="magasin.nom", read_only=True)
    magasin_id = serializers.UUIDField(source="magasin.public_id", read_only=True)
    destination = serializers.CharField(source="destination.nom", read_only=True)
    destination_id = serializers.UUIDField(source="destination.public_id", read_only=True)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    total_articles = serializers.IntegerField(read_only=True)
    envoye_par = serializers.SerializerMethodField()
    recu_par = serializers.SerializerMethodField()

    class Meta:
        model = TransfertStock
        fields = [
            "id",
            "numero",
            "magasin",
            "magasin_id",
            "destination",
            "destination_id",
            "statut",
            "statut_libelle",
            "total_articles",
            "observation",
            "envoye_par",
            "cree_le",
            "recu_par",
            "recu_le",
        ]

    def get_envoye_par(self, transfert) -> str:
        return _nom(transfert.envoye_par)

    def get_recu_par(self, transfert) -> str:
        return _nom(transfert.recu_par)


class TransfertSerializer(TransfertListeSerializer):
    lignes = LigneTransfertSerializer(many=True, read_only=True)

    class Meta(TransfertListeSerializer.Meta):
        fields = TransfertListeSerializer.Meta.fields + ["lignes"]


class TransfertViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Transferts envoyés ou reçus par les magasins du périmètre ; envoi et réception."""

    lookup_field = "public_id"
    permissions_requises = {
        "list": "stock.view_transfertstock",
        "retrieve": "stock.view_transfertstock",
        "create": "stock.add_transfertstock",
        "recevoir": "stock.change_transfertstock",
    }
    FILTRES = {
        "numero": "numero__icontains",
        "statut": "statut",
        "du": "cree_le__date__gte",
        "au": "cree_le__date__lte",
    }

    def get_serializer_class(self):
        return TransfertListeSerializer if self.action == "list" else TransfertSerializer

    def get_queryset(self):
        transferts = (
            TransfertStock.tous.select_related("magasin", "destination", "envoye_par", "recu_par")
            .prefetch_related(
                Prefetch("lignes", queryset=LigneTransfert.objects.select_related("article"))
            )
            .annotate(total_articles=Sum("lignes__quantite"))
            .order_by("-cree_le")
        )
        ids = perimetre_actuel()
        if ids is not None:
            transferts = transferts.filter(Q(magasin_id__in=ids) | Q(destination_id__in=ids))
        if self.action == "list":
            params = self.request.query_params
            magasin = params.get("magasin", "").strip()
            if magasin:
                transferts = transferts.filter(
                    Q(magasin__public_id=magasin) | Q(destination__public_id=magasin)
                )
            for cle, critere in self.FILTRES.items():
                valeur = params.get(cle, "").strip()
                if valeur:
                    transferts = transferts.filter(**{critere: valeur})
        return transferts

    def _transfert(self, public_id):
        """Le transfert concerne deux magasins : le droit se vérifie sur l'un ou l'autre (et non
        sur le seul magasin de départ, comme le ferait ``get_object``)."""
        transfert = self.get_queryset().filter(public_id=public_id).first()
        if transfert is None:
            raise NotFound("Transfert introuvable.")
        return transfert

    def retrieve(self, request, public_id=None):
        transfert = self._transfert(public_id)
        if not any(
            request.user.has_perm("stock.view_transfertstock", m)
            for m in (transfert.magasin, transfert.destination)
        ):
            raise PermissionDenied("Ce transfert ne concerne pas vos magasins.")
        return Response(TransfertSerializer(transfert).data)

    def _magasin(self, identifiant, champ):
        try:
            uuid.UUID(str(identifiant))
        except ValueError:
            raise ValidationError({champ: "Identifiant invalide."}) from None
        magasin = Magasin.tous.select_related("pays").filter(public_id=identifiant).first()
        if magasin is None:
            raise ValidationError({champ: "Magasin inconnu."})
        return magasin

    @extend_schema(request=TransfertSaisieSerializer, responses={201: TransfertSerializer})
    def create(self, request):
        saisie = TransfertSaisieSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        donnees = saisie.validated_data
        magasin = self._magasin(donnees["magasin"], "magasin")
        if not request.user.has_perm("stock.add_transfertstock", magasin):
            raise PermissionDenied("Pas de droit d'envoyer un transfert depuis ce magasin.")
        destination = self._magasin(donnees["destination"], "destination")
        articles = {
            a.public_id: a
            for a in Article.objects.filter(public_id__in=[x["article"] for x in donnees["lignes"]])
        }
        lignes = []
        for ligne in donnees["lignes"]:
            article = articles.get(ligne["article"])
            if article is None:
                raise ValidationError({"lignes": "Article inconnu."})
            lignes.append({"article": article, "quantite": ligne["quantite"]})
        try:
            transfert = envoyer_transfert(
                magasin=magasin,
                destination=destination,
                lignes=lignes,
                auteur=request.user,
                observation=donnees.get("observation", ""),
            )
        except TransfertImpossible as erreur:
            return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        transfert = self.get_queryset().get(pk=transfert.pk)
        return Response(TransfertSerializer(transfert).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses={200: TransfertSerializer})
    @action(detail=True, methods=["post"])
    def recevoir(self, request, public_id=None):
        """Le magasin destinataire réceptionne le transfert : les articles entrent en stock."""
        transfert = self._transfert(public_id)
        if not request.user.has_perm("stock.change_transfertstock", transfert.destination):
            raise PermissionDenied("Seul le magasin destinataire réceptionne ce transfert.")
        try:
            recevoir_transfert(transfert, auteur=request.user)
        except TransfertImpossible as erreur:
            return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(TransfertSerializer(self.get_queryset().get(pk=transfert.pk)).data)
