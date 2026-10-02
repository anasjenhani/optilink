from rest_framework import serializers

from ..models import Magasin, Pays


class PaysSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pays
        fields = [
            "code",
            "nom",
            "devise",
            "decimales",
            "indicatif_telephonique",
            "timbre_fiscal",
            "libelle_identifiant_prescripteur",
        ]


class MagasinSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    region = serializers.CharField(source="region.nom", read_only=True)
    pays = PaysSerializer(read_only=True)

    class Meta:
        model = Magasin
        fields = [
            "id",
            "code",
            "nom",
            "region",
            "pays",
            "adresse",
            "code_postal",
            "ville",
            "telephone",
            "nombre_peniches",
            "est_actif",
        ]
