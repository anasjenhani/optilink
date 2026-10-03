from decimal import Decimal

from rest_framework import serializers

from ..models import ClotureCaisse, DepenseCaisse

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
