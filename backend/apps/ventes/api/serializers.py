from decimal import Decimal

from rest_framework import serializers

from ..models import Avoir, Devis, Facture, LigneAvoir, LigneDevis, LigneVente, Paiement, Vente


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
    paiements = PaiementSaisieSerializer(
        many=True, help_text="Tout le prix, ou l'acompte d'une commande (peut être vide)."
    )
    commande = serializers.BooleanField(
        default=False, help_text="Commande : acompte maintenant, solde à la livraison."
    )
    livraison_prevue_le = serializers.DateField(required=False, allow_null=True)


class ReglementSerializer(serializers.Serializer):
    paiements = PaiementSaisieSerializer(many=True, allow_empty=False)


class LivraisonSerializer(serializers.Serializer):
    paiements = PaiementSaisieSerializer(
        many=True, required=False, help_text="Solde encaissé à la livraison, s'il reste dû."
    )


class LigneVenteSerializer(serializers.ModelSerializer):
    article = serializers.UUIDField(source="article.public_id", read_only=True)
    quantite_reprise = serializers.SerializerMethodField(help_text="Déjà reprise par avoir.")

    class Meta:
        model = LigneVente
        fields = [
            "id",
            "quantite_reprise",
            "article",
            "libelle",
            "quantite",
            "prix_unitaire_ttc",
            "remise_pct",
            "taux_tva",
            "total_ttc",
        ]

    def get_quantite_reprise(self, ligne) -> int:
        return sum(retour.quantite for retour in ligne.retours.all())


class PaiementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Paiement
        fields = ["mode", "montant", "recu_le"]


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
            "statut",
            "livraison_prevue_le",
            "livree_le",
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
    paiements = PaiementSaisieSerializer(many=True)
    commande = serializers.BooleanField(
        default=False, help_text="Commande : acompte maintenant, solde à la livraison."
    )
    livraison_prevue_le = serializers.DateField(required=False, allow_null=True)


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


class RetourSaisieSerializer(serializers.Serializer):
    ligne = serializers.IntegerField(help_text="``id`` de la ligne de vente.")
    quantite = serializers.IntegerField(min_value=1, max_value=999)
    remis_en_stock = serializers.BooleanField(default=True)


class AvoirSaisieSerializer(serializers.Serializer):
    vente = serializers.UUIDField()
    annulation = serializers.BooleanField(
        default=False, help_text="Annule toute la vente (ou la commande) ; ``lignes`` ignorées."
    )
    lignes = RetourSaisieSerializer(many=True, required=False)
    motif = serializers.CharField(max_length=300)
    mode_remboursement = serializers.ChoiceField(
        choices=Paiement.Mode.choices, required=False, allow_blank=True
    )
    remis_en_stock = serializers.BooleanField(
        default=True, help_text="Annulation d'une vente livrée : les articles reviennent en stock."
    )

    def validate(self, donnees):
        if not donnees["annulation"] and not donnees.get("lignes"):
            raise serializers.ValidationError({"lignes": "Préciser les articles repris."})
        return donnees


class LigneAvoirSerializer(serializers.ModelSerializer):
    class Meta:
        model = LigneAvoir
        fields = ["libelle", "quantite", "taux_tva", "total_ttc", "remis_en_stock"]


class AvoirSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    magasin = serializers.CharField(source="magasin.code", read_only=True)
    vente = serializers.CharField(source="vente.numero", read_only=True)
    facture = serializers.SerializerMethodField()
    client = serializers.SerializerMethodField()
    emis_par = serializers.CharField(source="emis_par.get_username", read_only=True)
    lignes = LigneAvoirSerializer(many=True, read_only=True)

    class Meta:
        model = Avoir
        fields = [
            "id",
            "numero",
            "magasin",
            "vente",
            "facture",
            "client",
            "annulation",
            "motif",
            "cree_le",
            "emis_par",
            "devise",
            "total_ht",
            "total_tva",
            "total_ttc",
            "montant_rembourse",
            "mode_remboursement",
            "lignes",
        ]

    def get_facture(self, avoir) -> str | None:
        return avoir.facture.numero if avoir.facture else None

    def get_client(self, avoir) -> dict | None:
        return client_resume(avoir.client)
