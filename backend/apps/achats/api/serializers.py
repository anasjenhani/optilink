from rest_framework import serializers

from apps.ventes.api.serializers import client_resume

from ..models import CasseVerre, CommandeFournisseur, Fournisseur, LigneCommandeFournisseur


class FournisseurSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    pays = serializers.CharField(source="pays.code", read_only=True)

    class Meta:
        model = Fournisseur
        fields = ["id", "nom", "pays", "telephone", "email", "est_actif"]


class VerreACommanderSerializer(serializers.Serializer):
    """Ligne d'une commande client dont les verres restent à commander."""

    ligne = serializers.IntegerField(source="pk")
    commande_client = serializers.CharField(source="vente.numero")
    client = serializers.SerializerMethodField()
    commandee_le = serializers.DateTimeField(source="vente.cree_le")
    livraison_prevue_le = serializers.DateField(source="vente.livraison_prevue_le")
    peniche = serializers.IntegerField(source="vente.peniche", allow_null=True)
    article = serializers.CharField(source="article.reference")
    libelle = serializers.CharField()
    quantite = serializers.IntegerField()
    fournisseur = serializers.UUIDField(
        source="article.fournisseur.public_id",
        allow_null=True,
        default=None,
        help_text="Fournisseur habituel de l'article.",
    )
    reference_fournisseur = serializers.CharField(source="article.reference_fournisseur")

    def get_client(self, ligne) -> dict | None:
        return client_resume(ligne.vente.client)


class LigneCommandeSaisieSerializer(serializers.Serializer):
    ligne = serializers.IntegerField(help_text="``ligne`` d'un verre à commander.")
    details = serializers.CharField(required=False, allow_blank=True, max_length=300)


class CommandeFournisseurSaisieSerializer(serializers.Serializer):
    magasin = serializers.UUIDField()
    fournisseur = serializers.UUIDField()
    reference_fournisseur = serializers.CharField(required=False, allow_blank=True, max_length=60)
    lignes = LigneCommandeSaisieSerializer(many=True, allow_empty=False)


class LigneCommandeFournisseurSerializer(serializers.ModelSerializer):
    commande_client = serializers.CharField(source="ligne_vente.vente.numero", read_only=True)
    libelle = serializers.CharField(source="ligne_vente.libelle", read_only=True)

    class Meta:
        model = LigneCommandeFournisseur
        fields = ["commande_client", "libelle", "quantite", "details"]


class CommandeFournisseurSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    magasin = serializers.CharField(source="magasin.code", read_only=True)
    fournisseur = serializers.CharField(source="fournisseur.nom", read_only=True)
    passee_par = serializers.CharField(source="passee_par.get_username", read_only=True)
    lignes = LigneCommandeFournisseurSerializer(many=True, read_only=True)

    class Meta:
        model = CommandeFournisseur
        fields = [
            "id",
            "numero",
            "magasin",
            "fournisseur",
            "reference_fournisseur",
            "statut",
            "cree_le",
            "passee_par",
            "recue_le",
            "lignes",
        ]


class CasseVerreSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    vente = serializers.UUIDField(source="vente.public_id", read_only=True)
    vente_numero = serializers.CharField(source="vente.numero", read_only=True)
    magasin = serializers.CharField(source="vente.magasin.code", read_only=True)
    client = serializers.SerializerMethodField()
    verre = serializers.CharField(source="ligne_commande.ligne_vente.libelle", read_only=True)
    commande_fournisseur = serializers.CharField(
        source="ligne_commande.commande.numero", read_only=True
    )
    fournisseur = serializers.CharField(
        source="ligne_commande.commande.fournisseur.nom", read_only=True
    )
    cause_libelle = serializers.CharField(source="get_cause_display", read_only=True)
    declaree_par = serializers.SerializerMethodField()

    class Meta:
        model = CasseVerre
        fields = [
            "id",
            "vente",
            "vente_numero",
            "magasin",
            "client",
            "verre",
            "commande_fournisseur",
            "fournisseur",
            "cause",
            "cause_libelle",
            "observation",
            "declaree_par",
            "cree_le",
        ]

    def get_client(self, casse) -> str | None:
        client = casse.vente.client
        return str(client) if client else None

    def get_declaree_par(self, casse) -> str:
        auteur = casse.declaree_par
        return auteur.get_full_name() or auteur.get_username()


class CasseVerreSaisieSerializer(serializers.Serializer):
    ligne_commande = serializers.IntegerField(
        help_text="Verre reçu (``verres[].id`` de la fiche de visite)."
    )
    cause = serializers.ChoiceField(choices=CasseVerre.Cause.choices)
    observation = serializers.CharField(required=False, allow_blank=True, max_length=300)
