"""API des inventaires : ouverture, comptage, écarts, validation (correction du stock)."""

import uuid

from django.db.models import Count, Q
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.achats.models import Fournisseur
from apps.reseau.models import Magasin

from ..inventaires import (
    InventaireImpossible,
    annuler_inventaire,
    compter,
    etat,
    ouvrir_inventaire,
    perimetre,
    reprendre_comptage,
    retirer,
    terminer_comptage,
    trouver_article,
    valider_inventaire,
)
from ..models import Article, Inventaire, Monture
from .sorties import _depot


class OuvertureSerializer(serializers.Serializer):
    magasin = serializers.UUIDField()
    depot = serializers.UUIDField(
        required=False, allow_null=True, help_text="Par défaut : le dépôt de vente du magasin."
    )
    famille = serializers.ChoiceField(
        choices=Article.Famille.choices, required=False, allow_blank=True
    )
    marque = serializers.CharField(required=False, allow_blank=True, max_length=100)
    nature = serializers.ChoiceField(
        choices=Monture.Categorie.choices, required=False, allow_blank=True
    )
    fournisseur = serializers.UUIDField(required=False, allow_null=True)
    observation = serializers.CharField(required=False, allow_blank=True)


class ChoixSerializer(serializers.Serializer):
    marques = serializers.ListField(child=serializers.CharField())
    fournisseurs = serializers.ListField(child=serializers.DictField())


class ComptageInventaireSerializer(serializers.Serializer):
    code = serializers.CharField(
        required=False, allow_blank=True, help_text="Code barre scanné ou référence tapée."
    )
    article = serializers.UUIDField(required=False)
    quantite = serializers.IntegerField(min_value=0, default=1)
    remplacer = serializers.BooleanField(
        default=False, help_text="Vrai : la quantité remplace le compté au lieu de s'y ajouter."
    )
    observation = serializers.CharField(
        required=False, allow_blank=True, max_length=200, allow_null=True, default=None
    )
    date_peremption = serializers.DateField(
        required=False,
        allow_null=True,
        help_text="Lentilles : péremption la plus proche des boîtes comptées (null l'efface).",
    )


class ValidationSerializer(serializers.Serializer):
    observation = serializers.CharField(
        allow_blank=True, help_text="Observation de la validation finale (obligatoire)."
    )


class RetraitSerializer(serializers.Serializer):
    article = serializers.UUIDField()


class LigneEtatSerializer(serializers.Serializer):
    article = serializers.UUIDField(source="article.public_id")
    reference = serializers.CharField(source="article.reference")
    code_barres = serializers.CharField(source="article.code_barres")
    libelle = serializers.CharField(source="article.libelle")
    famille = serializers.CharField(source="article.famille")
    stock_theorique = serializers.IntegerField()
    quantite_comptee = serializers.IntegerField()
    comptee = serializers.BooleanField()
    ecart = serializers.IntegerField()
    observation = serializers.CharField()
    date_peremption = serializers.DateField(allow_null=True)


def _nom(utilisateur):
    if utilisateur is None:
        return ""
    return utilisateur.get_full_name() or utilisateur.get_username()


class InventaireListeSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    magasin = serializers.CharField(source="magasin.nom", read_only=True)
    magasin_id = serializers.UUIDField(source="magasin.public_id", read_only=True)
    depot = serializers.CharField(source="depot.nom", read_only=True)
    depot_id = serializers.UUIDField(source="depot.public_id", read_only=True)
    famille_libelle = serializers.SerializerMethodField()
    perimetre = serializers.SerializerMethodField()
    fournisseur = serializers.CharField(source="fournisseur.nom", default="", read_only=True)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    articles_comptes = serializers.IntegerField(read_only=True)
    cree_par = serializers.SerializerMethodField()
    valide_par = serializers.SerializerMethodField()
    comptage_termine_par = serializers.SerializerMethodField()

    class Meta:
        model = Inventaire
        fields = [
            "id",
            "numero",
            "magasin",
            "magasin_id",
            "depot",
            "depot_id",
            "famille",
            "famille_libelle",
            "marque",
            "nature",
            "fournisseur",
            "perimetre",
            "statut",
            "statut_libelle",
            "articles_comptes",
            "observation",
            "cree_par",
            "cree_le",
            "valide_par",
            "valide_le",
            "comptage_termine_par",
            "comptage_termine_le",
            "observation_validation",
        ]

    def get_famille_libelle(self, inventaire) -> str:
        return inventaire.get_famille_display() if inventaire.famille else "Tout le stock"

    def get_perimetre(self, inventaire) -> str:
        return perimetre(inventaire)

    def get_cree_par(self, inventaire) -> str:
        return _nom(inventaire.cree_par)

    def get_valide_par(self, inventaire) -> str:
        return _nom(inventaire.valide_par)

    def get_comptage_termine_par(self, inventaire) -> str:
        return _nom(inventaire.comptage_termine_par)


class InventaireSerializer(InventaireListeSerializer):
    lignes = serializers.SerializerMethodField()

    class Meta(InventaireListeSerializer.Meta):
        fields = InventaireListeSerializer.Meta.fields + ["lignes"]

    @extend_schema(responses=LigneEtatSerializer(many=True))
    def get_lignes(self, inventaire) -> list:
        return LigneEtatSerializer(etat(inventaire), many=True).data


class InventaireViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Inventaires des magasins du périmètre."""

    lookup_field = "public_id"
    permissions_requises = {
        "list": "stock.view_inventaire",
        "retrieve": "stock.view_inventaire",
        "create": "stock.add_inventaire",
        "choix": "stock.add_inventaire",
        "compter": "stock.change_inventaire",
        "retirer": "stock.change_inventaire",
        "terminer": "stock.valider_inventaire",
        "reprendre": "stock.valider_inventaire",
        "valider": "stock.valider_inventaire",
        "annuler": "stock.valider_inventaire",
    }
    FILTRES = {
        "magasin": "magasin__public_id",
        "numero": "numero__icontains",
        "statut": "statut",
        "du": "cree_le__date__gte",
        "au": "cree_le__date__lte",
    }

    def get_serializer_class(self):
        return InventaireListeSerializer if self.action == "list" else InventaireSerializer

    def get_queryset(self):
        inventaires = (
            Inventaire.objects.select_related(
                "magasin",
                "depot",
                "fournisseur",
                "cree_par",
                "valide_par",
                "comptage_termine_par",
            )
            .annotate(articles_comptes=Count("lignes", filter=Q(lignes__quantite_comptee__gt=0)))
            .order_by("-cree_le")
        )
        if self.action == "list":
            params = self.request.query_params
            for cle, critere in self.FILTRES.items():
                valeur = params.get(cle, "").strip()
                if valeur:
                    if cle == "magasin":
                        try:
                            uuid.UUID(valeur)
                        except ValueError:
                            raise ValidationError({cle: "Identifiant invalide."}) from None
                    inventaires = inventaires.filter(**{critere: valeur})
        return inventaires

    def _reponse(self, inventaire, code=status.HTTP_200_OK):
        return Response(
            InventaireSerializer(self.get_queryset().get(pk=inventaire.pk)).data, status=code
        )

    @extend_schema(request=OuvertureSerializer, responses={201: InventaireSerializer})
    def create(self, request):
        saisie = OuvertureSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        donnees = saisie.validated_data
        magasin = (
            Magasin.objects.select_related("pays").filter(public_id=donnees["magasin"]).first()
        )
        if magasin is None:
            raise ValidationError({"magasin": "Magasin inconnu."})
        if not request.user.has_perm("stock.add_inventaire", magasin):
            raise PermissionDenied("Pas de droit d'ouvrir un inventaire dans ce magasin.")
        fournisseur = None
        if donnees.get("fournisseur"):
            fournisseur = Fournisseur.objects.filter(public_id=donnees["fournisseur"]).first()
            if fournisseur is None:
                raise ValidationError({"fournisseur": "Fournisseur inconnu."})
        try:
            inventaire = ouvrir_inventaire(
                magasin=magasin,
                auteur=request.user,
                famille=donnees.get("famille", ""),
                marque=donnees.get("marque", ""),
                nature=donnees.get("nature", ""),
                fournisseur=fournisseur,
                observation=donnees.get("observation", ""),
                depot=_depot(magasin, donnees.get("depot")),
            )
        except InventaireImpossible as erreur:
            return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        return self._reponse(inventaire, status.HTTP_201_CREATED)

    @extend_schema(responses=ChoixSerializer)
    @action(detail=False)
    def choix(self, request):
        """Marques de montures et fournisseurs proposés pour limiter un inventaire."""
        marques = (
            Monture.objects.exclude(marque="")
            .order_by("marque")
            .values_list("marque", flat=True)
            .distinct()
        )
        fournisseurs = Fournisseur.objects.filter(est_actif=True).order_by("nom")
        return Response(
            {
                "marques": list(marques),
                "fournisseurs": [{"id": str(f.public_id), "nom": f.nom} for f in fournisseurs],
            }
        )

    def _erreur(self, erreur):
        return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(request=ComptageInventaireSerializer, responses={200: InventaireSerializer})
    @action(detail=True, methods=["post"])
    def compter(self, request, public_id=None):
        """Compte un article : scan (``code``) ou choix dans la liste (``article``)."""
        inventaire = self.get_object()
        self._exiger_correction(request, inventaire)
        saisie = ComptageInventaireSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        donnees = saisie.validated_data
        try:
            if donnees.get("article"):
                article = Article.objects.filter(public_id=donnees["article"]).first()
                if article is None:
                    raise InventaireImpossible("Article inconnu.")
            else:
                article = trouver_article(donnees.get("code", ""))
            compter(
                inventaire,
                article,
                quantite=donnees["quantite"],
                remplacer=donnees["remplacer"],
                observation=donnees["observation"],
                **{c: donnees[c] for c in ("date_peremption",) if c in donnees},
            )
        except InventaireImpossible as erreur:
            return self._erreur(erreur)
        return self._reponse(inventaire)

    @extend_schema(request=RetraitSerializer, responses={200: InventaireSerializer})
    @action(detail=True, methods=["post"])
    def retirer(self, request, public_id=None):
        inventaire = self.get_object()
        self._exiger_correction(request, inventaire)
        saisie = RetraitSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        article = Article.objects.filter(public_id=saisie.validated_data["article"]).first()
        if article is None:
            raise ValidationError({"article": "Article inconnu."})
        try:
            retirer(inventaire, article)
        except InventaireImpossible as erreur:
            return self._erreur(erreur)
        return self._reponse(inventaire)

    def _exiger_correction(self, request, inventaire):
        """En vérification, seul le responsable (droit de valider) corrige les quantités."""
        if inventaire.statut == Inventaire.Statut.A_VERIFIER and not request.user.has_perm(
            "stock.valider_inventaire", inventaire
        ):
            raise PermissionDenied(
                "Le comptage est terminé : seul le responsable corrige les quantités."
            )

    @extend_schema(request=None, responses={200: InventaireSerializer})
    @action(detail=True, methods=["post"])
    def terminer(self, request, public_id=None):
        """Fin du comptage : passage en vérification des écarts."""
        inventaire = self.get_object()
        try:
            terminer_comptage(inventaire, auteur=request.user)
        except InventaireImpossible as erreur:
            return self._erreur(erreur)
        return self._reponse(inventaire)

    @extend_schema(request=None, responses={200: InventaireSerializer})
    @action(detail=True, methods=["post"])
    def reprendre(self, request, public_id=None):
        """Retour au comptage depuis la vérification."""
        inventaire = self.get_object()
        try:
            reprendre_comptage(inventaire)
        except InventaireImpossible as erreur:
            return self._erreur(erreur)
        return self._reponse(inventaire)

    @extend_schema(request=ValidationSerializer, responses={200: InventaireSerializer})
    @action(detail=True, methods=["post"])
    def valider(self, request, public_id=None):
        """Validation finale : corrige le stock du magasin selon les quantités vérifiées."""
        inventaire = self.get_object()
        saisie = ValidationSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        try:
            valider_inventaire(
                inventaire, auteur=request.user, observation=saisie.validated_data["observation"]
            )
        except InventaireImpossible as erreur:
            return self._erreur(erreur)
        return self._reponse(inventaire)

    @extend_schema(request=None, responses={200: InventaireSerializer})
    @action(detail=True, methods=["post"])
    def annuler(self, request, public_id=None):
        """Abandonne l'inventaire en cours, sans toucher au stock."""
        inventaire = self.get_object()
        try:
            annuler_inventaire(inventaire)
        except InventaireImpossible as erreur:
            return self._erreur(erreur)
        return self._reponse(inventaire)
