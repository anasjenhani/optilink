from decimal import Decimal

from rest_framework import serializers

from ..models import Devis, Facture, LigneDevis, LigneVente, Paiement, Vente


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


class LigneDevisSaisieSerializer(LigneSaisieSerializer):
    oeil = serializers.ChoiceField(
        choices=LigneDevis.Oeil.choices, required=False, allow_blank=True
    )


class DevisSaisieSerializer(serializers.Serializer):
    magasin = serializers.UUIDField()
    client = serializers.UUIDField()
    prescription = serializers.UUIDField(
        required=False, allow_null=True, help_text="Ordonnance du client, facultative."
    )
    lignes = LigneDevisSaisieSerializer(many=True, allow_empty=False)
    valable_jusqu_au = serializers.DateField(
        required=False, allow_null=True, help_text="Par défaut, dans DEVIS_VALIDITE_JOURS jours."
    )
    remarques = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class EncaissementDevisSerializer(serializers.Serializer):
    paiements = PaiementSaisieSerializer(many=True, allow_empty=False)


class LigneDevisSerializer(serializers.ModelSerializer):
    article = serializers.UUIDField(source="article.public_id", read_only=True)

    class Meta:
        model = LigneDevis
        fields = [
            "article",
            "libelle",
            "oeil",
            "quantite",
            "prix_unitaire_ttc",
            "remise_pct",
            "taux_tva",
            "total_ttc",
        ]


class DevisSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    magasin = serializers.CharField(source="magasin.code", read_only=True)
    client = serializers.SerializerMethodField()
    prescription = serializers.SerializerMethodField(
        help_text="Visible seulement par ceux qui ont accès aux ordonnances."
    )
    etabli_par = serializers.CharField(source="etabli_par.get_username", read_only=True)
    vente = serializers.SerializerMethodField(help_text="N° du ticket, une fois encaissé.")
    lignes = LigneDevisSerializer(many=True, read_only=True)

    class Meta:
        model = Devis
        fields = [
            "id",
            "numero",
            "magasin",
            "client",
            "prescription",
            "etabli_par",
            "cree_le",
            "valable_jusqu_au",
            "statut",
            "devise",
            "total_ht",
            "total_tva",
            "total_ttc",
            "remarques",
            "vente",
            "lignes",
        ]

    def get_client(self, devis) -> dict | None:
        return client_resume(devis.client)

    def get_prescription(self, devis) -> dict | None:
        requete = self.context.get("request")
        if devis.prescription is None or requete is None:
            return None
        if not requete.user.has_perm("optique.view_prescription"):
            return None
        return {
            "id": str(devis.prescription.public_id),
            "type": devis.prescription.type,
            "date_prescription": devis.prescription.date_prescription.isoformat(),
        }

    def get_vente(self, devis) -> str | None:
        return devis.vente.numero if devis.vente else None
