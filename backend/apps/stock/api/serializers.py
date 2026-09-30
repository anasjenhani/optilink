from rest_framework import serializers

from apps.reseau.models import Magasin

from ..models import Article, MouvementStock


class ArticleSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    stock = serializers.IntegerField(
        read_only=True, allow_null=True, help_text="Quantité en stock du magasin demandé."
    )

    class Meta:
        model = Article
        fields = [
            "id",
            "reference",
            "libelle",
            "famille",
            "code_barres",
            "prix_vente_ttc",
            "taux_tva",
            "stock",
        ]


class MouvementStockSerializer(serializers.ModelSerializer):
    magasin = serializers.SlugRelatedField(slug_field="public_id", queryset=Magasin.objects)
    article = serializers.SlugRelatedField(slug_field="public_id", queryset=Article.objects)
    type = serializers.ChoiceField(
        choices=[MouvementStock.Type.RECEPTION, MouvementStock.Type.AJUSTEMENT]
    )

    class Meta:
        model = MouvementStock
        fields = ["id", "magasin", "article", "quantite", "type", "reference", "horodatage"]
        read_only_fields = ["id", "horodatage"]

    def get_fields(self):
        champs = super().get_fields()
        # Évalués à chaque requête pour appliquer le périmètre de l'utilisateur.
        champs["magasin"].queryset = Magasin.objects.all()
        champs["article"].queryset = Article.objects.filter(est_actif=True)
        return champs

    def validate(self, donnees):
        if donnees["quantite"] == 0:
            raise serializers.ValidationError({"quantite": "La quantité ne peut pas être nulle."})
        if donnees["type"] == MouvementStock.Type.RECEPTION and donnees["quantite"] < 0:
            raise serializers.ValidationError({"quantite": "Une réception est positive."})
        return donnees
