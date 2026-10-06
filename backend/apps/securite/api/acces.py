"""Accès et sécurité : utilisateurs, profils et privilèges, gérés depuis l'application.

Garde-fous contre l'élévation de droits : un administrateur ne transmet un privilège
d'administration que s'il le détient lui-même, n'agit que sur les magasins qu'il voit, et ne
peut changer ni ses propres profils ni les privilèges d'un profil qui lui est donné.
"""

from django.contrib.auth.models import Group, Permission
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from django_otp.plugins.otp_static.models import StaticDevice
from django_otp.plugins.otp_totp.models import TOTPDevice
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.reseau.models import Magasin, Societe

from ..corbeille import mettre_a_la_corbeille
from ..models import Affectation, Utilisateur
from ..privileges import ADMINISTRATION, CODES, PRIVILEGES


def _codes(permissions):
    return {f"{p.content_type.app_label}.{p.codename}" for p in permissions}


def _permissions_du_catalogue(codes):
    filtre = Q()
    for code in codes:
        app_label, codename = code.split(".")
        filtre |= Q(content_type__app_label=app_label, codename=codename)
    return list(Permission.objects.filter(filtre)) if codes else []


def verifier_privileges(demandeur, codes):
    """Refuse si le demandeur transmet ou retire un privilège d'administration qu'il n'a pas."""
    if demandeur.is_superuser:
        return
    manquants = set(codes) & ADMINISTRATION - demandeur.get_all_permissions()
    if manquants:
        libelles = sorted(_libelle(code) for code in manquants)
        raise PermissionDenied(
            "Vous ne pouvez pas donner ou retirer un privilège d'administration "
            "que vous n'avez pas : " + ", ".join(libelles) + "."
        )


def _libelle(code):
    for module in PRIVILEGES.values():
        if code in module:
            return module[code]
    return code


def verifier_perimetre(demandeur, portee, magasin, societe):
    """Refuse un périmètre plus large que celui du demandeur."""
    autorises = demandeur.magasins_autorises()
    if autorises is None:
        return
    if portee == Affectation.Portee.RESEAU:
        raise PermissionDenied("Seul un administrateur de tout le réseau peut donner cette portée.")
    if portee == Affectation.Portee.MAGASIN:
        couverts = {magasin.pk}
    else:
        couverts = set(Magasin.tous.filter(societe=societe).values_list("pk", flat=True))
    if not couverts or not couverts <= autorises:
        raise PermissionDenied("Ce magasin ou cette société est hors de votre périmètre.")


def verifier_affectation(demandeur, affectation):
    verifier_privileges(demandeur, _codes(affectation.role.permissions.all()))
    verifier_perimetre(demandeur, affectation.portee, affectation.magasin, affectation.societe)


# --- Profils et privilèges -------------------------------------------------------------------


class PrivilegeSerializer(serializers.Serializer):
    code = serializers.CharField()
    libelle = serializers.CharField()


class ModulePrivilegesSerializer(serializers.Serializer):
    module = serializers.CharField()
    privileges = PrivilegeSerializer(many=True)


class PrivilegesView(APIView):
    """Catalogue des privilèges, regroupés par module."""

    permissions_requises = {"get": "auth.view_group"}

    @extend_schema(responses=ModulePrivilegesSerializer(many=True))
    def get(self, request):
        return Response(
            [
                {
                    "module": module,
                    "privileges": [
                        {"code": code, "libelle": libelle} for code, libelle in privileges.items()
                    ],
                }
                for module, privileges in PRIVILEGES.items()
            ]
        )


class ProfilSerializer(serializers.ModelSerializer):
    nom = serializers.CharField(source="name", max_length=150)
    privileges = serializers.ListField(
        child=serializers.CharField(), required=False, write_only=True
    )
    utilisateurs = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Group
        fields = ["id", "nom", "privileges", "utilisateurs"]

    def to_representation(self, profil):
        donnees = super().to_representation(profil)
        donnees["privileges"] = sorted(_codes(profil.permissions.all()) & CODES)
        return donnees

    def validate_nom(self, nom):
        autres = Group.objects.exclude(pk=getattr(self.instance, "pk", None))
        if autres.filter(name__iexact=nom.strip()).exists():
            raise ValidationError("Un profil porte déjà ce nom.")
        return nom.strip()

    def validate_privileges(self, codes):
        inconnus = set(codes) - CODES
        if inconnus:
            raise ValidationError(f"Privilèges inconnus : {', '.join(sorted(inconnus))}.")
        return set(codes)

    @transaction.atomic
    def save(self, **kwargs):
        codes = self.validated_data.pop("privileges", None)
        demandeur = self.context["request"].user
        if (
            self.instance is not None
            and not demandeur.is_superuser
            and demandeur.affectations_actives().filter(role=self.instance).exists()
        ):
            raise PermissionDenied("Vous ne pouvez pas modifier un profil qui vous est donné.")
        avant = set() if self.instance is None else _codes(self.instance.permissions.all())
        if codes is not None:
            verifier_privileges(demandeur, codes ^ (avant & CODES))
        profil = super().save(**kwargs)
        if codes is not None:
            hors_catalogue = [p for p in profil.permissions.all() if _codes([p]).isdisjoint(CODES)]
            profil.permissions.set(hors_catalogue + _permissions_du_catalogue(codes))
        return profil


class ProfilViewSet(viewsets.ModelViewSet):
    """Profils (rôles) et leurs privilèges."""

    serializer_class = ProfilSerializer
    pagination_class = None
    http_method_names = ["get", "post", "patch", "delete"]

    def get_queryset(self):
        jour = timezone.localdate()
        en_cours = Q(affectations__debut__lte=jour) & (
            Q(affectations__fin__isnull=True) | Q(affectations__fin__gte=jour)
        )
        return (
            Group.objects.annotate(
                utilisateurs=Count("affectations__utilisateur", filter=en_cours, distinct=True)
            )
            .prefetch_related("permissions__content_type")
            .order_by("name")
        )

    def perform_destroy(self, profil):
        if profil.affectations.exists():
            raise ValidationError(
                {"detail": "Ce profil est donné à des utilisateurs : retirez-le-leur d'abord."}
            )
        verifier_privileges(self.request.user, _codes(profil.permissions.all()) & CODES)
        mettre_a_la_corbeille(profil, auteur=self.request.user)


# --- Utilisateurs ----------------------------------------------------------------------------


class AffectationSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    profil = serializers.PrimaryKeyRelatedField(source="role", queryset=Group.objects.all())
    profil_nom = serializers.CharField(source="role.name", read_only=True)
    magasin = serializers.SlugRelatedField(
        slug_field="public_id",
        queryset=Magasin.tous.all(),
        required=False,
        allow_null=True,
    )
    societe = serializers.SlugRelatedField(
        slug_field="public_id", queryset=Societe.objects.all(), required=False, allow_null=True
    )
    perimetre = serializers.SerializerMethodField()

    class Meta:
        model = Affectation
        fields = [
            "id",
            "profil",
            "profil_nom",
            "portee",
            "magasin",
            "societe",
            "perimetre",
            "debut",
            "fin",
        ]

    def get_perimetre(self, affectation) -> str:
        return str(affectation.magasin or affectation.societe or "Tout le réseau")

    def validate(self, attrs):
        affectation = Affectation(
            portee=attrs["portee"],
            magasin=attrs.get("magasin"),
            societe=attrs.get("societe"),
            debut=attrs.get("debut") or timezone.localdate(),
            fin=attrs.get("fin"),
        )
        try:
            affectation.clean()
        except DjangoValidationError as erreur:
            raise ValidationError(erreur.messages) from erreur
        return attrs


class UtilisateurSerializer(serializers.ModelSerializer):
    identifiant = serializers.CharField(source="username", max_length=150)
    prenom = serializers.CharField(source="first_name", max_length=150, required=False)
    nom = serializers.CharField(source="last_name", max_length=150, required=False)
    actif = serializers.BooleanField(source="is_active", required=False)
    mot_de_passe = serializers.CharField(
        write_only=True, required=False, trim_whitespace=False, max_length=128
    )
    derniere_connexion = serializers.DateTimeField(source="last_login", read_only=True)
    mfa_active = serializers.SerializerMethodField()
    administrateur_technique = serializers.BooleanField(source="is_superuser", read_only=True)
    affectations = AffectationSerializer(many=True, required=False)

    class Meta:
        model = Utilisateur
        fields = [
            "id",
            "identifiant",
            "prenom",
            "nom",
            "email",
            "actif",
            "mot_de_passe",
            "derniere_connexion",
            "mfa_active",
            "administrateur_technique",
            "affectations",
        ]

    def get_mfa_active(self, utilisateur) -> bool:
        return TOTPDevice.objects.filter(user=utilisateur, confirmed=True).exists()

    def validate_identifiant(self, identifiant):
        autres = Utilisateur.objects.exclude(pk=getattr(self.instance, "pk", None))
        if autres.filter(username__iexact=identifiant).exists():
            raise ValidationError("Cet identifiant est déjà pris.")
        return identifiant

    def validate(self, attrs):
        if self.instance is None and not attrs.get("mot_de_passe"):
            raise ValidationError({"mot_de_passe": "Choisissez un mot de passe provisoire."})
        if attrs.get("mot_de_passe"):
            cible = self.instance or Utilisateur(
                username=attrs.get("username", ""),
                first_name=attrs.get("first_name", ""),
                last_name=attrs.get("last_name", ""),
                email=attrs.get("email", ""),
            )
            try:
                validate_password(attrs["mot_de_passe"], cible)
            except DjangoValidationError as erreur:
                raise ValidationError({"mot_de_passe": list(erreur.messages)}) from erreur
        return attrs

    @transaction.atomic
    def save(self, **kwargs):
        demandeur = self.context["request"].user
        affectations = self.validated_data.pop("affectations", None)
        mot_de_passe = self.validated_data.pop("mot_de_passe", None)
        if self.instance is not None:
            if self.instance.is_superuser and not demandeur.is_superuser:
                raise PermissionDenied("Ce compte technique ne se modifie que par lui-même.")
            if self.instance == demandeur and affectations is not None:
                raise PermissionDenied("Vous ne pouvez pas changer vos propres profils.")
            if self.instance == demandeur and self.validated_data.get("is_active") is False:
                raise PermissionDenied("Vous ne pouvez pas désactiver votre propre compte.")
        utilisateur = super().save(**kwargs)
        if mot_de_passe:
            # L'import chiffre les mots de passe d'avance (en parallèle) et ne les chiffre pas
            # du tout pour la vérification, annulée de toute façon : sinon le serveur coupe.
            chiffres = self.context.get("mots_de_passe_chiffres")
            if chiffres is None:
                utilisateur.set_password(mot_de_passe)
            elif mot_de_passe in chiffres:
                utilisateur.password = chiffres[mot_de_passe]
            else:
                utilisateur.set_unusable_password()
            utilisateur.save(update_fields=["password"])
        if affectations is not None:
            self._enregistrer_affectations(demandeur, utilisateur, affectations)
        return utilisateur

    def _enregistrer_affectations(self, demandeur, utilisateur, donnees):
        """Remplace les affectations par celles reçues : avec ``id`` modifiée, sans créée."""
        existantes = {a.pk: a for a in utilisateur.affectations.select_related("role")}
        recues = {d["id"] for d in donnees if d.get("id")}
        if recues - existantes.keys():
            raise ValidationError({"affectations": "Affectation inconnue pour cet utilisateur."})
        for pk in existantes.keys() - recues:
            verifier_affectation(demandeur, existantes[pk])
            existantes[pk].delete()
        for d in donnees:
            d = dict(d)
            pk = d.pop("id", None)
            nouvelle = Affectation(
                pk=pk,
                utilisateur=utilisateur,
                role=d["role"],
                portee=d["portee"],
                magasin=d.get("magasin"),
                societe=d.get("societe"),
                debut=d.get("debut") or timezone.localdate(),
                fin=d.get("fin"),
            )
            ancienne = existantes.get(pk)
            if ancienne is not None:
                if _etat(ancienne) == _etat(nouvelle):
                    continue
                # Changer une affectation, c'est retirer l'ancienne et donner la nouvelle.
                verifier_affectation(demandeur, ancienne)
            verifier_affectation(demandeur, nouvelle)
            nouvelle.save()


def _etat(affectation):
    return (
        affectation.role_id,
        affectation.portee,
        affectation.magasin_id,
        affectation.societe_id,
        affectation.debut,
        affectation.fin,
    )


class UtilisateurViewSet(viewsets.ModelViewSet):
    """Comptes des employés. Un compte se désactive, il ne se supprime pas."""

    serializer_class = UtilisateurSerializer
    pagination_class = None  # Quelques dizaines de comptes : tout s'affiche d'un coup.
    http_method_names = ["get", "post", "patch"]
    permissions_requises = {
        "list": "securite.view_utilisateur",
        "retrieve": "securite.view_utilisateur",
        "create": ["securite.add_utilisateur", "securite.add_affectation"],
        "partial_update": ["securite.change_utilisateur", "securite.change_affectation"],
        "reinitialiser_mfa": "securite.change_utilisateur",
    }

    def get_queryset(self):
        utilisateurs = Utilisateur.objects.prefetch_related(
            "affectations__role", "affectations__magasin", "affectations__societe"
        ).order_by("username")
        if getattr(self, "swagger_fake_view", False):
            return utilisateurs
        autorises = self.request.user.magasins_autorises()
        if autorises is None:
            return utilisateurs
        return utilisateurs.filter(
            Q(affectations__magasin__in=autorises)
            | Q(affectations__societe__magasins__in=autorises)
        ).distinct()

    @extend_schema(request=None, responses={204: None})
    @action(detail=True, methods=["post"], url_path="reinitialiser-mfa")
    def reinitialiser_mfa(self, request, pk=None):
        """Téléphone perdu : l'utilisateur réactivera la double authentification à sa connexion."""
        utilisateur = self.get_object()
        if utilisateur.is_superuser and not request.user.is_superuser:
            raise PermissionDenied("Ce compte technique ne se modifie que par lui-même.")
        TOTPDevice.objects.filter(user=utilisateur).delete()
        StaticDevice.objects.filter(user=utilisateur).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
