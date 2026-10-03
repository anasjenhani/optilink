from datetime import date

from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .. import reporting
from ..alertes import alertes, magasins_couverts
from .serializers import AlerteSerializer, SectionReportingSerializer


class AlerteViewSet(viewsets.ViewSet):
    """Alertes du jour ; chacun ne voit que celles de ses droits et de ses magasins."""

    permissions_requises = {"list": []}

    @extend_schema(responses=AlerteSerializer(many=True))
    def list(self, request):
        return Response(AlerteSerializer(alertes(request.user), many=True).data)


def _date(texte, defaut):
    if not texte:
        return defaut
    try:
        return date.fromisoformat(texte)
    except ValueError as erreur:
        raise ValidationError({"detail": f"Date invalide : {texte}."}) from erreur


class ReportingViewSet(viewsets.ViewSet):
    """Chiffre d'affaires et ventes de la période, une section par monnaie."""

    permissions_requises = {"list": ["ventes.consulter_reporting"]}

    @extend_schema(
        parameters=[
            OpenApiParameter("du", OpenApiTypes.DATE, description="Début (1er du mois par défaut)"),
            OpenApiParameter("au", OpenApiTypes.DATE, description="Fin incluse (aujourd'hui)"),
            OpenApiParameter("magasin", OpenApiTypes.UUID, description="Un seul magasin"),
        ],
        responses=SectionReportingSerializer(many=True),
    )
    def list(self, request):
        aujourdhui = timezone.localdate()
        du = _date(request.query_params.get("du"), aujourdhui.replace(day=1))
        au = _date(request.query_params.get("au"), aujourdhui)
        if du > au:
            raise ValidationError({"detail": "La date de début est après la date de fin."})
        magasins = magasins_couverts(request.user, "ventes.consulter_reporting")
        choisi = request.query_params.get("magasin")
        selection = [m for m in magasins.values() if not choisi or str(m.public_id) == choisi]
        sections = reporting.rapport(selection, du, au)
        return Response(SectionReportingSerializer(sections, many=True).data)
