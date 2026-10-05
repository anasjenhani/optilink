import uuid

from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.reseau.models import Magasin

from ..models import (
    BonReception,
    CasseVerre,
    CommandeFournisseur,
    Fournisseur,
    LigneCommandeFournisseur,
)
from ..receptions import (
    ReceptionImpossible,
    derniers_prix,
    enregistrer_reception,
    lignes_a_recevoir,
    taux_tva_par_defaut,
)
from ..services import (
    CasseImpossible,
    CommandeFournisseurImpossible,
    annuler_commande_fournisseur,
    declarer_casse,
    passer_commande,
    receptionner,
    verres_a_commander,
)
from .serializers import (
    BonReceptionListeSerializer,
    BonReceptionSaisieSerializer,
    BonReceptionSerializer,
    CasseVerreSaisieSerializer,
    CasseVerreSerializer,
    CommandeFournisseurSaisieSerializer,
    CommandeFournisseurSerializer,
    FournisseurSerializer,
    LigneAReceptionnerSerializer,
    VerreACommanderSerializer,
)


class FournisseurViewSet(
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.ReadOnlyModelViewSet,
):
    """Fournisseurs : recherche par colonne, création et modification de la fiche.

    Un fournisseur ne se supprime pas (ses achats restent) : on le désactive.
    """

    serializer_class = FournisseurSerializer
    lookup_field = "public_id"
    http_method_names = ["get", "post", "patch"]
    # Recherche par colonne, comme le tableau « Recherche d'un fournisseur ».
    FILTRES = {
        "code": "code__startswith",
        "nom": "nom__icontains",
        "adresse": "adresse__icontains",
        "ville": "ville__icontains",
        "telephone": "telephone__icontains",
    }

    def get_queryset(self):
        fournisseurs = Fournisseur.objects.select_related("pays").order_by("nom")
        parametres = self.request.query_params
        if self.action == "list" and parametres.get("inactifs") != "1":
            fournisseurs = fournisseurs.filter(est_actif=True)
        for cle, critere in self.FILTRES.items():
            if parametres.get(cle, "").strip():
                fournisseurs = fournisseurs.filter(**{critere: parametres[cle].strip()})
        return fournisseurs

    def perform_create(self, serializer):
        pays = serializer.validated_data.get("pays")
        if pays is None:
            magasin = Magasin.objects.select_related("pays").first()
            if magasin is None:
                raise ValidationError({"pays": "Préciser le pays du fournisseur."})
            pays = magasin.pays
        serializer.save(pays=pays)


class CommandeFournisseurViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Commandes de verres aux fournisseurs, pour les commandes clients du magasin."""

    serializer_class = CommandeFournisseurSerializer
    lookup_field = "public_id"
    filterset_fields = ["statut", "magasin__public_id", "numero"]
    permissions_requises = {
        "list": "achats.view_commandefournisseur",
        "retrieve": "achats.view_commandefournisseur",
        "create": "achats.add_commandefournisseur",
        "a_commander": "achats.view_commandefournisseur",
        "receptionner": "achats.change_commandefournisseur",
        "annuler": "achats.change_commandefournisseur",
    }

    def get_queryset(self):
        return CommandeFournisseur.objects.select_related(
            "magasin", "fournisseur", "passee_par"
        ).prefetch_related("lignes__ligne_vente__vente")

    def _magasin(self, public_id):
        magasin = Magasin.objects.select_related("pays").filter(public_id=public_id).first()
        if magasin is None:
            raise ValidationError({"magasin": "Magasin inconnu ou hors de votre périmètre."})
        return magasin

    @extend_schema(
        parameters=[OpenApiParameter("magasin", OpenApiTypes.UUID, required=True)],
        responses={200: VerreACommanderSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="a-commander")
    def a_commander(self, request):
        """Verres des commandes clients qui restent à commander au fournisseur."""
        identifiant = request.query_params.get("magasin")
        if not identifiant:
            raise ValidationError({"magasin": "Préciser le magasin."})
        try:
            uuid.UUID(identifiant)
        except ValueError:
            raise ValidationError({"magasin": "Identifiant invalide."}) from None
        magasin = self._magasin(identifiant)
        lignes = verres_a_commander(magasin)
        return Response(VerreACommanderSerializer(lignes, many=True).data)

    @extend_schema(
        request=CommandeFournisseurSaisieSerializer, responses={201: CommandeFournisseurSerializer}
    )
    def create(self, request):
        saisie = CommandeFournisseurSaisieSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        donnees = saisie.validated_data
        magasin = self._magasin(donnees["magasin"])
        if not request.user.has_perm("achats.add_commandefournisseur", magasin):
            raise PermissionDenied("Pas de droit de commande fournisseur dans ce magasin.")
        fournisseur = get_object_or_404(Fournisseur, public_id=donnees["fournisseur"])
        try:
            commande = passer_commande(
                magasin=magasin,
                fournisseur=fournisseur,
                lignes=[
                    {"ligne_vente": ligne["ligne"], "details": ligne.get("details", "")}
                    for ligne in donnees["lignes"]
                ],
                auteur=request.user,
                reference_fournisseur=donnees.get("reference_fournisseur", ""),
            )
        except CommandeFournisseurImpossible as erreur:
            return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        commande = self.get_queryset().get(pk=commande.pk)
        return Response(
            CommandeFournisseurSerializer(commande).data, status=status.HTTP_201_CREATED
        )

    def _changer(self, operation, **parametres):
        try:
            commande = operation(commande=self.get_object(), **parametres)
        except CommandeFournisseurImpossible as erreur:
            return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(CommandeFournisseurSerializer(self.get_queryset().get(pk=commande.pk)).data)

    @extend_schema(request=None, responses={200: CommandeFournisseurSerializer})
    @action(detail=True, methods=["post"])
    def receptionner(self, request, public_id=None):
        """Verres reçus : les commandes clients concernées peuvent être livrées."""
        return self._changer(receptionner, utilisateur=request.user)

    @extend_schema(request=None, responses={200: CommandeFournisseurSerializer})
    @action(detail=True, methods=["post"])
    def annuler(self, request, public_id=None):
        """Les verres repassent « à commander »."""
        return self._changer(annuler_commande_fournisseur)


class CasseVerreViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    """Verres cassés ou défectueux après réception, à recommander au fournisseur."""

    serializer_class = CasseVerreSerializer
    filterset_fields = ["cause", "vente__magasin__public_id"]
    permissions_requises = {"list": "achats.view_casseverre", "create": "achats.add_casseverre"}

    def get_queryset(self):
        # Les ventes visibles portent le périmètre de magasins de l'utilisateur.
        from apps.ventes.models import Vente

        return CasseVerre.objects.filter(vente__in=Vente.objects.all()).select_related(
            "vente__magasin",
            "vente__client",
            "ligne_commande__ligne_vente",
            "ligne_commande__commande__fournisseur",
            "declaree_par",
        )

    @extend_schema(request=CasseVerreSaisieSerializer, responses={201: CasseVerreSerializer})
    def create(self, request):
        """Déclare une casse : le verre repasse « à commander » et le suivi y revient."""
        from apps.ventes.models import Vente

        saisie = CasseVerreSaisieSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        donnees = saisie.validated_data
        ligne = (
            LigneCommandeFournisseur.objects.filter(
                pk=donnees["ligne_commande"], ligne_vente__vente__in=Vente.objects.all()
            )
            .select_related("ligne_vente__vente")
            .first()
        )
        if ligne is None:
            raise ValidationError({"ligne_commande": "Verre inconnu ou hors de votre périmètre."})
        if not request.user.has_perm("achats.add_casseverre", ligne.ligne_vente.vente):
            raise PermissionDenied("Pas de droit de déclarer une casse dans ce magasin.")
        try:
            casse = declarer_casse(
                ligne_commande=ligne,
                cause=donnees["cause"],
                observation=donnees.get("observation", ""),
                utilisateur=request.user,
            )
        except CasseImpossible as erreur:
            return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        casse = self.get_queryset().get(pk=casse.pk)
        return Response(CasseVerreSerializer(casse).data, status=status.HTTP_201_CREATED)


class BonReceptionViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Bons de réception achat du magasin : liste, détail, saisie et verres à recevoir."""

    lookup_field = "public_id"
    permissions_requises = {
        "list": "achats.view_bonreception",
        "retrieve": "achats.view_bonreception",
        "create": "achats.add_bonreception",
        "a_recevoir": "achats.add_bonreception",
        "prix_achat": "achats.add_bonreception",
    }
    FILTRES = {
        "numero": "numero__icontains",
        "fournisseur": "fournisseur__nom__icontains",
        "numero_bl": "numero_bl__icontains",
        "etat": "etat",
        "numero_facture": "numero_facture__icontains",
        "observation": "observation__icontains",
        "du": "date_saisie__gte",
        "au": "date_saisie__lte",
        "magasin": "magasin__public_id",
    }

    def get_serializer_class(self):
        return BonReceptionListeSerializer if self.action == "list" else BonReceptionSerializer

    def get_queryset(self):
        bons = (
            BonReception.objects.select_related("magasin__pays", "fournisseur", "cree_par")
            .prefetch_related("lignes__article", "lignes__ligne_commande__commande")
            .annotate(total_articles=Sum("lignes__quantite", filter=Q(lignes__non_conforme=False)))
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
        # Totaux de toute la liste filtrée, comme le pied du tableau.
        totaux = self.filter_queryset(self.get_queryset()).aggregate(
            total_ht=Sum("total_ht"), total_net_ht=Sum("total_net_ht"), total_ttc=Sum("total_ttc")
        )
        articles = self.filter_queryset(self.get_queryset()).aggregate(
            n=Sum("lignes__quantite", filter=Q(lignes__non_conforme=False))
        )["n"]
        if isinstance(reponse.data, dict):
            reponse.data["totaux"] = {
                **{cle: str(valeur or 0) for cle, valeur in totaux.items()},
                "total_articles": articles or 0,
            }
        return reponse

    def _magasin(self, identifiant):
        try:
            uuid.UUID(str(identifiant))
        except ValueError:
            raise ValidationError({"magasin": "Identifiant invalide."}) from None
        magasin = Magasin.objects.select_related("pays").filter(public_id=identifiant).first()
        if magasin is None:
            raise ValidationError({"magasin": "Magasin inconnu ou hors de votre périmètre."})
        return magasin

    @extend_schema(
        parameters=[
            OpenApiParameter("magasin", OpenApiTypes.UUID, required=True),
            OpenApiParameter("fournisseur", OpenApiTypes.UUID, required=True),
        ],
        responses={200: LigneAReceptionnerSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="a-recevoir")
    def a_recevoir(self, request):
        """Verres commandés à ce fournisseur et pas encore reçus (« Importer bon commande »)."""
        magasin = self._magasin(request.query_params.get("magasin", ""))
        fournisseur = get_object_or_404(
            Fournisseur, public_id=request.query_params.get("fournisseur") or uuid.uuid4()
        )
        lignes = list(lignes_a_recevoir(magasin, fournisseur))
        articles = {ligne.article for ligne in lignes}
        contexte = {
            "prix": derniers_prix(articles),
            "taux": taux_tva_par_defaut(articles, magasin.pays),
        }
        return Response(LigneAReceptionnerSerializer(lignes, many=True, context=contexte).data)

    @extend_schema(
        parameters=[
            OpenApiParameter("magasin", OpenApiTypes.UUID, required=True),
            OpenApiParameter(
                "articles", OpenApiTypes.STR, description="UUID séparés par des virgules"
            ),
        ],
        responses={200: OpenApiTypes.OBJECT},
    )
    @action(detail=False, methods=["get"], url_path="derniers-prix")
    def prix_achat(self, request):
        """Par article : dernier prix d'achat HT et taux de TVA proposé."""
        from apps.stock.models import Article

        magasin = self._magasin(request.query_params.get("magasin", ""))
        try:
            identifiants = [
                uuid.UUID(i) for i in request.query_params.get("articles", "").split(",") if i
            ]
        except ValueError:
            raise ValidationError({"articles": "Identifiants invalides."}) from None
        articles = list(Article.objects.filter(public_id__in=identifiants))
        prix = derniers_prix(articles)
        taux = taux_tva_par_defaut(articles, magasin.pays)
        return Response(
            {
                str(article.public_id): {
                    "dernier_prix_achat": None
                    if prix.get(article.pk) is None
                    else str(prix[article.pk]),
                    "taux_tva": str(taux[article.pk]),
                }
                for article in articles
            }
        )

    @extend_schema(request=BonReceptionSaisieSerializer, responses={201: BonReceptionSerializer})
    def create(self, request):
        saisie = BonReceptionSaisieSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        donnees = saisie.validated_data
        magasin = self._magasin(donnees["magasin"])
        if not request.user.has_perm("achats.add_bonreception", magasin):
            raise PermissionDenied("Pas de droit de réception dans ce magasin.")
        fournisseur = get_object_or_404(Fournisseur, public_id=donnees["fournisseur"])
        try:
            bon = enregistrer_reception(
                magasin=magasin,
                fournisseur=fournisseur,
                numero_bl=donnees["numero_bl"],
                date_bl=donnees["date_bl"],
                date_saisie=donnees.get("date_saisie"),
                taux_remise_ex=donnees["taux_remise_ex"],
                observation=donnees.get("observation", ""),
                lignes=[dict(ligne) for ligne in donnees["lignes"]],
                auteur=request.user,
            )
        except ReceptionImpossible as erreur:
            return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        bon = self.get_queryset().get(pk=bon.pk)
        return Response(BonReceptionSerializer(bon).data, status=status.HTTP_201_CREATED)
