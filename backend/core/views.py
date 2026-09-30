from django.core.cache import cache
from django.db import connection
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


def _verifier(fonction):
    try:
        fonction()
        return "ok"
    except Exception:
        return "indisponible"


def _base_de_donnees():
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")


def _cache():
    cache.set("sante", "ok", 5)


_ETAT_SANTE = inline_serializer(
    "EtatSante",
    fields={
        "statut": serializers.ChoiceField(choices=["ok", "degrade"]),
        "base_de_donnees": serializers.CharField(help_text="ok ou indisponible"),
        "cache": serializers.CharField(help_text="ok ou indisponible"),
    },
)


@extend_schema(auth=[], responses={200: _ETAT_SANTE, 503: _ETAT_SANTE})
@api_view(["GET"])
@permission_classes([AllowAny])
def sante(request):
    """État des dépendances, utilisé par Docker, Nginx et la supervision."""
    composants = {"base_de_donnees": _verifier(_base_de_donnees), "cache": _verifier(_cache)}
    ok = all(etat == "ok" for etat in composants.values())
    return Response({"statut": "ok" if ok else "degrade", **composants}, status=200 if ok else 503)
