import uuid
from datetime import date

from django.db.models import DecimalField, Prefetch, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils import timezone
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

from ..models import Avoir, Devis, EtapeCommande, Facture, Paiement, Vente
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
from ..suivi import EtapeImpossible, changer_etape, commandes, etat, journee
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
from .suivi import ETATS, EtapeSaisieSerializer, JourneeSerializer, SuiviSerializer
from .visites import (
    FicheVisiteSerializer,
    RecuSerializer,
    ResteVendeurSerializer,
    VenteFiltre,
    recus,
    reste_par_vendeur,
)


def _uuid(valeur, champ):
    try:
        return uuid.UUID(str(valeur))
    except ValueError:
        raise ValidationError({champ: "Identifiant invalide."}) from None


def _date(valeur, champ):
    try:
        return date.fromisoformat(valeur)
    except ValueError:
        raise ValidationError({champ: "Date attendue au format AAAA-MM-JJ."}) from None


def _entier(valeur, champ):
    try:
        return int(valeur)
    except ValueError:
        raise ValidationError({champ: "Nombre entier attendu."}) from None


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
    filterset_class = VenteFiltre

    def get_queryset(self):
        return Vente.objects.select_related(
            "magasin", "vendeur", "client__organisme", "facture"
        ).prefetch_related(
            "lignes__article",
            "lignes__retours",
            "lignes__lunette",
            "lunettes__lignes",
            "lunettes__prescription",
            "lignes__lentilles",
            "lentilles__lignes",
            "lentilles__prescription",
            "paiements",
            "prises_en_charge",
        )

    @extend_schema(responses={200: FicheVisiteSerializer})
    @action(detail=True)
    def fiche(self, request, public_id=None):
        """Fiche complète d'une visite : articles, règlements, PEC, suivi, verres, avoirs."""
        vente = (
            self.get_queryset()
            .prefetch_related(
                "paiements__recu_par",
                "prises_en_charge__organisme",
                Prefetch("etapes", queryset=EtapeCommande.objects.select_related("par")),
                "avoirs",
            )
            .get(pk=self.get_object().pk)
        )
        return Response(FicheVisiteSerializer(vente).data)

    @extend_schema(
        parameters=[
            OpenApiParameter("magasin", OpenApiTypes.UUID),
            OpenApiParameter("du", OpenApiTypes.DATE),
            OpenApiParameter("au", OpenApiTypes.DATE),
            OpenApiParameter("mode", OpenApiTypes.STR, enum=Paiement.Mode.values),
        ],
        responses={200: RecuSerializer(many=True)},
    )
    @action(detail=False, pagination_class=None, filterset_class=None)
    def recus(self, request):
        """Reçus des règlements (au plus 500, les plus récents d'abord), pour les réimprimer."""
        parametres = request.query_params
        ventes = self.get_queryset()
        if parametres.get("magasin"):
            ventes = ventes.filter(magasin__public_id=_uuid(parametres["magasin"], "magasin"))
        paiements = recus(ventes)
        for champ, filtre in (("du", "recu_le__date__gte"), ("au", "recu_le__date__lte")):
            if parametres.get(champ):
                paiements = paiements.filter(**{filtre: _date(parametres[champ], champ)})
        if parametres.get("mode"):
            paiements = paiements.filter(mode=parametres["mode"])
        return Response(RecuSerializer(paiements[:500], many=True).data)

    @extend_schema(
        parameters=[OpenApiParameter("magasin", OpenApiTypes.UUID)],
        responses={200: ResteVendeurSerializer(many=True)},
    )
    @action(detail=False, url_path="reste-par-vendeur", pagination_class=None, filterset_class=None)
    def reste_par_vendeur(self, request):
        """Reste dû sur les commandes en cours, par vendeur, avec le détail des commandes."""
        ventes = self.get_queryset().filter(statut=Vente.Statut.EN_COMMANDE)
        if request.query_params.get("magasin"):
            ventes = ventes.filter(
                magasin__public_id=_uuid(request.query_params["magasin"], "magasin")
            )
        return Response(ResteVendeurSerializer(reste_par_vendeur(ventes), many=True).data)

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
        donnees = saisie.validated_data
        if donnees["a_credit"]:
            self._verifier_credit(self.get_object().magasin)
        return self._apres(
            livrer_commande,
            paiements=donnees.get("paiements", []),
            a_credit=donnees["a_credit"],
            credit_echeance=donnees.get("credit_echeance"),
        )

    def _verifier_credit(self, magasin):
        if not self.request.user.has_perm("ventes.vendre_a_credit", magasin):
            raise PermissionDenied("Vente à crédit non autorisée pour votre rôle.")

    @extend_schema(
        parameters=[
            OpenApiParameter("magasin", OpenApiTypes.UUID, description="Un seul magasin."),
            OpenApiParameter("annee", OpenApiTypes.INT),
            OpenApiParameter("mois", OpenApiTypes.INT),
            OpenApiParameter("etat", OpenApiTypes.STR, enum=[e for e, _ in ETATS]),
            OpenApiParameter("type", OpenApiTypes.STR, enum=["verre", "lentille", "autre"]),
        ],
        responses={200: SuiviSerializer(many=True)},
    )
    @action(detail=False, pagination_class=None)
    def suivi(self, request):
        """Suivi qualité des commandes : étape de chacune, de la visite à la livraison."""
        parametres = request.query_params
        ventes = commandes(self.get_queryset()).prefetch_related(
            Prefetch("etapes", queryset=EtapeCommande.objects.order_by("le", "pk"))
        )
        if parametres.get("magasin"):
            ventes = ventes.filter(magasin__public_id=_uuid(parametres["magasin"], "magasin"))
        for champ, filtre in (("annee", "cree_le__year"), ("mois", "cree_le__month")):
            if parametres.get(champ):
                ventes = ventes.filter(**{filtre: _entier(parametres[champ], champ)})
        ventes = list(ventes[:2000])
        etats = {vente.pk: etat(vente) for vente in ventes}
        serializer = SuiviSerializer(ventes, many=True, context={"etats": etats})
        lignes = serializer.data
        if parametres.get("etat"):
            lignes = [ligne for ligne in lignes if ligne["etat"] == parametres["etat"]]
        if parametres.get("type"):
            lignes = [ligne for ligne in lignes if ligne["type"] == parametres["type"]]
        return Response(lignes)

    @extend_schema(request=EtapeSaisieSerializer, responses={200: VenteSerializer})
    @action(detail=True, methods=["post"])
    def etape(self, request, public_id=None):
        """Fait passer une commande à une étape du suivi (montage, contrôle qualité…)."""
        saisie = EtapeSaisieSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        try:
            vente = changer_etape(
                vente=self.get_object(),
                utilisateur=request.user,
                etape=saisie.validated_data["etape"],
                observation=saisie.validated_data.get("observation", ""),
            )
        except EtapeImpossible as erreur:
            return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(VenteSerializer(self.get_queryset().get(pk=vente.pk)).data)

    @extend_schema(
        parameters=[
            OpenApiParameter("magasin", OpenApiTypes.UUID, required=True),
            OpenApiParameter("date", OpenApiTypes.DATE, description="Par défaut, aujourd'hui."),
        ],
        responses={200: JourneeSerializer},
    )
    @action(detail=False, pagination_class=None)
    def journee(self, request):
        """État de la journée de vente d'un magasin : ventes, réglé, reste, encaissements."""
        parametres = request.query_params
        magasin = get_object_or_404(
            Magasin.objects.select_related("pays"),
            public_id=_uuid(parametres.get("magasin", ""), "magasin"),
        )
        jour = timezone.localdate()
        if parametres.get("date"):
            try:
                jour = date.fromisoformat(parametres["date"])
            except ValueError:
                raise ValidationError({"date": "Date attendue au format AAAA-MM-JJ."}) from None
        ventes = list(
            self.get_queryset()
            .filter(magasin=magasin, cree_le__date=jour)
            .exclude(statut=Vente.Statut.ANNULEE)
            .annotate(
                regle=Coalesce(
                    Sum(
                        "paiements__montant",
                        filter=Q(paiements__statut=Paiement.Statut.ENCAISSE),
                    ),
                    Value(0),
                    output_field=DecimalField(max_digits=14, decimal_places=3),
                )
            )
            .order_by("cree_le")
        )
        paiements = Paiement.objects.filter(
            vente__in=Vente.objects.filter(magasin=magasin), recu_le__date=jour
        )
        donnees = {
            "date": jour,
            "magasin": magasin.nom,
            "devise": magasin.pays.devise,
            **journee(ventes, paiements),
            "ventes": ventes,
        }
        return Response(JourneeSerializer(donnees).data)

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
        lunettes = self._avec_ordonnances(donnees.get("lunettes", []), user)
        lentilles = self._avec_ordonnances(donnees.get("lentilles", []), user)
        if donnees["a_credit"]:
            self._verifier_credit(magasin)

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
                lunettes=lunettes,
                lentilles=lentilles,
                a_credit=donnees["a_credit"],
                credit_echeance=donnees.get("credit_echeance"),
            )
        except VenteInvalide as erreur:
            return Response({"detail": str(erreur)}, status=status.HTTP_400_BAD_REQUEST)
        vente = self.get_queryset().get(pk=vente.pk)
        return Response(VenteSerializer(vente).data, status=status.HTTP_201_CREATED)

    def _avec_ordonnances(self, saisies, user):
        """Remplace l'identifiant d'ordonnance de chaque équipement par l'ordonnance elle-même."""
        identifiants = {s["prescription"] for s in saisies if s.get("prescription")}
        if identifiants and not user.has_perm("optique.view_prescription"):
            raise PermissionDenied("Pas d'accès aux ordonnances.")
        ordonnances = Prescription.objects.filter(public_id__in=identifiants).in_bulk(
            field_name="public_id"
        )
        if len(ordonnances) != len(identifiants):
            raise ValidationError({"detail": "Ordonnance inconnue."})
        return [{**s, "prescription": ordonnances.get(s.get("prescription"))} for s in saisies]


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
