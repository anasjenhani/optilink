from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.reseau.banques import valider_banque
from apps.reseau.models import Magasin, Societe

from .. import banque
from ..models import ClotureCaisse, CompteTresorerie, DepenseCaisse, OperationTresorerie

MONTANT = {"max_digits": 14, "decimal_places": 3, "min_value": 0}


class SituationSerializer(serializers.Serializer):
    """Ce qui est attendu dans la caisse depuis la dernière clôture."""

    debut = serializers.DateTimeField(allow_null=True)
    fin = serializers.DateTimeField()
    devise = serializers.CharField()
    fond_initial = serializers.DecimalField(max_digits=14, decimal_places=3)
    encaisse_especes = serializers.DecimalField(max_digits=14, decimal_places=3)
    encaisse_cheques = serializers.DecimalField(max_digits=14, decimal_places=3)
    nombre_cheques = serializers.IntegerField()
    encaisse_cartes = serializers.DecimalField(max_digits=14, decimal_places=3)
    rembourse_especes = serializers.DecimalField(max_digits=14, decimal_places=3)
    rembourse_cheques = serializers.DecimalField(max_digits=14, decimal_places=3)
    rembourse_cartes = serializers.DecimalField(max_digits=14, decimal_places=3)
    depenses = serializers.DecimalField(max_digits=14, decimal_places=3)
    alimentations = serializers.DecimalField(max_digits=14, decimal_places=3)
    especes_attendues = serializers.DecimalField(max_digits=14, decimal_places=3)
    cheques_attendus = serializers.DecimalField(max_digits=14, decimal_places=3)
    cartes_attendues = serializers.DecimalField(max_digits=14, decimal_places=3)
    cloture_rejetee = serializers.UUIDField(
        allow_null=True, help_text="Clôture rejetée à corriger avant d'en faire une nouvelle."
    )


class ComptageSerializer(serializers.Serializer):
    especes_comptees = serializers.DecimalField(**MONTANT)
    cheques_comptes = serializers.DecimalField(**MONTANT)
    nombre_cheques_comptes = serializers.IntegerField(min_value=0)
    cartes_comptees = serializers.DecimalField(**MONTANT)
    fond_conserve = serializers.DecimalField(**MONTANT)
    commentaire_caissier = serializers.CharField(required=False, allow_blank=True)


class ClotureSaisieSerializer(ComptageSerializer):
    magasin = serializers.UUIDField()


class VerificationSerializer(serializers.Serializer):
    commentaire = serializers.CharField(required=False, allow_blank=True, default="")


class ClotureSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    magasin = serializers.CharField(source="magasin.nom", read_only=True)
    cloturee_par = serializers.SerializerMethodField()
    verifiee_par = serializers.SerializerMethodField()
    especes_attendues = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    cheques_attendus = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    cartes_attendues = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    ecart_especes = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    ecart_cheques = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    ecart_cartes = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    especes_a_remettre = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    depot_especes = serializers.CharField(
        source="depot_especes.numero", read_only=True, allow_null=True
    )
    depot_cheques = serializers.CharField(
        source="depot_cheques.numero", read_only=True, allow_null=True
    )
    encaissement_cartes = serializers.CharField(
        source="encaissement_cartes.numero", read_only=True, allow_null=True
    )

    class Meta:
        model = ClotureCaisse
        fields = [
            "id",
            "numero",
            "magasin",
            "debut",
            "fin",
            "devise",
            "statut",
            "fond_initial",
            "encaisse_especes",
            "encaisse_cheques",
            "nombre_cheques",
            "encaisse_cartes",
            "rembourse_especes",
            "rembourse_cheques",
            "rembourse_cartes",
            "depenses",
            "alimentations",
            "especes_attendues",
            "cheques_attendus",
            "cartes_attendues",
            "especes_comptees",
            "cheques_comptes",
            "nombre_cheques_comptes",
            "cartes_comptees",
            "fond_conserve",
            "especes_a_remettre",
            "ecart_especes",
            "ecart_cheques",
            "ecart_cartes",
            "commentaire_caissier",
            "cloturee_par",
            "verifiee_par",
            "verifiee_le",
            "commentaire_finance",
            "depot_especes",
            "depot_cheques",
            "encaissement_cartes",
        ]

    def get_cloturee_par(self, cloture) -> str:
        return cloture.cloturee_par.get_full_name() or cloture.cloturee_par.get_username()

    def get_verifiee_par(self, cloture) -> str | None:
        u = cloture.verifiee_par
        return (u.get_full_name() or u.get_username()) if u else None


class DepenseSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    magasin = serializers.SlugRelatedField(slug_field="public_id", read_only=True)
    magasin_id = serializers.UUIDField(write_only=True)
    montant = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal("0.001"))
    saisie_par = serializers.SerializerMethodField()
    cloture = serializers.CharField(source="cloture.numero", read_only=True, allow_null=True)

    class Meta:
        model = DepenseCaisse
        fields = [
            "id",
            "magasin",
            "magasin_id",
            "categorie",
            "motif",
            "beneficiaire",
            "montant",
            "payee_le",
            "saisie_par",
            "cloture",
        ]
        read_only_fields = ["payee_le"]

    def get_saisie_par(self, depense) -> str:
        return depense.saisie_par.get_full_name() or depense.saisie_par.get_username()


def nom_de(utilisateur):
    if utilisateur is None:
        return None
    return utilisateur.get_full_name() or utilisateur.get_username()


POSITIF = {"max_digits": 14, "decimal_places": 3, "min_value": Decimal("0.001")}


SOLDE = serializers.DecimalField(max_digits=14, decimal_places=3, allow_null=True)


class CompteSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    societe = serializers.SlugRelatedField(slug_field="public_id", queryset=Societe.objects.all())
    societe_nom = serializers.CharField(source="societe.raison_sociale", read_only=True)
    magasin = serializers.SlugRelatedField(
        slug_field="public_id",
        queryset=Magasin.tous.all(),
        required=False,
        allow_null=True,
    )
    magasin_nom = serializers.CharField(source="magasin.nom", read_only=True, allow_null=True)
    solde_comptable = serializers.SerializerMethodField(
        help_text="Selon OptiLink ; vide si vous ne voyez pas les soldes de la société."
    )
    solde_banque = serializers.SerializerMethodField(
        help_text="Ce que le relevé doit afficher : opérations rapprochées seulement."
    )

    class Meta:
        model = CompteTresorerie
        fields = [
            "id",
            "societe",
            "societe_nom",
            "type",
            "nom",
            "banque",
            "rib",
            "magasin",
            "magasin_nom",
            "devise",
            "solde_initial",
            "est_actif",
            "solde_comptable",
            "solde_banque",
        ]

    def validate(self, donnees):
        type_ = donnees.get("type", getattr(self.instance, "type", None))
        magasin = donnees.get("magasin", getattr(self.instance, "magasin", None))
        societe = donnees.get("societe", getattr(self.instance, "societe", None))
        if type_ == CompteTresorerie.Type.COFFRE and magasin is None:
            raise serializers.ValidationError({"magasin": "Un coffre se trouve dans un magasin."})
        if type_ != CompteTresorerie.Type.COFFRE:
            donnees["magasin"] = None
        elif magasin.societe_id != societe.pk:
            raise serializers.ValidationError({"magasin": "Ce magasin est d'une autre société."})
        if "banque" in donnees or "rib" in donnees:
            try:
                donnees["banque"] = valider_banque(
                    donnees.get("banque", getattr(self.instance, "banque", "")),
                    donnees.get("rib", getattr(self.instance, "rib", "")),
                    getattr(societe, "pays", None),
                )
            except DjangoValidationError as erreur:
                raise serializers.ValidationError(erreur.message_dict) from erreur
        return donnees

    def _soldes(self, compte):
        visibles = self.context.get("soldes_visibles")
        if visibles is not None and compte.societe_id not in visibles:
            return None
        cache = self.context.setdefault("_soldes", {})
        if compte.pk not in cache:
            cache[compte.pk] = banque.soldes(compte)
        return cache[compte.pk]

    @extend_schema_field(SOLDE)
    def get_solde_comptable(self, compte):
        soldes = self._soldes(compte)
        return soldes and SOLDE.to_representation(soldes[0])

    @extend_schema_field(SOLDE)
    def get_solde_banque(self, compte):
        soldes = self._soldes(compte)
        return soldes and SOLDE.to_representation(soldes[1])


class OperationSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    societe = serializers.CharField(source="societe.raison_sociale")
    type_libelle = serializers.CharField(source="get_type_display")
    source = serializers.CharField(source="source.nom", allow_null=True)
    destination = serializers.CharField(source="destination.nom", allow_null=True)
    magasin = serializers.CharField(source="magasin.nom", allow_null=True)
    commission = serializers.DecimalField(max_digits=14, decimal_places=3, allow_null=True)
    cree_par = serializers.SerializerMethodField()
    rapprochee_par = serializers.SerializerMethodField()

    class Meta:
        model = OperationTresorerie
        fields = [
            "id",
            "numero",
            "societe",
            "type",
            "type_libelle",
            "statut",
            "source",
            "destination",
            "magasin",
            "montant",
            "montant_credite",
            "commission",
            "date_prevue",
            "date_operation",
            "date_valeur",
            "reference",
            "libelle",
            "cree_par",
            "rapprochee_par",
        ]
        read_only_fields = fields

    def get_cree_par(self, operation) -> str:
        return nom_de(operation.cree_par)

    def get_rapprochee_par(self, operation) -> str | None:
        return nom_de(operation.rapprochee_par)


class ARemettreSerializer(serializers.Serializer):
    """Clôture validée dont une partie de l'argent attend d'être déposée."""

    id = serializers.UUIDField(source="cloture.public_id")
    numero = serializers.CharField(source="cloture.numero")
    magasin = serializers.CharField(source="cloture.magasin.nom")
    societe = serializers.UUIDField(source="cloture.magasin.societe.public_id")
    fin = serializers.DateTimeField(source="cloture.fin")
    devise = serializers.CharField(source="cloture.devise")
    especes = serializers.DecimalField(max_digits=14, decimal_places=3, allow_null=True)
    cheques = serializers.DecimalField(max_digits=14, decimal_places=3, allow_null=True)
    nombre_cheques = serializers.IntegerField(allow_null=True)
    cartes = serializers.DecimalField(max_digits=14, decimal_places=3, allow_null=True)


class _Effectuer(serializers.Serializer):
    prevue = serializers.BooleanField(
        default=False, help_text="Prévision : le versement n'est pas encore fait."
    )
    reference = serializers.CharField(required=False, allow_blank=True, default="", max_length=60)
    date = serializers.DateField(
        required=False, allow_null=True, default=None, help_text="Date prévue ou date du dépôt."
    )


class DepotSerializer(_Effectuer):
    type = serializers.ChoiceField(choices=list(banque.DEPOTS))
    clotures = serializers.ListField(child=serializers.UUIDField(), min_length=1)
    destination = serializers.UUIDField()


class OperationSaisieSerializer(_Effectuer):
    type = serializers.ChoiceField(
        choices=[
            OperationTresorerie.Type.TRANSFERT,
            OperationTresorerie.Type.ALIMENTATION_FOND,
            OperationTresorerie.Type.OPERATION_BANCAIRE,
        ]
    )
    societe = serializers.UUIDField()
    montant = serializers.DecimalField(**POSITIF)
    source = serializers.UUIDField(required=False, allow_null=True, default=None)
    destination = serializers.UUIDField(required=False, allow_null=True, default=None)
    magasin = serializers.UUIDField(required=False, allow_null=True, default=None)
    libelle = serializers.CharField(required=False, allow_blank=True, default="", max_length=200)


class EffectuerSerializer(serializers.Serializer):
    reference = serializers.CharField(required=False, allow_blank=True, default="", max_length=60)
    date = serializers.DateField(required=False, allow_null=True, default=None)


class RapprocherSerializer(serializers.Serializer):
    date_valeur = serializers.DateField()
    montant_credite = serializers.DecimalField(
        max_digits=14,
        decimal_places=3,
        min_value=0,
        required=False,
        allow_null=True,
        default=None,
        help_text="Cartes : montant crédité par la banque, commission déduite.",
    )
