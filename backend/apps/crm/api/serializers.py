from rest_framework import serializers

from apps.reseau.models import Magasin

from ..models import Client


class ClientSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    magasin_origine = serializers.SlugRelatedField(
        slug_field="public_id",
        queryset=Magasin.objects,
        help_text="Magasin où le client a été créé ; ne change plus ensuite.",
    )

    class Meta:
        model = Client
        fields = [
            "id",
            "numero",
            "civilite",
            "nom",
            "prenom",
            "date_naissance",
            "telephone",
            "telephone_2",
            "email",
            "adresse",
            "code_postal",
            "ville",
            "societe",
            "matricule_fiscal",
            "magasin_origine",
            "accepte_relances",
            "notes",
            "est_actif",
            "cree_le",
        ]
        read_only_fields = ["numero", "cree_le"]

    def validate(self, attrs):
        if self.instance is not None:
            attrs.pop("magasin_origine", None)
        if "matricule_fiscal" in attrs:
            attrs["matricule_fiscal"] = attrs["matricule_fiscal"].strip().upper()
        societe = attrs.get("societe", getattr(self.instance, "societe", ""))
        matricule = attrs.get("matricule_fiscal", getattr(self.instance, "matricule_fiscal", ""))
        if matricule and not societe:
            raise serializers.ValidationError(
                {"societe": "Un matricule fiscal va avec le nom de la société."}
            )
        return attrs
