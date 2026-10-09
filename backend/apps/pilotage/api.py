from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.reseau.models import Magasin

from . import statistiques


class ColonneSerializer(serializers.Serializer):
    cle = serializers.CharField()
    libelle = serializers.CharField()
    type = serializers.ChoiceField(choices=["texte", "nombre", "montant", "pourcent", "date"])


class StatistiqueSerializer(serializers.Serializer):
    titre = serializers.CharField()
    devise = serializers.CharField()
    decimales = serializers.IntegerField()
    devises = serializers.ListField(child=serializers.CharField())
    du = serializers.DateField()
    au = serializers.DateField()
    colonnes = ColonneSerializer(many=True)
    lignes = serializers.ListField(child=serializers.DictField())
    totaux = serializers.DictField()


class FiltreSerializer(serializers.Serializer):
    du = serializers.DateField(required=False)
    au = serializers.DateField(required=False)
    magasin = serializers.UUIDField(required=False)
    devise = serializers.CharField(required=False, max_length=3)


def _texte(valeur):
    # Montants et taux en texte, comme partout dans l'API : pas d'arrondi flottant.
    return str(valeur) if not isinstance(valeur, (str, int)) else valeur


class StatistiqueViewSet(viewsets.ViewSet):
    """Statistiques des ventes : montures, verres, lentilles, remises, gratuits,
    ophtalmologues, TVA, bénéfice journalier."""

    permissions_requises = {"retrieve": "ventes.consulter_reporting"}
    lookup_value_regex = "|".join(statistiques.RAPPORTS)

    @extend_schema(
        parameters=[
            OpenApiParameter("du", OpenApiTypes.DATE, description="Par défaut : début du mois."),
            OpenApiParameter("au", OpenApiTypes.DATE, description="Par défaut : aujourd'hui."),
            OpenApiParameter("magasin", OpenApiTypes.UUID, description="Tous par défaut."),
            OpenApiParameter("devise", OpenApiTypes.STR),
        ],
        responses=StatistiqueSerializer,
    )
    def retrieve(self, request, pk=None):
        filtre = FiltreSerializer(data=request.query_params)
        filtre.is_valid(raise_exception=True)
        donnees = filtre.validated_data
        au = donnees.get("au") or timezone.localdate()
        du = donnees.get("du") or au.replace(day=1)
        if du > au:
            raise ValidationError({"du": "Le début est après la fin."})
        magasins = Magasin.objects.select_related("pays").order_by("code")
        if donnees.get("magasin"):
            magasins = magasins.filter(public_id=donnees["magasin"])
        # Le droit de consulter, magasin par magasin.
        magasins = [m for m in magasins if request.user.has_perm("ventes.consulter_reporting", m)]
        if not magasins:
            raise ValidationError({"magasin": "Aucun magasin à consulter."})
        devises = sorted({m.pays.devise for m in magasins})
        devise = donnees.get("devise") or devises[0]
        magasins = [m for m in magasins if m.pays.devise == devise]
        if not magasins:
            raise ValidationError({"devise": "Aucun magasin dans cette monnaie."})
        decimales = magasins[0].pays.decimales
        periode = statistiques.Periode(magasins, devise, decimales, du, au)
        resultat = statistiques.calculer(pk, periode)
        resultat["lignes"] = [
            {cle: _texte(v) for cle, v in ligne.items()} for ligne in resultat["lignes"]
        ]
        resultat["totaux"] = {cle: _texte(v) for cle, v in resultat["totaux"].items()}
        return Response(
            {
                **resultat,
                "devise": devise,
                "decimales": decimales,
                "devises": devises,
                "du": du,
                "au": au,
            }
        )
