import uuid

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.crm.models import Client
from apps.optique.models import Prescription
from apps.reseau.models import Magasin
from apps.stock.models import Article

from ..models import Avoir, Devis, Facture, Vente
from ..services import (
    AvoirImpossible,
    DevisImpossible,
    FactureImpossible,
    VenteInvalide,
    accepter_devis,
    annuler_vente,
    emettre_avoir,
    encaisser_devis,
    enregistrer_vente,
    etablir_devis,
    generer_facture,
    livrer_commande,
    refuser_devis,
    regler_commande,
)
from .serializers import (
    AvoirSaisieSerializer,
    AvoirSerializer,
    DevisSaisieSerializer,
    DevisSerializer,
    EncaissementDevisSerializer,
    FactureSaisieSerializer,
    FactureSerializer,
    LivraisonSerializer,
    ReglementSerializer,
    VenteSaisieSerializer,
    VenteSerializer,
)


class VenteViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Ventes du périmètre. Une vente enregistrée n'est jamais modifiée ; une commande reçoit
    ensuite ses règlements, puis sa livraison."""

    serializer_class = VenteSerializer
    lookup_field = "public_id"
    filterset_fields = ["numero", "statut", "peniche", "magasin__public_id"]

    def get_queryset(self):
        return Vente.objects.select_related(
            "magasin", "vendeur", "client", "facture"
        ).prefetch_related("lignes__article", "lignes__retours", "paiements")

    def _apres(self, operation, **parametres):
        try:
            vente = operation(vente=self.get_object(), utilisateur=self.request.user, **parametres)
        except VenteInvalide as erreur:
            return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(VenteSerializer(self.get_queryset().get(pk=vente.pk)).data)

    @extend_schema(request=ReglementSerializer, responses={200: VenteSerializer})
    @action(detail=True, methods=["post"])
    def reglement(self, request, public_id=None):
        """Encaisse un règlement sur une commande pas encore soldée."""
        saisie = ReglementSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        return self._apres(regler_commande, paiements=saisie.validated_data["paiements"])

    @extend_schema(request=LivraisonSerializer, responses={200: VenteSerializer})
    @action(detail=True, methods=["post"])
    def livrer(self, request, public_id=None):
        """Livre une commande ; le solde éventuel est encaissé en même temps."""
        saisie = LivraisonSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        return self._apres(livrer_commande, paiements=saisie.validated_data.get("paiements", []))

    @extend_schema(request=VenteSaisieSerializer, responses={201: VenteSerializer})
    def create(self, request):
        saisie = VenteSaisieSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        donnees = saisie.validated_data

        magasin = Magasin.objects.filter(public_id=donnees["magasin"]).first()
        if magasin is None:
            raise ValidationError({"magasin": "Magasin inconnu ou hors de votre périmètre."})
        user = request.user
        if not user.has_perm("ventes.add_vente", magasin):
            raise PermissionDenied("Pas de droit de vente dans ce magasin.")
        if any(ligne["remise_pct"] > 0 for ligne in donnees["lignes"]) and not user.has_perm(
            "ventes.appliquer_remise", magasin
        ):
            raise PermissionDenied("Remise non autorisée pour votre rôle.")

        articles = Article.objects.filter(
            public_id__in={ligne["article"] for ligne in donnees["lignes"]}, est_actif=True
        ).in_bulk(field_name="public_id")
        manquants = {ligne["article"] for ligne in donnees["lignes"]} - set(articles)
        if manquants:
            raise ValidationError({"lignes": "Article inconnu ou retiré de la vente."})

        client = None
        if donnees.get("client"):
            if not user.has_perm("crm.view_client"):
                raise PermissionDenied("Pas d'accès aux fiches clients.")
            client = Client.objects.filter(public_id=donnees["client"]).first()
            if client is None:
                raise ValidationError({"client": "Client inconnu."})

        try:
            vente = enregistrer_vente(
                magasin=magasin,
                vendeur=user,
                lignes=[
                    {**ligne, "article": articles[ligne["article"]]} for ligne in donnees["lignes"]
                ],
                paiements=donnees["paiements"],
                client=client,
                commande=donnees["commande"],
                livraison_prevue_le=donnees.get("livraison_prevue_le"),
                peniche=donnees.get("peniche"),
            )
        except VenteInvalide as erreur:
            return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        vente = self.get_queryset().get(pk=vente.pk)
        return Response(VenteSerializer(vente).data, status=status.HTTP_201_CREATED)


class FactureViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Factures du périmètre. Une facture se génère à part, pour une vente entièrement payée."""

    serializer_class = FactureSerializer
    lookup_field = "public_id"
    filterset_fields = ["numero"]

    def get_queryset(self):
        return Facture.objects.select_related(
            "magasin", "vente", "client", "emise_par"
        ).prefetch_related("vente__lignes__article", "vente__lignes__retours")

    @extend_schema(request=FactureSaisieSerializer, responses={201: FactureSerializer})
    def create(self, request):
        saisie = FactureSaisieSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        donnees = saisie.validated_data

        vente = (
            Vente.objects.select_related("magasin", "client")
            .filter(public_id=donnees["vente"])
            .first()
        )
        if vente is None:
            raise ValidationError({"vente": "Vente inconnue ou hors de votre périmètre."})
        if not request.user.has_perm("ventes.add_facture", vente.magasin):
            raise PermissionDenied("Pas de droit de facturation dans ce magasin.")
        client = vente.client
        if donnees.get("client"):
            client = Client.objects.filter(public_id=donnees["client"]).first()
            if client is None:
                raise ValidationError({"client": "Client inconnu."})

        try:
            facture = generer_facture(
                vente=vente,
                client=client,
                emetteur=request.user,
                mode_paiement_timbre=donnees.get("mode_paiement_timbre", ""),
            )
        except FactureImpossible as erreur:
            return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        facture = self.get_queryset().get(pk=facture.pk)
        return Response(FactureSerializer(facture).data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter("client", OpenApiTypes.UUID, description="Devis d'un client"),
            OpenApiParameter("statut", OpenApiTypes.STR, enum=Devis.Statut.values),
        ]
    )
)
class DevisViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Devis d'équipement du périmètre : établir, accepter, refuser, encaisser au prix du devis."""

    serializer_class = DevisSerializer
    lookup_field = "public_id"
    filterset_fields = ["numero", "statut"]
    permissions_requises = {
        "list": "ventes.view_devis",
        "retrieve": "ventes.view_devis",
        "create": "ventes.add_devis",
        "accepter": "ventes.change_devis",
        "refuser": "ventes.change_devis",
        "encaisser": ["ventes.view_devis", "ventes.add_vente"],
    }

    def get_queryset(self):
        devis = Devis.objects.select_related(
            "magasin", "client", "prescription", "etabli_par", "vente"
        ).prefetch_related("lignes__article")
        client_id = self.request.query_params.get("client")
        if self.action == "list" and client_id:
            try:
                devis = devis.filter(client__public_id=uuid.UUID(client_id))
            except ValueError:
                raise ValidationError({"client": "Identifiant invalide."}) from None
        return devis

    def _reponse(self, devis, code=status.HTTP_200_OK):
        devis = self.get_queryset().get(pk=devis.pk)
        return Response(self.get_serializer(devis).data, status=code)

    @extend_schema(request=DevisSaisieSerializer, responses={201: DevisSerializer})
    def create(self, request):
        saisie = DevisSaisieSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        donnees = saisie.validated_data
        user = request.user

        magasin = Magasin.objects.filter(public_id=donnees["magasin"]).first()
        if magasin is None:
            raise ValidationError({"magasin": "Magasin inconnu ou hors de votre périmètre."})
        if not user.has_perm("ventes.add_devis", magasin):
            raise PermissionDenied("Pas de droit d'établir un devis dans ce magasin.")
        if any(ligne["remise_pct"] > 0 for ligne in donnees["lignes"]) and not user.has_perm(
            "ventes.appliquer_remise", magasin
        ):
            raise PermissionDenied("Remise non autorisée pour votre rôle.")
        if not user.has_perm("crm.view_client"):
            raise PermissionDenied("Pas d'accès aux fiches clients.")
        client = Client.objects.filter(public_id=donnees["client"]).first()
        if client is None:
            raise ValidationError({"client": "Client inconnu."})
        prescription = None
        if donnees.get("prescription"):
            if not user.has_perm("optique.view_prescription"):
                raise PermissionDenied("Pas d'accès aux ordonnances.")
            prescription = Prescription.objects.filter(public_id=donnees["prescription"]).first()
            if prescription is None:
                raise ValidationError({"prescription": "Ordonnance inconnue."})

        uuids = {ligne["article"] for ligne in donnees["lignes"]}
        articles = Article.objects.filter(public_id__in=uuids, est_actif=True).in_bulk(
            field_name="public_id"
        )
        if uuids - set(articles):
            raise ValidationError({"lignes": "Article inconnu ou retiré de la vente."})

        try:
            devis = etablir_devis(
                magasin=magasin,
                auteur=user,
                client=client,
                prescription=prescription,
                lignes=[
                    {**ligne, "article": articles[ligne["article"]]} for ligne in donnees["lignes"]
                ],
                valable_jusqu_au=donnees.get("valable_jusqu_au"),
                remarques=donnees.get("remarques", ""),
            )
        except DevisImpossible as erreur:
            return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        return self._reponse(devis, status.HTTP_201_CREATED)

    def _changer(self, operation, **parametres):
        try:
            resultat = operation(devis=self.get_object(), **parametres)
        except DevisImpossible as erreur:
            return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        return resultat

    @extend_schema(request=None, responses={200: DevisSerializer})
    @action(detail=True, methods=["post"])
    def accepter(self, request, public_id=None):
        resultat = self._changer(accepter_devis)
        return resultat if isinstance(resultat, Response) else self._reponse(resultat)

    @extend_schema(request=None, responses={200: DevisSerializer})
    @action(detail=True, methods=["post"])
    def refuser(self, request, public_id=None):
        resultat = self._changer(refuser_devis)
        return resultat if isinstance(resultat, Response) else self._reponse(resultat)

    @extend_schema(request=EncaissementDevisSerializer, responses={201: VenteSerializer})
    @action(detail=True, methods=["post"])
    def encaisser(self, request, public_id=None):
        """Encaisse le devis en caisse, au prix du devis ; renvoie le ticket."""
        saisie = EncaissementDevisSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        donnees = saisie.validated_data
        resultat = self._changer(
            encaisser_devis,
            vendeur=request.user,
            paiements=donnees["paiements"],
            commande=donnees["commande"],
            livraison_prevue_le=donnees.get("livraison_prevue_le"),
            peniche=donnees.get("peniche"),
        )
        if isinstance(resultat, Response):
            return resultat
        vente = VenteViewSet().get_queryset().get(pk=resultat.pk)
        return Response(VenteSerializer(vente).data, status=status.HTTP_201_CREATED)


class AvoirViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Avoirs du périmètre : retour d'articles ou annulation d'une vente, avec remboursement."""

    serializer_class = AvoirSerializer
    lookup_field = "public_id"
    filterset_fields = ["numero", "annulation"]

    def get_queryset(self):
        return Avoir.objects.select_related(
            "magasin", "vente", "facture", "client", "emis_par"
        ).prefetch_related("lignes")

    @extend_schema(request=AvoirSaisieSerializer, responses={201: AvoirSerializer})
    def create(self, request):
        saisie = AvoirSaisieSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        donnees = saisie.validated_data

        vente = Vente.objects.select_related("magasin").filter(public_id=donnees["vente"]).first()
        if vente is None:
            raise ValidationError({"vente": "Vente inconnue ou hors de votre périmètre."})
        if not request.user.has_perm("ventes.add_avoir", vente.magasin):
            raise PermissionDenied("Pas de droit d'émettre un avoir dans ce magasin.")
        commun = {
            "vente": vente,
            "motif": donnees["motif"],
            "emetteur": request.user,
            "mode_remboursement": donnees.get("mode_remboursement", ""),
        }
        try:
            if donnees["annulation"]:
                avoir = annuler_vente(**commun, remis_en_stock=donnees["remis_en_stock"])
            else:
                avoir = emettre_avoir(
                    **commun,
                    retours=[
                        {
                            "ligne_vente": r["ligne"],
                            "quantite": r["quantite"],
                            "remis_en_stock": r["remis_en_stock"],
                        }
                        for r in donnees["lignes"]
                    ],
                )
        except AvoirImpossible as erreur:
            return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        avoir = self.get_queryset().get(pk=avoir.pk)
        return Response(AvoirSerializer(avoir).data, status=status.HTTP_201_CREATED)
