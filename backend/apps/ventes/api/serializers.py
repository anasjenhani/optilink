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
    montant = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))


class VenteSaisieSerializer(serializers.Serializer):
    magasin = serializers.UUIDField()
    lignes = LigneSaisieSerializer(many=True, allow_empty=False)
    paiements = PaiementSaisieSerializer(many=True, allow_empty=False)


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
    lignes = LigneVenteSerializer(many=True, read_only=True)
    paiements = PaiementSerializer(many=True, read_only=True)

    class Meta:
        model = Vente
        fields = [
            "id",
            "numero",
            "magasin",
            "vendeur",
            "cree_le",
            "total_ht",
            "total_tva",
            "total_ttc",
            "lignes",
            "paiements",
        ]
