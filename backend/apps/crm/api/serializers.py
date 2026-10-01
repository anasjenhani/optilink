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
            "civilite",
            "nom",
            "prenom",
            "date_naissance",
            "telephone",
            "email",
            "adresse",
            "code_postal",
            "ville",
            "matricule_fiscal",
            "magasin_origine",
            "accepte_relances",
            "notes",
            "est_actif",
            "cree_le",
        ]
        read_only_fields = ["cree_le"]

    def validate(self, attrs):
        if self.instance is not None:
            attrs.pop("magasin_origine", None)
        return attrs
