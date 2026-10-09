import uuid
from decimal import Decimal

from django.db.models import Prefetch
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.reseau.models import Magasin

from .. import reglements
from ..models import FactureAchat, Fournisseur, ImputationReglement, ReglementFournisseur


class ImputationSerializer(serializers.ModelSerializer):
    facture = serializers.UUIDField(source="facture.public_id")
    facture_numero = serializers.CharField(source="facture.numero")
    reference_fournisseur = serializers.CharField(source="facture.reference_fournisseur")
    date_reference = serializers.DateField(source="facture.date_reference")
    facture_total_ttc = serializers.DecimalField(
        source="facture.total_ttc", max_digits=14, decimal_places=3
    )

    class Meta:
        model = ImputationReglement
        fields = [
            "facture",
            "facture_numero",
            "reference_fournisseur",
            "date_reference",
            "facture_total_ttc",
            "montant",
            "le",
        ]


class ReglementFournisseurSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    magasin = serializers.CharField(source="magasin.public_id")
    magasin_nom = serializers.CharField(source="magasin.nom")
    societe = serializers.CharField(source="magasin.societe.raison_sociale")
    societe_matricule = serializers.CharField(source="magasin.societe.matricule_fiscal")
    societe_adresse = serializers.CharField(source="magasin.societe.adresse")
    devise = serializers.CharField(source="magasin.pays.devise")
    decimales = serializers.IntegerField(source="magasin.pays.decimales")
    fournisseur = serializers.CharField(source="fournisseur.public_id")
    fournisseur_nom = serializers.CharField(source="fournisseur.nom")
    fournisseur_matricule = serializers.CharField(source="fournisseur.matricule_fiscal")
    fournisseur_adresse = serializers.CharField(source="fournisseur.adresse")
    mode_libelle = serializers.CharField(source="get_mode_display")
    statut_libelle = serializers.CharField(source="get_statut_display")
    total_regle = serializers.DecimalField(max_digits=14, decimal_places=3)
    disponible = serializers.SerializerMethodField()
    imputations = ImputationSerializer(many=True)
    cree_par = serializers.SerializerMethodField()

    class Meta:
        model = ReglementFournisseur
        fields = [
            "id",
            "numero",
            "magasin",
            "magasin_nom",
            "societe",
            "societe_matricule",
            "societe_adresse",
            "devise",
            "decimales",
            "fournisseur",
            "fournisseur_nom",
            "fournisseur_matricule",
            "fournisseur_adresse",
            "date_reglement",
            "mode",
            "mode_libelle",
            "reference",
            "banque",
            "echeance",
            "statut",
            "statut_libelle",
            "debite_le",
            "montant",
            "taux_retenue",
            "retenue",
            "total_regle",
            "disponible",
            "observation",
            "imputations",
            "cree_par",
            "cree_le",
        ]

    def get_disponible(self, reglement) -> str:
        impute = sum((i.montant for i in reglement.imputations.all()), Decimal("0"))
        return str(reglement.total_regle - impute)

    def get_cree_par(self, reglement) -> str:
        return reglement.cree_par.get_full_name() or reglement.cree_par.get_username()


class LigneImputationSerializer(serializers.Serializer):
    facture = serializers.UUIDField()
    montant = serializers.DecimalField(max_digits=14, decimal_places=3)


class SaisieReglementSerializer(serializers.Serializer):
    magasin = serializers.UUIDField()
    fournisseur = serializers.UUIDField()
    date_reglement = serializers.DateField()
    mode = serializers.ChoiceField(choices=ReglementFournisseur.Mode.choices)
    montant = serializers.DecimalField(max_digits=14, decimal_places=3)
    taux_retenue = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, default=0
    )
    retenue = serializers.DecimalField(max_digits=14, decimal_places=3, required=False, default=0)
    reference = serializers.CharField(required=False, allow_blank=True, max_length=60)
    banque = serializers.CharField(required=False, allow_blank=True, max_length=100)
    echeance = serializers.DateField(required=False, allow_null=True)
    observation = serializers.CharField(required=False, allow_blank=True)
    lignes = LigneImputationSerializer(many=True, required=False)


class ImputationAvanceSerializer(serializers.Serializer):
    le = serializers.DateField()
    lignes = LigneImputationSerializer(many=True)


class DebitSerializer(serializers.Serializer):
    le = serializers.DateField()


class FactureARegler(serializers.Serializer):
    id = serializers.UUIDField()
    numero = serializers.CharField()
    reference_fournisseur = serializers.CharField()
    date_reference = serializers.DateField()
    total_ttc = serializers.DecimalField(max_digits=14, decimal_places=3)
    regle = serializers.DecimalField(max_digits=14, decimal_places=3)
    reste = serializers.DecimalField(max_digits=14, decimal_places=3)


class AvanceSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    numero = serializers.CharField()
    date_reglement = serializers.DateField()
    disponible = serializers.DecimalField(max_digits=14, decimal_places=3)


class SituationFournisseurSerializer(serializers.Serializer):
    factures = FactureARegler(many=True)
    avances = AvanceSerializer(many=True)
    total_reste = serializers.DecimalField(max_digits=14, decimal_places=3)
    total_avances = serializers.DecimalField(max_digits=14, decimal_places=3)


def _uuid(valeur, champ):
    try:
        return uuid.UUID(str(valeur))
    except ValueError:
        raise ValidationError({champ: "Identifiant invalide."}) from None


class ReglementFournisseurViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Règlements fournisseurs : paiement des factures achat, avances et échéancier.

    Filtres : ``fournisseur``, ``magasin``, ``mode``, ``statut`` (``a_echoir`` pour
    l'échéancier, trié par échéance), ``du`` / ``au`` (date du règlement).
    """

    serializer_class = ReglementFournisseurSerializer
    lookup_field = "public_id"
    http_method_names = ["get", "post", "delete"]
    permissions_requises = {
        "list": "achats.view_reglementfournisseur",
        "retrieve": "achats.view_reglementfournisseur",
        "situation": "achats.view_reglementfournisseur",
        "create": "achats.add_reglementfournisseur",
        "imputer": "achats.add_reglementfournisseur",
        "debiter": "achats.change_reglementfournisseur",
        "destroy": "achats.delete_reglementfournisseur",
    }
    FILTRES = {
        "fournisseur": "fournisseur__public_id",
        "magasin": "magasin__public_id",
        "mode": "mode",
        "statut": "statut",
        "du": "date_reglement__gte",
        "au": "date_reglement__lte",
    }

    def get_queryset(self):
        reglements_ = ReglementFournisseur.objects.select_related(
            "magasin__pays", "magasin__societe", "fournisseur", "cree_par"
        ).prefetch_related(
            Prefetch(
                "imputations",
                queryset=ImputationReglement.objects.select_related("facture").order_by("pk"),
            )
        )
        if self.action != "list":
            return reglements_
        for parametre, champ in self.FILTRES.items():
            valeur = self.request.query_params.get(parametre)
            if valeur:
                if parametre in ("fournisseur", "magasin"):
                    valeur = _uuid(valeur, parametre)
                reglements_ = reglements_.filter(**{champ: valeur})
        if self.request.query_params.get("statut") == ReglementFournisseur.Statut.A_ECHOIR:
            reglements_ = reglements_.order_by("echeance", "sequence")
        return reglements_

    def _magasin(self, identifiant, permission):
        magasin = Magasin.objects.select_related("pays").filter(public_id=identifiant).first()
        if magasin is None:
            raise ValidationError({"magasin": "Magasin inconnu ou hors de votre périmètre."})
        if not self.request.user.has_perm(permission, magasin):
            raise PermissionDenied("Pas de droit sur les règlements fournisseurs de ce magasin.")
        return magasin

    @staticmethod
    def _fournisseur(identifiant):
        fournisseur = Fournisseur.objects.filter(public_id=identifiant).first()
        if fournisseur is None:
            raise ValidationError({"fournisseur": "Fournisseur inconnu."})
        return fournisseur

    @staticmethod
    def _lignes(lignes):
        factures = {
            f.public_id: f
            for f in FactureAchat.objects.filter(
                public_id__in=[ligne["facture"] for ligne in lignes]
            )
        }
        if len(factures) != len({ligne["facture"] for ligne in lignes}):
            raise ValidationError({"lignes": "Facture inconnue ou hors de votre périmètre."})
        return [(factures[ligne["facture"]], ligne["montant"]) for ligne in lignes]

    def _repondre(self, reglement, code=status.HTTP_200_OK):
        return Response(
            ReglementFournisseurSerializer(self.get_queryset().get(pk=reglement.pk)).data, code
        )

    def _reglement(self, permission):
        reglement = self.get_object()
        if not self.request.user.has_perm(permission, reglement):
            raise PermissionDenied("Pas de droit sur les règlements fournisseurs de ce magasin.")
        return reglement

    @extend_schema(
        parameters=[
            OpenApiParameter("fournisseur", OpenApiTypes.UUID),
            OpenApiParameter("magasin", OpenApiTypes.UUID),
            OpenApiParameter("mode", OpenApiTypes.STR),
            OpenApiParameter("statut", OpenApiTypes.STR),
            OpenApiParameter("du", OpenApiTypes.DATE),
            OpenApiParameter("au", OpenApiTypes.DATE),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        parameters=[
            OpenApiParameter("magasin", OpenApiTypes.UUID, required=True),
            OpenApiParameter("fournisseur", OpenApiTypes.UUID, required=True),
        ],
        responses=SituationFournisseurSerializer,
    )
    @action(detail=False, methods=["get"])
    def situation(self, request):
        """Factures non soldées du fournisseur dans ce magasin, et avances encore à imputer."""
        magasin = self._magasin(
            _uuid(request.query_params.get("magasin", ""), "magasin"),
            "achats.view_reglementfournisseur",
        )
        fournisseur = self._fournisseur(
            _uuid(request.query_params.get("fournisseur", ""), "fournisseur")
        )
        factures = []
        for facture in reglements.factures_a_regler(magasin, fournisseur):
            regle = reglements.deja_regle(facture)
            factures.append(
                {
                    "id": facture.public_id,
                    "numero": facture.numero,
                    "reference_fournisseur": facture.reference_fournisseur,
                    "date_reference": facture.date_reference,
                    "total_ttc": facture.total_ttc,
                    "regle": regle,
                    "reste": facture.total_ttc - regle,
                }
            )
        avances = []
        for reglement in ReglementFournisseur.objects.filter(
            magasin=magasin, fournisseur=fournisseur
        ).order_by("date_reglement", "sequence"):
            reste = reglements.disponible(reglement)
            if reste > 0:
                avances.append(
                    {
                        "id": reglement.public_id,
                        "numero": reglement.numero,
                        "date_reglement": reglement.date_reglement,
                        "disponible": reste,
                    }
                )
        return Response(
            SituationFournisseurSerializer(
                {
                    "factures": factures,
                    "avances": avances,
                    "total_reste": sum((f["reste"] for f in factures), Decimal("0")),
                    "total_avances": sum((a["disponible"] for a in avances), Decimal("0")),
                }
            ).data
        )

    @extend_schema(
        request=SaisieReglementSerializer, responses={201: ReglementFournisseurSerializer}
    )
    def create(self, request):
        saisie = SaisieReglementSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        d = saisie.validated_data
        magasin = self._magasin(d["magasin"], "achats.add_reglementfournisseur")
        try:
            reglement = reglements.regler(
                magasin=magasin,
                fournisseur=self._fournisseur(d["fournisseur"]),
                date_reglement=d["date_reglement"],
                mode=d["mode"],
                montant=d["montant"],
                taux_retenue=d["taux_retenue"],
                retenue=d["retenue"],
                reference=d.get("reference", ""),
                banque=d.get("banque", ""),
                echeance=d.get("echeance"),
                observation=d.get("observation", ""),
                lignes=self._lignes(d.get("lignes", [])),
                utilisateur=request.user,
            )
        except reglements.ReglementImpossible as erreur:
            return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        return self._repondre(reglement, status.HTTP_201_CREATED)

    @extend_schema(request=ImputationAvanceSerializer, responses=ReglementFournisseurSerializer)
    @action(detail=True, methods=["post"])
    def imputer(self, request, public_id=None):
        """Solde des factures avec l'avance restante de ce règlement."""
        reglement = self._reglement("achats.add_reglementfournisseur")
        saisie = ImputationAvanceSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        try:
            reglements.imputer_avance(
                reglement,
                lignes=self._lignes(saisie.validated_data["lignes"]),
                le=saisie.validated_data["le"],
            )
        except reglements.ReglementImpossible as erreur:
            return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        return self._repondre(reglement)

    @extend_schema(request=DebitSerializer, responses=ReglementFournisseurSerializer)
    @action(detail=True, methods=["post"])
    def debiter(self, request, public_id=None):
        """Le chèque ou la traite a été débité par la banque."""
        reglement = self._reglement("achats.change_reglementfournisseur")
        saisie = DebitSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        try:
            reglements.debiter(reglement, le=saisie.validated_data["le"])
        except reglements.ReglementImpossible as erreur:
            return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        return self._repondre(reglement)

    def destroy(self, request, public_id=None):
        """Annule un règlement saisi par erreur ; ses factures redeviennent à régler."""
        reglements.annuler(self._reglement("achats.delete_reglementfournisseur"))
        return Response(status=status.HTTP_204_NO_CONTENT)
