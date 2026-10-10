"""API des bons de sortie (et sorties casse), des demandes de transfert, du réassort et du
stock à une date."""

import uuid
from datetime import timedelta

from django.db.models import Prefetch, Q
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.achats.depot import depot_de
from apps.reseau.models import Depot, Magasin
from core.perimetre import perimetre_actuel

from .. import sorties
from ..models import (
    Article,
    BonSortie,
    DemandeTransfert,
    LigneDemandeTransfert,
    LigneSortie,
)
from ..transferts import TransfertImpossible


def _nom(utilisateur):
    if utilisateur is None:
        return ""
    return utilisateur.get_full_name() or utilisateur.get_username()


def _magasin(identifiant, champ):
    try:
        uuid.UUID(str(identifiant))
    except ValueError:
        raise ValidationError({champ: "Identifiant invalide."}) from None
    magasin = Magasin.tous.select_related("pays").filter(public_id=identifiant).first()
    if magasin is None:
        raise ValidationError({champ: "Magasin inconnu."})
    return magasin


def _depot(magasin, identifiant, defaut=None):
    """Dépôt du magasin choisi par son identifiant ; sans identifiant, ``defaut`` (par défaut le
    dépôt de vente du magasin)."""
    if not identifiant:
        return defaut or magasin.depot_de_vente
    try:
        uuid.UUID(str(identifiant))
    except ValueError:
        raise ValidationError({"depot": "Identifiant invalide."}) from None
    depot = Depot.objects.filter(public_id=identifiant, magasin=magasin).first()
    if depot is None:
        raise ValidationError({"depot": f"Ce dépôt n'est pas un dépôt de {magasin.nom}."})
    return depot


def _articles(lignes):
    """Saisie [{"article": uuid, "quantite"}] → [{"article": Article, "quantite"}]."""
    articles = {
        a.public_id: a for a in Article.objects.filter(public_id__in=[x["article"] for x in lignes])
    }
    resultat = []
    for ligne in lignes:
        article = articles.get(ligne["article"])
        if article is None:
            raise ValidationError({"lignes": "Article inconnu."})
        resultat.append({"article": article, "quantite": ligne["quantite"]})
    return resultat


def _date(request, nom, defaut):
    valeur = request.query_params.get(nom)
    if not valeur:
        return defaut
    try:
        return serializers.DateField().to_internal_value(valeur)
    except serializers.ValidationError:
        raise ValidationError({nom: "Date invalide (AAAA-MM-JJ)."}) from None


class LigneArticleSaisieSerializer(serializers.Serializer):
    article = serializers.UUIDField()
    quantite = serializers.IntegerField(min_value=1)


class LigneArticleSerializer(serializers.Serializer):
    article = serializers.UUIDField(source="article.public_id")
    reference = serializers.CharField(source="article.reference")
    libelle = serializers.CharField(source="article.libelle")
    famille = serializers.CharField(source="article.famille")
    quantite = serializers.IntegerField()


# Bons de sortie


class BonSortieSaisieSerializer(serializers.Serializer):
    magasin = serializers.UUIDField()
    depot = serializers.UUIDField(
        required=False, allow_null=True, help_text="Par défaut : le dépôt de vente du magasin."
    )
    type = serializers.ChoiceField(choices=BonSortie.Type.choices)
    motif = serializers.CharField(max_length=200)
    observation = serializers.CharField(required=False, allow_blank=True)
    lignes = LigneArticleSaisieSerializer(many=True)


class BonSortieSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    magasin = serializers.CharField(source="magasin.nom", read_only=True)
    depot = serializers.CharField(source="depot.nom", read_only=True)
    type_libelle = serializers.CharField(source="get_type_display", read_only=True)
    cree_par = serializers.SerializerMethodField()
    total_articles = serializers.SerializerMethodField()
    lignes = LigneArticleSerializer(many=True, read_only=True)

    class Meta:
        model = BonSortie
        fields = [
            "id",
            "numero",
            "magasin",
            "depot",
            "type",
            "type_libelle",
            "motif",
            "observation",
            "cree_le",
            "cree_par",
            "total_articles",
            "lignes",
        ]

    def get_cree_par(self, bon) -> str:
        return _nom(bon.cree_par)

    def get_total_articles(self, bon) -> int:
        return sum(ligne.quantite for ligne in bon.lignes.all())


class BonSortieViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Bons de sortie et sorties casse : les articles sortent du stock sans être vendus."""

    serializer_class = BonSortieSerializer
    lookup_field = "public_id"
    permissions_requises = {
        "list": "stock.view_bonsortie",
        "retrieve": "stock.view_bonsortie",
        "create": "stock.add_bonsortie",
    }

    def get_queryset(self):
        bons = BonSortie.objects.select_related("magasin", "depot", "cree_par").prefetch_related(
            Prefetch("lignes", queryset=LigneSortie.objects.select_related("article"))
        )
        params = self.request.query_params
        if params.get("type"):
            bons = bons.filter(type=params["type"])
        if params.get("magasin"):
            bons = bons.filter(magasin=_magasin(params["magasin"], "magasin"))
        return bons

    @extend_schema(
        parameters=[
            OpenApiParameter("type", OpenApiTypes.STR, enum=BonSortie.Type.values),
            OpenApiParameter("magasin", OpenApiTypes.UUID),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(request=BonSortieSaisieSerializer, responses={201: BonSortieSerializer})
    def create(self, request):
        saisie = BonSortieSaisieSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        donnees = saisie.validated_data
        magasin = _magasin(donnees["magasin"], "magasin")
        if not request.user.has_perm("stock.add_bonsortie", magasin):
            raise PermissionDenied("Pas de droit de sortir du stock dans ce magasin.")
        try:
            bon = sorties.sortir(
                magasin=magasin,
                type=donnees["type"],
                motif=donnees["motif"],
                lignes=_articles(donnees["lignes"]),
                auteur=request.user,
                observation=donnees.get("observation", ""),
                depot=_depot(magasin, donnees.get("depot")),
            )
        except sorties.SortieImpossible as erreur:
            return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        bon = self.get_queryset().get(pk=bon.pk)
        return Response(BonSortieSerializer(bon).data, status=status.HTTP_201_CREATED)


# Demandes de transfert et réassort


class LigneDemandeSerializer(LigneArticleSerializer):
    quantite_servie = serializers.IntegerField()


class DemandeTransfertSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    magasin = serializers.CharField(source="magasin.nom", read_only=True)
    magasin_id = serializers.UUIDField(source="magasin.public_id", read_only=True)
    aupres_de = serializers.CharField(source="aupres_de.nom", read_only=True)
    aupres_de_id = serializers.UUIDField(source="aupres_de.public_id", read_only=True)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    demandee_par = serializers.SerializerMethodField()
    traitee_par = serializers.SerializerMethodField()
    transfert = serializers.SerializerMethodField()
    lignes = LigneDemandeSerializer(many=True, read_only=True)

    class Meta:
        model = DemandeTransfert
        fields = [
            "id",
            "numero",
            "magasin",
            "magasin_id",
            "aupres_de",
            "aupres_de_id",
            "statut",
            "statut_libelle",
            "observation",
            "cree_le",
            "demandee_par",
            "traitee_par",
            "traitee_le",
            "motif_refus",
            "transfert",
            "lignes",
        ]

    def get_demandee_par(self, demande) -> str:
        return _nom(demande.demandee_par)

    def get_traitee_par(self, demande) -> str:
        return _nom(demande.traitee_par)

    def get_transfert(self, demande) -> str | None:
        return demande.transfert.numero if demande.transfert else None


class DemandeTransfertSaisieSerializer(serializers.Serializer):
    magasin = serializers.UUIDField(help_text="Magasin qui demande.")
    aupres_de = serializers.UUIDField(help_text="Magasin sollicité (le dépôt, en général).")
    observation = serializers.CharField(required=False, allow_blank=True)
    lignes = LigneArticleSaisieSerializer(many=True)


class ServirSerializer(serializers.Serializer):
    lignes = LigneArticleSaisieSerializer(
        many=True,
        required=False,
        help_text="Quantités envoyées par article ; absent : tout ce qui est demandé.",
    )


class RefusSerializer(serializers.Serializer):
    motif = serializers.CharField(max_length=200)


class ReassortSerializer(serializers.Serializer):
    article = serializers.UUIDField(source="article.public_id")
    reference = serializers.CharField(source="article.reference")
    libelle = serializers.CharField(source="article.libelle")
    famille = serializers.CharField(source="article.famille")
    vendu = serializers.IntegerField()
    stock = serializers.IntegerField()
    stock_depot = serializers.IntegerField(allow_null=True)
    propose = serializers.IntegerField()


class DemandeTransfertViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Demandes d'articles d'un magasin à un autre (au dépôt : demandes d'alimentation)."""

    serializer_class = DemandeTransfertSerializer
    lookup_field = "public_id"
    permissions_requises = {
        "list": "stock.view_demandetransfert",
        "retrieve": "stock.view_demandetransfert",
        "create": "stock.add_demandetransfert",
        "servir": "stock.change_demandetransfert",
        "refuser": "stock.change_demandetransfert",
        "annuler": "stock.add_demandetransfert",
        "reassort": "stock.add_demandetransfert",
    }

    def get_queryset(self):
        demandes = DemandeTransfert.tous.select_related(
            "magasin", "aupres_de", "demandee_par", "traitee_par", "transfert"
        ).prefetch_related(
            Prefetch("lignes", queryset=LigneDemandeTransfert.objects.select_related("article"))
        )
        ids = perimetre_actuel()
        if ids is not None:
            demandes = demandes.filter(Q(magasin_id__in=ids) | Q(aupres_de_id__in=ids))
        if self.action == "list":
            params = self.request.query_params
            if params.get("statut"):
                demandes = demandes.filter(statut=params["statut"])
            if params.get("sens") == "recues":
                demandes = demandes.exclude(magasin_id__in=ids) if ids is not None else demandes
            elif params.get("sens") == "envoyees" and ids is not None:
                demandes = demandes.filter(magasin_id__in=ids)
        return demandes

    def _demande(self, public_id):
        demande = self.get_queryset().filter(public_id=public_id).first()
        if demande is None:
            raise NotFound("Demande introuvable.")
        return demande

    @extend_schema(
        parameters=[
            OpenApiParameter("statut", OpenApiTypes.STR, enum=DemandeTransfert.Statut.values),
            OpenApiParameter(
                "sens",
                OpenApiTypes.STR,
                enum=["recues", "envoyees"],
                description="recues : à servir par mes magasins ; envoyees : faites par eux.",
            ),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, public_id=None):
        return Response(DemandeTransfertSerializer(self._demande(public_id)).data)

    @extend_schema(
        request=DemandeTransfertSaisieSerializer, responses={201: DemandeTransfertSerializer}
    )
    def create(self, request):
        saisie = DemandeTransfertSaisieSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        donnees = saisie.validated_data
        magasin = _magasin(donnees["magasin"], "magasin")
        if not request.user.has_perm("stock.add_demandetransfert", magasin):
            raise PermissionDenied("Pas de droit de demander pour ce magasin.")
        try:
            demande = sorties.demander(
                magasin=magasin,
                aupres_de=_magasin(donnees["aupres_de"], "aupres_de"),
                lignes=_articles(donnees["lignes"]),
                auteur=request.user,
                observation=donnees.get("observation", ""),
            )
        except TransfertImpossible as erreur:
            return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        demande = self.get_queryset().get(pk=demande.pk)
        return Response(DemandeTransfertSerializer(demande).data, status=status.HTTP_201_CREATED)

    def _traiter(self, demande, permission, magasin, message, fonction):
        if not self.request.user.has_perm(permission, magasin):
            raise PermissionDenied(message)
        try:
            fonction()
        except TransfertImpossible as erreur:
            return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(DemandeTransfertSerializer(self.get_queryset().get(pk=demande.pk)).data)

    @extend_schema(request=ServirSerializer, responses={200: DemandeTransfertSerializer})
    @action(detail=True, methods=["post"])
    def servir(self, request, public_id=None):
        """Le magasin sollicité envoie les articles : un transfert part vers le demandeur."""
        demande = self._demande(public_id)
        saisie = ServirSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        quantites = None
        if "lignes" in saisie.validated_data:
            quantites = {
                ligne["article"].pk: ligne["quantite"]
                for ligne in _articles(saisie.validated_data["lignes"])
            }
        return self._traiter(
            demande,
            "stock.change_demandetransfert",
            demande.aupres_de,
            "Seul le magasin sollicité sert cette demande.",
            lambda: sorties.servir(demande, auteur=request.user, quantites=quantites),
        )

    @extend_schema(request=RefusSerializer, responses={200: DemandeTransfertSerializer})
    @action(detail=True, methods=["post"])
    def refuser(self, request, public_id=None):
        demande = self._demande(public_id)
        saisie = RefusSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        return self._traiter(
            demande,
            "stock.change_demandetransfert",
            demande.aupres_de,
            "Seul le magasin sollicité refuse cette demande.",
            lambda: sorties.refuser(
                demande, auteur=request.user, motif=saisie.validated_data["motif"]
            ),
        )

    @extend_schema(request=None, responses={200: DemandeTransfertSerializer})
    @action(detail=True, methods=["post"])
    def annuler(self, request, public_id=None):
        demande = self._demande(public_id)
        return self._traiter(
            demande,
            "stock.add_demandetransfert",
            demande.magasin,
            "Seul le magasin demandeur retire sa demande.",
            lambda: sorties.annuler(demande, auteur=request.user),
        )

    @extend_schema(
        parameters=[
            OpenApiParameter("magasin", OpenApiTypes.UUID, required=True),
            OpenApiParameter("du", OpenApiTypes.DATE, description="Par défaut : il y a 30 jours."),
            OpenApiParameter("au", OpenApiTypes.DATE, description="Par défaut : aujourd'hui."),
            OpenApiParameter("famille", OpenApiTypes.STR, enum=Article.Famille.values),
            OpenApiParameter(
                "depot",
                OpenApiTypes.UUID,
                description="Magasin qui abrite le dépôt central (par défaut : celui de la "
                "société).",
            ),
        ],
        responses=ReassortSerializer(many=True),
    )
    @action(detail=False, pagination_class=None)
    def reassort(self, request):
        """Réassort : ce qui s'est vendu, le stock du magasin et du dépôt, la quantité à
        redemander."""
        if not request.query_params.get("magasin"):
            raise ValidationError({"magasin": "Choisir le magasin."})
        magasin = _magasin(request.query_params["magasin"], "magasin")
        if not request.user.has_perm("stock.add_demandetransfert", magasin):
            raise PermissionDenied("Pas de droit de demander pour ce magasin.")
        if request.query_params.get("depot"):
            depot = _magasin(request.query_params["depot"], "depot")
        else:
            depot = depot_de(magasin)
            if depot is not None and depot.pk == magasin.pk:
                depot = None
        au = _date(request, "au", timezone.localdate())
        du = _date(request, "du", au - timedelta(days=30))
        lignes = sorties.reassort(
            magasin, du=du, au=au, famille=request.query_params.get("famille", ""), depot=depot
        )
        return Response(ReassortSerializer(lignes, many=True).data)


# Stock à une date


class StockADateSerializer(serializers.Serializer):
    article = serializers.UUIDField(source="article.public_id")
    reference = serializers.CharField(source="article.reference")
    libelle = serializers.CharField(source="article.libelle")
    famille = serializers.CharField(source="article.famille")
    quantite = serializers.IntegerField()
    valeur_achat = serializers.DecimalField(max_digits=14, decimal_places=3, allow_null=True)


class StockADateResultatSerializer(serializers.Serializer):
    date = serializers.DateField()
    magasin = serializers.CharField()
    articles = serializers.IntegerField()
    quantite = serializers.IntegerField()
    valeur_achat = serializers.DecimalField(max_digits=16, decimal_places=3)
    lignes = StockADateSerializer(many=True)


class StockADateViewSet(viewsets.ViewSet):
    """Stock d'un magasin tel qu'il était à la fin d'un jour donné."""

    permissions_requises = {"list": "stock.view_article"}

    @extend_schema(
        parameters=[
            OpenApiParameter("magasin", OpenApiTypes.UUID, required=True),
            OpenApiParameter("date", OpenApiTypes.DATE, description="Par défaut : aujourd'hui."),
            OpenApiParameter("famille", OpenApiTypes.STR, enum=Article.Famille.values),
            OpenApiParameter("recherche", OpenApiTypes.STR),
            OpenApiParameter(
                "depot", OpenApiTypes.UUID, description="Par défaut : tous les dépôts du magasin."
            ),
        ],
        responses=StockADateResultatSerializer,
    )
    def list(self, request):
        if not request.query_params.get("magasin"):
            raise ValidationError({"magasin": "Choisir le magasin."})
        magasin = _magasin(request.query_params["magasin"], "magasin")
        if not request.user.has_perm("stock.view_article", magasin):
            raise PermissionDenied("Pas de droit de voir le stock de ce magasin.")
        jour = _date(request, "date", timezone.localdate())
        lignes = sorties.stock_a_la_date(
            magasin,
            jour,
            famille=request.query_params.get("famille", ""),
            recherche=request.query_params.get("recherche", ""),
            depot=(
                _depot(magasin, request.query_params["depot"])
                if request.query_params.get("depot")
                else None
            ),
        )
        valeur = sum((ligne["valeur_achat"] or 0 for ligne in lignes), 0)
        resultat = {
            "date": jour,
            "magasin": magasin.nom,
            "articles": len(lignes),
            "quantite": sum(ligne["quantite"] for ligne in lignes),
            "valeur_achat": valeur,
            "lignes": lignes,
        }
        return Response(StockADateResultatSerializer(resultat).data)
