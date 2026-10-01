from decimal import Decimal

from rest_framework import serializers

from ..models import LigneVente, Paiement, Vente


class LigneSaisieSerializer(serializers.Serializer):
    article = serializers.UUIDField()
    quantite = serializers.IntegerField(min_value=1, max_value=999)
    remise_pct = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        default=Decimal("0"),
    )


class PaiementSaisieSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=Paiement.Mode.choices)
    montant = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal("0.001"))


class VenteSaisieSerializer(serializers.Serializer):
    magasin = serializers.UUIDField()
    facture = serializers.BooleanField(
        default=False,
        help_text="Facture au nom du client (avec droit de timbre) plutôt qu'un ticket de caisse.",
    )
    client = serializers.UUIDField(required=False, allow_null=True)
    lignes = LigneSaisieSerializer(many=True, allow_empty=False)
    paiements = PaiementSaisieSerializer(many=True, allow_empty=False)

    def validate(self, attrs):
        if attrs["facture"] and not attrs.get("client"):
            raise serializers.ValidationError({"client": "Une facture exige un client."})
        return attrs


class LigneVenteSerializer(serializers.ModelSerializer):
    article = serializers.UUIDField(source="article.public_id", read_only=True)

    class Meta:
        model = LigneVente
        fields = [
            "article",
            "libelle",
            "quantite",
            "prix_unitaire_ttc",
            "remise_pct",
            "taux_tva",
            "total_ttc",
        ]


class PaiementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Paiement
        fields = ["mode", "montant"]


class VenteSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    magasin = serializers.CharField(source="magasin.code", read_only=True)
    vendeur = serializers.CharField(source="vendeur.get_username", read_only=True)
    client = serializers.SerializerMethodField()
    lignes = LigneVenteSerializer(many=True, read_only=True)
    paiements = PaiementSerializer(many=True, read_only=True)

    class Meta:
        model = Vente
        fields = [
            "id",
            "type_document",
            "numero",
            "magasin",
            "client",
            "vendeur",
            "cree_le",
            "devise",
            "total_ht",
            "total_tva",
            "total_ttc",
            "timbre_fiscal",
            "net_a_payer",
            "lignes",
            "paiements",
        ]

    def get_client(self, vente) -> dict | None:
        if vente.client is None:
            return None
        client = vente.client
        return {
            "id": str(client.public_id),
            "nom": str(client),
            "matricule_fiscal": client.matricule_fiscal,
        }
