import re
from decimal import Decimal

from rest_framework import serializers

from apps.crm.models import Client
from apps.reseau.models import Magasin

from ..models import Prescription

QUART = Decimal("0.25")


def dioptries(minimum, maximum, **kwargs):
    return serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal(minimum),
        max_value=Decimal(maximum),
        coerce_to_string=True,
        **kwargs,
    )


class MesureOeilSerializer(serializers.Serializer):
    sphere = dioptries("-30", "30")
    cylindre = dioptries("-10", "10", default=Decimal("0"))
    axe = serializers.IntegerField(min_value=0, max_value=180, required=False, allow_null=True)
    addition = dioptries("0", "4", required=False, allow_null=True)
    rayon = serializers.DecimalField(
        max_digits=4,
        decimal_places=2,
        min_value=Decimal("5"),
        max_value=Decimal("11"),
        required=False,
        allow_null=True,
        help_text="Lentilles : rayon de courbure (mm).",
    )
    diametre = serializers.DecimalField(
        max_digits=4,
        decimal_places=2,
        min_value=Decimal("8"),
        max_value=Decimal("17"),
        required=False,
        allow_null=True,
        help_text="Lentilles : diamètre (mm).",
    )

    def validate(self, attrs):
        for champ in ("sphere", "cylindre", "addition"):
            valeur = attrs.get(champ)
            if valeur is not None and valeur % QUART:
                raise serializers.ValidationError({champ: "Par pas de 0,25 dioptrie."})
        if attrs.get("cylindre") and attrs.get("axe") is None:
            raise serializers.ValidationError({"axe": "Obligatoire quand il y a un cylindre."})
        return attrs


class MesuresSerializer(serializers.Serializer):
    od = MesureOeilSerializer(help_text="Œil droit")
    og = MesureOeilSerializer(help_text="Œil gauche")
    ecart_pupillaire = serializers.DecimalField(
        max_digits=4,
        decimal_places=1,
        min_value=Decimal("40"),
        max_value=Decimal("80"),
        required=False,
        allow_null=True,
        help_text="Écart pupillaire de loin (mm).",
    )
    remarques = serializers.CharField(required=False, allow_blank=True, max_length=500)


class PrescriptionSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    client = serializers.SlugRelatedField(slug_field="public_id", queryset=Client.objects)
    magasin_saisie = serializers.SlugRelatedField(slug_field="public_id", queryset=Magasin.objects)
    saisie_par = serializers.SerializerMethodField()
    mesures = MesuresSerializer()

    class Meta:
        model = Prescription
        fields = [
            "id",
            "client",
            "type",
            "date_prescription",
            "prescripteur",
            "prescripteur_identifiant",
            "mesures",
            "magasin_saisie",
            "saisie_par",
            "cree_le",
        ]
        read_only_fields = ["cree_le"]

    def get_saisie_par(self, prescription) -> str:
        return prescription.saisie_par.get_full_name() or prescription.saisie_par.get_username()

    def validate(self, attrs):
        pays = attrs["magasin_saisie"].pays
        identifiant = attrs.get("prescripteur_identifiant", "")
        motif = pays.format_identifiant_prescripteur
        if identifiant and motif and not re.fullmatch(motif, identifiant):
            raise serializers.ValidationError(
                {"prescripteur_identifiant": f"{pays.libelle_identifiant_prescripteur} invalide."}
            )
        return attrs

    def validate_date_prescription(self, valeur):
        from django.utils import timezone

        if valeur > timezone.localdate():
            raise serializers.ValidationError("Une ordonnance ne peut pas être datée du futur.")
        return valeur

    def create(self, validated_data):
        mesures = MesuresSerializer(validated_data.pop("mesures")).data
        prescription = Prescription(**validated_data)
        prescription.mesures = mesures
        prescription.save()
        return prescription
