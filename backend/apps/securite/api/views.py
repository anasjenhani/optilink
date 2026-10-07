import base64
import io

from django.contrib.auth import authenticate, login, logout
from django.db import transaction
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django_otp import login as otp_login
from django_otp import match_token, user_has_device
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_otp.qr import write_qrcode_image
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.permissions import mfa_requise, mfa_verifiee

from ..journal import journaliser
from ..models import EvenementSecurite
from .serializers import (
    ActivationMfaSerializer,
    CodeSerializer,
    ConfirmationMfaSerializer,
    ConnexionSerializer,
    EtatSessionSerializer,
)

NOMBRE_CODES_SECOURS = 10
NOM_APPLICATION = "Application d'authentification"
NOM_CODES_SECOURS = "Codes de secours"


def etat_mfa(user):
    if mfa_verifiee(user):
        return "verifiee"
    if not mfa_requise(user):
        return "non_requise"
    return "a_verifier" if user_has_device(user) else "a_activer"


def etat_session(request):
    user = request.user
    if not user.is_authenticated:
        return {"authentifie": False, "mfa": None, "utilisateur": None}
    mfa = etat_mfa(user)
    acces_ouvert = mfa in ("verifiee", "non_requise")
    return {
        "authentifie": True,
        "mfa": mfa,
        "utilisateur": {
            "identifiant": user.get_username(),
            "nom_complet": user.get_full_name() or user.get_username(),
            # Les droits ne sont communiqués qu'une fois le second facteur validé.
            "permissions": sorted(user.get_all_permissions()) if acces_ouvert else [],
        },
    }


def verifier_csrf(request):
    """Le contrôle CSRF de DRF ne s'applique qu'aux sessions ouvertes : on l'impose ici aussi."""
    SessionAuthentication().enforce_csrf(request)


class SessionView(APIView):
    """État de la session ; pose aussi le cookie CSRF utilisé par le frontend."""

    permission_classes = [AllowAny]

    @extend_schema(responses=EtatSessionSerializer, auth=[])
    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        return Response(etat_session(request))


class ConnexionView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "connexion"

    @extend_schema(request=ConnexionSerializer, responses=EtatSessionSerializer, auth=[])
    def post(self, request):
        verifier_csrf(request)
        donnees = ConnexionSerializer(data=request.data)
        donnees.is_valid(raise_exception=True)
        user = authenticate(
            request,
            username=donnees.validated_data["identifiant"],
            password=donnees.validated_data["mot_de_passe"],
        )
        if user is None:
            return Response(
                {"detail": "Identifiant ou mot de passe incorrect."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        login(request, user)
        return Response(etat_session(request))


class DeconnexionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class VerificationMfaView(APIView):
    """Second facteur : code de l'application d'authentification ou code de secours."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "mfa"

    @extend_schema(request=CodeSerializer, responses=EtatSessionSerializer)
    def post(self, request):
        donnees = CodeSerializer(data=request.data)
        donnees.is_valid(raise_exception=True)
        device = match_token(request.user, donnees.validated_data["code"].replace(" ", ""))
        if device is None:
            journaliser(EvenementSecurite.Type.MFA_ECHOUEE, request, request.user)
            return Response({"detail": "Code incorrect."}, status=status.HTTP_400_BAD_REQUEST)
        otp_login(request, device)
        details = "code de secours" if isinstance(device, StaticDevice) else ""
        journaliser(EvenementSecurite.Type.MFA_REUSSIE, request, request.user, details=details)
        return Response(etat_session(request))


class ActivationMfaView(APIView):
    """Prépare une nouvelle application d'authentification, à confirmer par un premier code.

    Possible à la première connexion, ou pour remplacer son téléphone une fois déjà vérifié.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses=ActivationMfaSerializer)
    def post(self, request):
        user = request.user
        if user_has_device(user) and not mfa_verifiee(user):
            return Response(
                {"detail": "Validez d'abord votre code actuel pour changer d'application."},
                status=status.HTTP_403_FORBIDDEN,
            )
        TOTPDevice.objects.filter(user=user, confirmed=False).delete()
        device = TOTPDevice.objects.create(user=user, name=NOM_APPLICATION, confirmed=False)
        svg = io.BytesIO()
        write_qrcode_image(device.config_url, svg)
        return Response(
            {
                "uri": device.config_url,
                "cle": base64.b32encode(device.bin_key).decode(),
                "qr_svg": svg.getvalue().decode(),
            }
        )


class ConfirmationMfaView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "mfa"

    @extend_schema(request=CodeSerializer, responses=ConfirmationMfaSerializer)
    def post(self, request):
        user = request.user
        if user_has_device(user) and not mfa_verifiee(user):
            return Response(
                {"detail": "Validez d'abord votre code actuel pour changer d'application."},
                status=status.HTTP_403_FORBIDDEN,
            )
        donnees = CodeSerializer(data=request.data)
        donnees.is_valid(raise_exception=True)
        device = TOTPDevice.objects.filter(user=user, confirmed=False).last()
        if device is None:
            return Response(
                {"detail": "Aucune activation en cours."}, status=status.HTTP_400_BAD_REQUEST
            )
        if not device.verify_token(donnees.validated_data["code"].replace(" ", "")):
            journaliser(EvenementSecurite.Type.MFA_ECHOUEE, request, user, details="activation")
            return Response({"detail": "Code incorrect."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            TOTPDevice.objects.filter(user=user, confirmed=True).delete()
            device.confirmed = True
            device.save(update_fields=["confirmed"])
            StaticDevice.objects.filter(user=user).delete()
            secours = StaticDevice.objects.create(user=user, name=NOM_CODES_SECOURS)
            codes = [StaticToken.random_token() for _ in range(NOMBRE_CODES_SECOURS)]
            StaticToken.objects.bulk_create(
                [StaticToken(device=secours, token=code) for code in codes]
            )
        otp_login(request, device)
        journaliser(EvenementSecurite.Type.MFA_ACTIVEE, request, user)
        return Response({"codes_secours": codes, "session": etat_session(request)})
