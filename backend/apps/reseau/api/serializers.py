from rest_framework import serializers

from ..models import Magasin, Pays, Societe


class PaysSerializer(serializers.ModelSerializer):
    taux_tva = serializers.SlugRelatedField(
        slug_field="taux", many=True, read_only=True, help_text="Taux de TVA du pays."
    )

    class Meta:
        model = Pays
        fields = [
            "code_numerique",
            "code",
            "nom",
            "devise",
            "decimales",
            "indicatif_telephonique",
            "timbre_fiscal",
            "libelle_identifiant_prescripteur",
            "taux_tva",
        ]


class MagasinSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    societe = serializers.CharField(source="societe.raison_sociale", read_only=True)
    societe_id = serializers.UUIDField(source="societe.public_id", read_only=True)
    pays = PaysSerializer(read_only=True)

    class Meta:
        model = Magasin
        fields = [
            "id",
            "code",
            "nom",
            "societe",
            "societe_id",
            "pays",
            "adresse",
            "code_postal",
            "ville",
            "telephone",
            "nombre_peniches",
            "est_actif",
        ]


class SocieteSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)

    class Meta:
        model = Societe
        fields = ["id", "code", "raison_sociale"]
