from decimal import Decimal

from rest_framework import serializers

from ..models import Facture, LigneVente, Paiement, Vente


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
    client = serializers.UUIDField(
        required=False, allow_null=True, help_text="Facultatif ; repris pour la facture."
    )
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
    client = serializers.SerializerMethodField()
    reste_a_payer = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    facture = serializers.SerializerMethodField(help_text="N° de la facture, si elle est émise.")
    lignes = LigneVenteSerializer(many=True, read_only=True)
    paiements = PaiementSerializer(many=True, read_only=True)

    class Meta:
        model = Vente
        fields = [
            "id",
            "numero",
            "magasin",
            "client",
            "vendeur",
            "cree_le",
            "devise",
            "total_ht",
            "total_tva",
            "total_ttc",
            "reste_a_payer",
            "facture",
            "lignes",
            "paiements",
        ]

    def get_client(self, vente) -> dict | None:
        return client_resume(vente.client)

    def get_facture(self, vente) -> str | None:
        facture = getattr(vente, "facture", None)
        return facture.numero if facture else None


def client_resume(client):
    if client is None:
        return None
    return {
        "id": str(client.public_id),
        "nom": str(client),
        "matricule_fiscal": client.matricule_fiscal,
    }


class FactureSaisieSerializer(serializers.Serializer):
    vente = serializers.UUIDField(help_text="Vente entièrement payée à facturer.")
    client = serializers.UUIDField(
        required=False, allow_null=True, help_text="Par défaut, le client de la vente."
    )
    mode_paiement_timbre = serializers.ChoiceField(
        choices=Paiement.Mode.choices,
        required=False,
        allow_blank=True,
        help_text="Règlement du droit de timbre par le client.",
    )


class FactureSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    magasin = serializers.CharField(source="magasin.code", read_only=True)
    vente = serializers.CharField(source="vente.numero", read_only=True)
    client = serializers.SerializerMethodField()
    emise_par = serializers.CharField(source="emise_par.get_username", read_only=True)
    lignes = LigneVenteSerializer(source="vente.lignes", many=True, read_only=True)

    class Meta:
        model = Facture
        fields = [
            "id",
            "numero",
            "magasin",
            "vente",
            "client",
            "cree_le",
            "emise_par",
            "devise",
            "total_ht",
            "total_tva",
            "total_ttc",
            "timbre_fiscal",
            "net_a_payer",
            "mode_paiement_timbre",
            "lignes",
        ]

    def get_client(self, facture) -> dict | None:
        return client_resume(facture.client)
