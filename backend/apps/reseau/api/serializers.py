from rest_framework import serializers

from ..models import Magasin


class MagasinSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    region = serializers.CharField(source="region.nom", read_only=True)

    class Meta:
        model = Magasin
        fields = [
            "id",
            "code",
            "nom",
            "region",
            "adresse",
            "code_postal",
            "ville",
            "telephone",
            "est_actif",
        ]
