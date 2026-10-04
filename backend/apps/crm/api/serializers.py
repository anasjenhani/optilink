from rest_framework import serializers

from apps.reseau.models import Magasin

from ..models import Client, Organisme


class OrganismeSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    pays = serializers.CharField(source="pays.code", read_only=True)
    type_libelle = serializers.CharField(source="get_type_display", read_only=True)

    class Meta:
        model = Organisme
        fields = ["id", "nom", "type", "type_libelle", "pays"]


class ClientSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    organisme = serializers.SlugRelatedField(
        slug_field="public_id",
        queryset=Organisme.objects.filter(est_actif=True),
        allow_null=True,
        required=False,
        help_text="CNAM, assurance ou mutuelle du client (PEC client).",
    )
    organisme_nom = serializers.CharField(source="organisme.nom", read_only=True, default=None)
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
            "reference_externe",
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
            "organisme",
            "organisme_nom",
            "numero_affilie",
            "notes",
            "est_actif",
            "cree_le",
        ]
        read_only_fields = ["numero", "reference_externe", "cree_le"]

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
