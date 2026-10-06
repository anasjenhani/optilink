import uuid

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.reseau.models import Magasin

from .. import remunerations, services
from ..models import Acompte, DemandeConge, Employe, Pointage, Prime
from .serializers import (
    AcomptePourSerializer,
    AcompteSaisieSerializer,
    AcompteSerializer,
    CongeSerializer,
    DecisionSerializer,
    DemandePourSerializer,
    DemandeSaisieSerializer,
    EmployeSerializer,
    FeuillePresenceSerializer,
    MonEspaceSerializer,
    PresenceSaisieSerializer,
    PrimeSaisieSerializer,
    PrimeSerializer,
    RecapSerializer,
    VersementSerializer,
)


def _executer(fonction, *args, **kwargs):
    try:
        return fonction(*args, **kwargs)
    except (services.CongeImpossible, remunerations.OperationImpossible) as erreur:
        raise ValidationError({"detail": str(erreur)}) from erreur


def exiger(request, permission, magasin):
    if not request.user.has_perm(permission, magasin):
        raise PermissionDenied("Vous n'avez pas ce droit dans ce magasin.")


def magasin_autorise(request, public_id, permission):
    try:
        public_id = uuid.UUID(str(public_id))
    except ValueError as erreur:
        raise ValidationError({"magasin": "Identifiant de magasin invalide."}) from erreur
    magasin = get_object_or_404(Magasin.objects, public_id=public_id)
    exiger(request, permission, magasin)
    return magasin


class EmployeViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Fiches du personnel, avec le solde de congés de chacun."""

    serializer_class = EmployeSerializer
    lookup_field = "public_id"
    pagination_class = None
    http_method_names = ["get", "post", "patch"]
    filterset_fields = ["magasin__public_id"]
    permissions_requises = {
        "list": "rh.view_employe",
        "retrieve": "rh.view_employe",
        "create": "rh.add_employe",
        "partial_update": "rh.change_employe",
    }

    def get_queryset(self):
        employes = Employe.objects.select_related("magasin", "utilisateur")
        if self.request.query_params.get("actifs") == "true":
            employes = employes.filter(date_sortie__isnull=True)
        return employes

    def perform_create(self, serializer):
        exiger(self.request, "rh.add_employe", serializer.validated_data["magasin"])
        serializer.save()

    def perform_update(self, serializer):
        nouveau = serializer.validated_data.get("magasin", serializer.instance.magasin)
        exiger(self.request, "rh.change_employe", nouveau)
        serializer.save()


def feuille(magasin, jour):
    """Employés présents dans l'effectif ce jour-là, avec leur pointage ou leur congé."""
    employes = list(
        Employe.objects.filter(magasin=magasin, date_embauche__lte=jour).exclude(
            date_sortie__lt=jour
        )
    )
    pointages = {p.employe_id: p for p in Pointage.objects.filter(employe__in=employes, date=jour)}
    conges = services.en_conge(employes, jour)
    lignes = [
        {
            "employe": e,
            "pointage": pointages.get(e.pk),
            "conge": conges[e.pk].get_type_display() if e.pk in conges else None,
        }
        for e in employes
    ]
    return FeuillePresenceSerializer(lignes, many=True).data


class PresenceViewSet(viewsets.GenericViewSet):
    """Feuille de présence d'un magasin pour un jour."""

    serializer_class = FeuillePresenceSerializer
    pagination_class = None
    permissions_requises = {"list": "rh.view_pointage", "create": "rh.add_pointage"}

    def get_queryset(self):
        return Pointage.objects.none()

    @extend_schema(
        parameters=[
            OpenApiParameter("magasin", OpenApiTypes.UUID, required=True),
            OpenApiParameter("date", OpenApiTypes.DATE),
        ],
        responses=FeuillePresenceSerializer(many=True),
    )
    def list(self, request):
        magasin = magasin_autorise(request, request.query_params.get("magasin"), "rh.view_pointage")
        jour = request.query_params.get("date") or timezone.localdate().isoformat()
        try:
            jour = timezone.datetime.fromisoformat(jour).date()
        except ValueError as erreur:
            raise ValidationError({"date": "Date invalide."}) from erreur
        return Response(feuille(magasin, jour))

    @extend_schema(request=PresenceSaisieSerializer, responses=FeuillePresenceSerializer(many=True))
    @transaction.atomic
    def create(self, request):
        saisie = PresenceSaisieSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        d = saisie.validated_data
        magasin = magasin_autorise(request, d["magasin"], "rh.add_pointage")
        if d["date"] > timezone.localdate():
            raise ValidationError({"date": "On ne pointe pas un jour à venir."})
        employes = {
            e.public_id: e
            for e in Employe.objects.filter(
                magasin=magasin, public_id__in=[ligne["employe"] for ligne in d["lignes"]]
            )
        }
        conges = services.en_conge(employes.values(), d["date"])
        for ligne in d["lignes"]:
            employe = employes.get(ligne["employe"])
            if employe is None:
                raise ValidationError({"lignes": "Employé introuvable dans ce magasin."})
            if employe.pk in conges:
                raise ValidationError({"lignes": f"{employe} est en congé ce jour-là."})
            Pointage.objects.update_or_create(
                employe=employe,
                date=d["date"],
                defaults={
                    "magasin": magasin,
                    "statut": ligne["statut"],
                    "arrivee": ligne["arrivee"],
                    "depart": ligne["depart"],
                    "commentaire": ligne["commentaire"],
                    "saisi_par": request.user,
                },
            )
        return Response(feuille(magasin, d["date"]))


class CongeViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Demandes de congé des employés et décision du responsable."""

    serializer_class = CongeSerializer
    lookup_field = "public_id"
    filterset_fields = ["statut", "type", "employe__public_id", "magasin__public_id"]
    permissions_requises = {
        "list": "rh.view_demandeconge",
        "retrieve": "rh.view_demandeconge",
        "create": "rh.add_demandeconge",
        "annuler": "rh.add_demandeconge",
        "accepter": "rh.decider_demandeconge",
        "refuser": "rh.decider_demandeconge",
    }

    def get_queryset(self):
        return DemandeConge.objects.select_related(
            "employe", "magasin", "demandee_par", "decidee_par"
        )

    @extend_schema(request=DemandePourSerializer, responses={201: CongeSerializer})
    def create(self, request):
        """Saisit une demande pour un employé du magasin."""
        saisie = DemandePourSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        d = dict(saisie.validated_data)
        employe = Employe.objects.filter(public_id=d.pop("employe")).first()
        if employe is None:
            raise ValidationError({"employe": "Employé introuvable."})
        exiger(request, "rh.add_demandeconge", employe.magasin)
        demande = _executer(
            services.demander, employe, request.user, d["type"], d["debut"], d["fin"], d["motif"]
        )
        return Response(CongeSerializer(demande).data, status=status.HTTP_201_CREATED)

    def _decider(self, request, accepter):
        demande = self.get_object()
        saisie = DecisionSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        demande = _executer(
            services.decider, demande, request.user, accepter, saisie.validated_data["commentaire"]
        )
        return Response(CongeSerializer(demande).data)

    @extend_schema(request=DecisionSerializer, responses=CongeSerializer)
    @action(detail=True, methods=["post"])
    def accepter(self, request, public_id=None):
        return self._decider(request, accepter=True)

    @extend_schema(request=DecisionSerializer, responses=CongeSerializer)
    @action(detail=True, methods=["post"])
    def refuser(self, request, public_id=None):
        return self._decider(request, accepter=False)

    @extend_schema(request=None, responses=CongeSerializer)
    @action(detail=True, methods=["post"])
    def annuler(self, request, public_id=None):
        return Response(CongeSerializer(_executer(services.annuler, self.get_object())).data)


class MonEspaceViewSet(viewsets.GenericViewSet):
    """L'employé connecté : son solde, ses demandes, une nouvelle demande."""

    serializer_class = MonEspaceSerializer
    pagination_class = None
    # Chacun voit ses propres congés : aucun privilège n'est exigé.
    permissions_requises = {
        "list": [],
        "demander": [],
        "annuler": [],
        "demander_acompte": [],
        "annuler_acompte": [],
    }

    def get_queryset(self):
        return Employe.objects.none()

    def _employe(self):
        employe = Employe.tous.select_related("magasin").filter(utilisateur=self.request.user)
        employe = employe.first()
        if employe is None:
            raise NotFound("Votre compte n'est relié à aucune fiche employé.")
        return employe

    def _espace(self, employe):
        conges = DemandeConge.tous.filter(employe=employe).select_related(
            "employe", "magasin", "demandee_par", "decidee_par"
        )
        acomptes = Acompte.tous.filter(employe=employe).select_related(
            "employe", "magasin", "demande_par", "decide_par"
        )
        primes = Prime.tous.filter(employe=employe, statut=Prime.Statut.VALIDEE).select_related(
            "employe", "magasin", "proposee_par", "validee_par"
        )
        return MonEspaceSerializer(
            {"employe": employe, "conges": conges, "acomptes": acomptes, "primes": primes}
        ).data

    @extend_schema(responses=MonEspaceSerializer)
    def list(self, request):
        return Response(self._espace(self._employe()))

    @extend_schema(request=DemandeSaisieSerializer, responses={201: MonEspaceSerializer})
    @action(detail=False, methods=["post"])
    def demander(self, request):
        employe = self._employe()
        saisie = DemandeSaisieSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        d = saisie.validated_data
        _executer(
            services.demander, employe, request.user, d["type"], d["debut"], d["fin"], d["motif"]
        )
        return Response(self._espace(employe), status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses=MonEspaceSerializer)
    @action(detail=True, methods=["post"])
    def annuler(self, request, pk=None):
        employe = self._employe()
        try:
            demande = DemandeConge.tous.get(employe=employe, public_id=uuid.UUID(str(pk)))
        except (ValueError, DemandeConge.DoesNotExist) as erreur:
            raise NotFound("Demande introuvable.") from erreur
        _executer(services.annuler, demande)
        return Response(self._espace(employe))

    @extend_schema(request=AcompteSaisieSerializer, responses={201: MonEspaceSerializer})
    @action(detail=False, methods=["post"], url_path="demander-acompte")
    def demander_acompte(self, request):
        employe = self._employe()
        saisie = AcompteSaisieSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        d = saisie.validated_data
        _executer(
            remunerations.demander_acompte,
            employe,
            request.user,
            d["montant"],
            d["mois"],
            d["motif"],
        )
        return Response(self._espace(employe), status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses=MonEspaceSerializer)
    @action(detail=True, methods=["post"], url_path="annuler-acompte")
    def annuler_acompte(self, request, pk=None):
        """Retire sa propre demande d'acompte tant que les RH n'ont pas décidé."""
        employe = self._employe()
        try:
            acompte = Acompte.tous.get(employe=employe, public_id=uuid.UUID(str(pk)))
        except (ValueError, Acompte.DoesNotExist) as erreur:
            raise NotFound("Acompte introuvable.") from erreur
        _executer(remunerations.annuler_acompte, acompte, par_l_employe=True)
        return Response(self._espace(employe))


def _employe_autorise(request, public_id, permission):
    employe = Employe.objects.select_related("magasin").filter(public_id=public_id).first()
    if employe is None:
        raise ValidationError({"employe": "Employé introuvable."})
    exiger(request, permission, employe.magasin)
    return employe


class AcompteViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Avances sur salaire : demande, accord des RH, versement, retenue sur la paie."""

    serializer_class = AcompteSerializer
    lookup_field = "public_id"
    filterset_fields = ["statut", "mois", "employe__public_id", "magasin__public_id"]
    permissions_requises = {
        "list": "rh.view_acompte",
        "retrieve": "rh.view_acompte",
        "create": "rh.add_acompte",
        "annuler": "rh.add_acompte",
        "accorder": "rh.decider_acompte",
        "refuser": "rh.decider_acompte",
        "verser": "rh.decider_acompte",
    }

    def get_queryset(self):
        return Acompte.objects.select_related("employe", "magasin", "demande_par", "decide_par")

    @extend_schema(request=AcomptePourSerializer, responses={201: AcompteSerializer})
    def create(self, request):
        saisie = AcomptePourSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        d = saisie.validated_data
        employe = _employe_autorise(request, d["employe"], "rh.add_acompte")
        acompte = _executer(
            remunerations.demander_acompte,
            employe,
            request.user,
            d["montant"],
            d["mois"],
            d["motif"],
        )
        return Response(AcompteSerializer(acompte).data, status=status.HTTP_201_CREATED)

    def _decider(self, request, accorder):
        saisie = DecisionSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        acompte = _executer(
            remunerations.decider_acompte,
            self.get_object(),
            request.user,
            accorder,
            saisie.validated_data["commentaire"],
        )
        return Response(AcompteSerializer(acompte).data)

    @extend_schema(request=DecisionSerializer, responses=AcompteSerializer)
    @action(detail=True, methods=["post"])
    def accorder(self, request, public_id=None):
        return self._decider(request, accorder=True)

    @extend_schema(request=DecisionSerializer, responses=AcompteSerializer)
    @action(detail=True, methods=["post"])
    def refuser(self, request, public_id=None):
        return self._decider(request, accorder=False)

    @extend_schema(request=VersementSerializer, responses=AcompteSerializer)
    @action(detail=True, methods=["post"])
    def verser(self, request, public_id=None):
        saisie = VersementSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        d = saisie.validated_data
        acompte = _executer(
            remunerations.verser_acompte, self.get_object(), d["mode"], d["reference"], d["date"]
        )
        return Response(AcompteSerializer(acompte).data)

    @extend_schema(request=None, responses=AcompteSerializer)
    @action(detail=True, methods=["post"])
    def annuler(self, request, public_id=None):
        acompte = _executer(remunerations.annuler_acompte, self.get_object())
        return Response(AcompteSerializer(acompte).data)


class PrimeViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Primes : proposées par le responsable, validées par les RH."""

    serializer_class = PrimeSerializer
    lookup_field = "public_id"
    filterset_fields = ["statut", "mois", "type", "employe__public_id", "magasin__public_id"]
    permissions_requises = {
        "list": "rh.view_prime",
        "retrieve": "rh.view_prime",
        "create": "rh.add_prime",
        "annuler": "rh.add_prime",
        "valider": "rh.valider_prime",
        "refuser": "rh.valider_prime",
    }

    def get_queryset(self):
        return Prime.objects.select_related("employe", "magasin", "proposee_par", "validee_par")

    @extend_schema(request=PrimeSaisieSerializer, responses={201: PrimeSerializer})
    def create(self, request):
        saisie = PrimeSaisieSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        d = saisie.validated_data
        employe = _employe_autorise(request, d["employe"], "rh.add_prime")
        prime = _executer(
            remunerations.proposer_prime,
            employe,
            request.user,
            d["type"],
            d["montant"],
            d["mois"],
            d["motif"],
        )
        return Response(PrimeSerializer(prime).data, status=status.HTTP_201_CREATED)

    def _decider(self, request, valider):
        saisie = DecisionSerializer(data=request.data)
        saisie.is_valid(raise_exception=True)
        prime = _executer(
            remunerations.decider_prime,
            self.get_object(),
            request.user,
            valider,
            saisie.validated_data["commentaire"],
        )
        return Response(PrimeSerializer(prime).data)

    @extend_schema(request=DecisionSerializer, responses=PrimeSerializer)
    @action(detail=True, methods=["post"])
    def valider(self, request, public_id=None):
        return self._decider(request, valider=True)

    @extend_schema(request=DecisionSerializer, responses=PrimeSerializer)
    @action(detail=True, methods=["post"])
    def refuser(self, request, public_id=None):
        return self._decider(request, valider=False)

    @extend_schema(request=None, responses=PrimeSerializer)
    @action(detail=True, methods=["post"])
    def annuler(self, request, public_id=None):
        return Response(
            PrimeSerializer(_executer(remunerations.annuler_prime, self.get_object())).data
        )


class RecapViewSet(viewsets.GenericViewSet):
    """Récapitulatif du mois pour la paie : acomptes à retenir et primes à verser."""

    serializer_class = RecapSerializer
    pagination_class = None
    permissions_requises = {"list": ["rh.view_acompte", "rh.view_prime"]}

    def get_queryset(self):
        return Employe.objects.none()

    @extend_schema(
        parameters=[OpenApiParameter("mois", OpenApiTypes.DATE, description="Un jour du mois.")],
        responses=RecapSerializer(many=True),
    )
    def list(self, request):
        texte = request.query_params.get("mois") or timezone.localdate().isoformat()
        try:
            mois = remunerations.premier_du_mois(timezone.datetime.fromisoformat(texte).date())
        except ValueError as erreur:
            raise ValidationError({"mois": "Date invalide."}) from erreur
        employes = (
            Employe.objects.select_related("magasin")
            .filter(date_embauche__lt=(mois + timezone.timedelta(days=32)).replace(day=1))
            .exclude(date_sortie__lt=mois)
        )
        return Response(
            RecapSerializer(remunerations.recapitulatif(employes, mois), many=True).data
        )
