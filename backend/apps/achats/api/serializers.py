from rest_framework import serializers

from apps.reseau.models import Pays
from apps.stock.models import Article
from apps.ventes.api.serializers import client_resume

from ..models import (
    BonReception,
    CasseVerre,
    CommandeFournisseur,
    Fournisseur,
    LigneCommandeFournisseur,
    LigneReception,
)
from ..receptions import detail_tva


class FournisseurSerializer(serializers.ModelSerializer):
    """Fiche fournisseur ; le code est attribué à la création, le pays par son code ISO."""

    id = serializers.UUIDField(source="public_id", read_only=True)
    pays = serializers.SlugRelatedField(
        slug_field="code", queryset=Pays.objects.all(), required=False
    )

    class Meta:
        model = Fournisseur
        fields = [
            "id",
            "code",
            "nom",
            "notre_code",
            "responsable",
            "fournisseur_verres",
            "pays",
            "matricule_fiscal",
            "registre_commerce",
            "code_douane",
            "forme_juridique",
            "capital_social",
            "timbre_fiscal",
            "assujetti",
            "fodec",
            "regime_tva",
            "numero_exoneration",
            "exoneration_du",
            "exoneration_au",
            "adresse",
            "code_postal",
            "ville",
            "telephone",
            "telephone_2",
            "fax",
            "email",
            "site_web",
            "banque",
            "rib",
            "observation",
            "est_actif",
        ]
        read_only_fields = ["code"]

    def validate(self, attrs):
        du = attrs.get("exoneration_du", getattr(self.instance, "exoneration_du", None))
        au = attrs.get("exoneration_au", getattr(self.instance, "exoneration_au", None))
        if du and au and au < du:
            raise serializers.ValidationError({"exoneration_au": "Fin avant le début."})
        return attrs


class ArticleResumeSerializer(serializers.Serializer):
    id = serializers.UUIDField(source="public_id")
    reference = serializers.CharField()
    libelle = serializers.CharField()
    famille = serializers.CharField()
    code_barres = serializers.CharField()


class LigneAReceptionnerSerializer(serializers.Serializer):
    """Verre commandé au fournisseur pour un client, en attente de réception."""

    ligne_commande = serializers.IntegerField(source="pk")
    commande = serializers.CharField(source="commande.numero")
    commande_client = serializers.CharField(source="ligne_vente.vente.numero")
    client = serializers.SerializerMethodField()
    oeil = serializers.SerializerMethodField()
    article = ArticleResumeSerializer()
    designation = serializers.SerializerMethodField()
    quantite = serializers.IntegerField()
    dernier_prix_achat = serializers.SerializerMethodField()
    taux_tva = serializers.SerializerMethodField()

    def get_client(self, ligne) -> str | None:
        client = ligne.ligne_vente.vente.client
        return str(client) if client else None

    def get_oeil(self, ligne) -> str:
        from ..receptions import oeil_de

        return oeil_de(ligne)

    def get_designation(self, ligne) -> str:
        return ligne.details or ligne.article.libelle

    def get_dernier_prix_achat(self, ligne) -> str | None:
        prix = self.context["prix"].get(ligne.article_id)
        return None if prix is None else str(prix)

    def get_taux_tva(self, ligne) -> str:
        return str(self.context["taux"][ligne.article_id])


class LigneReceptionSaisieSerializer(serializers.Serializer):
    article = serializers.SlugRelatedField(
        slug_field="public_id", queryset=Article.objects.filter(est_actif=True)
    )
    ligne_commande = serializers.IntegerField(
        required=False, allow_null=True, help_text="Verre commandé (``a-recevoir``)."
    )
    oeil = serializers.ChoiceField(
        choices=LigneReception.Oeil.choices, required=False, allow_blank=True
    )
    quantite = serializers.IntegerField(min_value=1)
    prix_achat_ht = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=0)
    taux_remise = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=0, max_value=100, default=0
    )
    taux_tva = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=100)
    non_conforme = serializers.BooleanField(default=False)
    motif = serializers.CharField(required=False, allow_blank=True, max_length=200)
    numero_serie = serializers.CharField(required=False, allow_blank=True, max_length=60)
    numero_lot = serializers.CharField(required=False, allow_blank=True, max_length=60)
    date_peremption = serializers.DateField(required=False, allow_null=True)


class BonReceptionSaisieSerializer(serializers.Serializer):
    magasin = serializers.UUIDField()
    fournisseur = serializers.UUIDField()
    numero_bl = serializers.CharField(max_length=60)
    date_bl = serializers.DateField()
    date_saisie = serializers.DateField(required=False)
    taux_remise_ex = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=0, max_value=100, default=0
    )
    observation = serializers.CharField(required=False, allow_blank=True)
    lignes = LigneReceptionSaisieSerializer(many=True, allow_empty=False)


class LigneReceptionSerializer(serializers.ModelSerializer):
    article = ArticleResumeSerializer(read_only=True)
    commande = serializers.CharField(
        source="ligne_commande.commande.numero", read_only=True, default=None
    )

    class Meta:
        model = LigneReception
        fields = [
            "article",
            "commande",
            "oeil",
            "designation",
            "quantite",
            "prix_achat_ht",
            "taux_remise",
            "taux_tva",
            "net_ht",
            "montant_ttc",
            "non_conforme",
            "motif",
            "numero_serie",
            "numero_lot",
            "date_peremption",
        ]


class BonReceptionListeSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    magasin = serializers.CharField(source="magasin.code", read_only=True)
    fournisseur = serializers.CharField(source="fournisseur.nom", read_only=True)
    fournisseur_code = serializers.IntegerField(source="fournisseur.code", read_only=True)
    etat_libelle = serializers.CharField(source="get_etat_display", read_only=True)
    type_bl = serializers.SerializerMethodField()
    total_articles = serializers.IntegerField(read_only=True)
    cree_par = serializers.SerializerMethodField()

    class Meta:
        model = BonReception
        fields = [
            "id",
            "numero",
            "magasin",
            "date_saisie",
            "fournisseur",
            "fournisseur_code",
            "numero_bl",
            "date_bl",
            "etat",
            "etat_libelle",
            "numero_facture",
            "observation",
            "total_ht",
            "total_net_ht",
            "total_ttc",
            "type_bl",
            "total_articles",
            "cree_par",
        ]

    def get_type_bl(self, bon) -> str:
        """Famille des articles du bon (« Verre », « Lentille »…), ou « Mixte »."""
        familles = {ligne.article.get_famille_display() for ligne in bon.lignes.all()}
        return familles.pop() if len(familles) == 1 else "Mixte"

    def get_cree_par(self, bon) -> str:
        return bon.cree_par.get_full_name() or bon.cree_par.get_username()


class BonReceptionSerializer(BonReceptionListeSerializer):
    lignes = LigneReceptionSerializer(many=True, read_only=True)
    detail_tva = serializers.SerializerMethodField()

    class Meta(BonReceptionListeSerializer.Meta):
        fields = BonReceptionListeSerializer.Meta.fields + [
            "taux_remise_ex",
            "total_remise",
            "remise_ex",
            "total_fodec",
            "total_tva",
            "detail_tva",
            "lignes",
        ]

    def get_detail_tva(self, bon) -> list[dict]:
        return [{k: str(v) for k, v in ligne.items()} for ligne in detail_tva(bon)]


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
