from decimal import Decimal

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.reseau.models import Magasin
from apps.securite.models import Utilisateur

from .. import services
from ..models import Acompte, DemandeConge, Employe, Pointage, Prime

JOURS = {"max_digits": 5, "decimal_places": 1}


def nom_de(utilisateur):
    if utilisateur is None:
        return None
    return utilisateur.get_full_name() or utilisateur.get_username()


class SoldeSerializer(serializers.Serializer):
    acquis = serializers.DecimalField(**JOURS)
    pris = serializers.DecimalField(**JOURS)
    en_attente = serializers.DecimalField(**JOURS)
    disponible = serializers.DecimalField(**JOURS)


class EmployeSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    magasin = serializers.SlugRelatedField(slug_field="public_id", queryset=Magasin.tous.all())
    magasin_nom = serializers.CharField(source="magasin.nom", read_only=True)
    utilisateur = serializers.SlugRelatedField(
        slug_field="username",
        queryset=Utilisateur.objects.all(),
        required=False,
        allow_null=True,
        help_text="Identifiant du compte OptiLink de l'employé.",
    )
    solde = serializers.SerializerMethodField()

    class Meta:
        model = Employe
        fields = [
            "id",
            "matricule",
            "magasin",
            "magasin_nom",
            "utilisateur",
            "nom",
            "prenom",
            "cin",
            "telephone",
            "poste",
            "date_embauche",
            "date_sortie",
            "conges_par_mois",
            "salaire_base",
            "solde_conges_initial",
            "solde",
        ]
        read_only_fields = ["matricule"]

    def validate(self, donnees):
        embauche = donnees.get("date_embauche", getattr(self.instance, "date_embauche", None))
        sortie = donnees.get("date_sortie", getattr(self.instance, "date_sortie", None))
        if sortie and embauche and sortie < embauche:
            raise serializers.ValidationError({"date_sortie": "La sortie précède l'embauche."})
        return donnees

    @extend_schema_field(SoldeSerializer)
    def get_solde(self, employe):
        return SoldeSerializer(services.solde(employe)).data


class CongeSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    employe = serializers.UUIDField(source="employe.public_id", read_only=True)
    employe_nom = serializers.CharField(source="employe.__str__", read_only=True)
    magasin = serializers.CharField(source="magasin.nom", read_only=True)
    type_libelle = serializers.CharField(source="get_type_display", read_only=True)
    demandee_par = serializers.SerializerMethodField()
    decidee_par = serializers.SerializerMethodField()

    class Meta:
        model = DemandeConge
        fields = [
            "id",
            "employe",
            "employe_nom",
            "magasin",
            "type",
            "type_libelle",
            "debut",
            "fin",
            "jours",
            "motif",
            "statut",
            "demandee_par",
            "decidee_par",
            "decidee_le",
            "commentaire_decision",
            "cree_le",
        ]
        read_only_fields = fields

    def get_demandee_par(self, demande) -> str:
        return nom_de(demande.demandee_par)

    def get_decidee_par(self, demande) -> str | None:
        return nom_de(demande.decidee_par)


class DemandeSaisieSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=DemandeConge.Type.choices)
    debut = serializers.DateField()
    fin = serializers.DateField()
    motif = serializers.CharField(required=False, allow_blank=True, default="", max_length=200)


class DemandePourSerializer(DemandeSaisieSerializer):
    employe = serializers.UUIDField()


class DecisionSerializer(serializers.Serializer):
    commentaire = serializers.CharField(required=False, allow_blank=True, default="")


class LignePresenceSerializer(serializers.Serializer):
    employe = serializers.UUIDField()
    statut = serializers.ChoiceField(choices=Pointage.Statut.choices)
    arrivee = serializers.TimeField(required=False, allow_null=True, default=None)
    depart = serializers.TimeField(required=False, allow_null=True, default=None)
    commentaire = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=200
    )


class PresenceSaisieSerializer(serializers.Serializer):
    magasin = serializers.UUIDField()
    date = serializers.DateField()
    lignes = LignePresenceSerializer(many=True)


class PointageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pointage
        fields = ["statut", "arrivee", "depart", "commentaire"]


class FeuillePresenceSerializer(serializers.Serializer):
    """Une ligne de la feuille de présence du jour."""

    employe = serializers.UUIDField(source="employe.public_id")
    matricule = serializers.CharField(source="employe.matricule")
    nom = serializers.CharField(source="employe.__str__")
    poste = serializers.CharField(source="employe.poste")
    pointage = PointageSerializer(allow_null=True)
    conge = serializers.CharField(
        allow_null=True, help_text="Type de congé si l'employé est en congé."
    )


MONTANT = {"max_digits": 12, "decimal_places": 3}


class AcompteSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    employe = serializers.UUIDField(source="employe.public_id", read_only=True)
    employe_nom = serializers.CharField(source="employe.__str__", read_only=True)
    magasin = serializers.CharField(source="magasin.nom", read_only=True)
    demande_par = serializers.SerializerMethodField()
    decide_par = serializers.SerializerMethodField()

    class Meta:
        model = Acompte
        fields = [
            "id",
            "employe",
            "employe_nom",
            "magasin",
            "montant",
            "mois",
            "motif",
            "statut",
            "demande_par",
            "decide_par",
            "decide_le",
            "commentaire_decision",
            "mode_versement",
            "verse_le",
            "reference_versement",
        ]
        read_only_fields = fields

    def get_demande_par(self, acompte) -> str:
        return nom_de(acompte.demande_par)

    def get_decide_par(self, acompte) -> str | None:
        return nom_de(acompte.decide_par)


class PrimeSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    employe = serializers.UUIDField(source="employe.public_id", read_only=True)
    employe_nom = serializers.CharField(source="employe.__str__", read_only=True)
    magasin = serializers.CharField(source="magasin.nom", read_only=True)
    type_libelle = serializers.CharField(source="get_type_display", read_only=True)
    proposee_par = serializers.SerializerMethodField()
    validee_par = serializers.SerializerMethodField()

    class Meta:
        model = Prime
        fields = [
            "id",
            "employe",
            "employe_nom",
            "magasin",
            "type",
            "type_libelle",
            "montant",
            "mois",
            "motif",
            "statut",
            "proposee_par",
            "validee_par",
            "validee_le",
            "commentaire_decision",
        ]
        read_only_fields = fields

    def get_proposee_par(self, prime) -> str:
        return nom_de(prime.proposee_par)

    def get_validee_par(self, prime) -> str | None:
        return nom_de(prime.validee_par)


POSITIF = MONTANT | {"min_value": Decimal("0.001")}


class AcompteSaisieSerializer(serializers.Serializer):
    montant = serializers.DecimalField(**POSITIF)
    mois = serializers.DateField(
        required=False, allow_null=True, default=None, help_text="Paie qui le retiendra."
    )
    motif = serializers.CharField(required=False, allow_blank=True, default="", max_length=200)


class AcomptePourSerializer(AcompteSaisieSerializer):
    employe = serializers.UUIDField()


class VersementSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=Acompte.Mode.choices)
    reference = serializers.CharField(required=False, allow_blank=True, default="", max_length=60)
    date = serializers.DateField(required=False, allow_null=True, default=None)


class PrimeSaisieSerializer(serializers.Serializer):
    employe = serializers.UUIDField()
    type = serializers.ChoiceField(choices=Prime.Type.choices)
    montant = serializers.DecimalField(**POSITIF)
    mois = serializers.DateField()
    motif = serializers.CharField(required=False, allow_blank=True, default="", max_length=200)


class RecapSerializer(serializers.Serializer):
    """Ce que la paie du mois retiendra (acomptes) ou ajoutera (primes)."""

    employe = serializers.UUIDField(source="employe.public_id")
    matricule = serializers.CharField(source="employe.matricule")
    nom = serializers.CharField(source="employe.__str__")
    magasin = serializers.CharField(source="employe.magasin.nom")
    salaire_base = serializers.DecimalField(**MONTANT, allow_null=True)
    acomptes = serializers.DecimalField(**MONTANT)
    primes = serializers.DecimalField(**MONTANT)


class MonEspaceSerializer(serializers.Serializer):
    employe = EmployeSerializer()
    conges = CongeSerializer(many=True)
    acomptes = AcompteSerializer(many=True)
    primes = PrimeSerializer(many=True, help_text="Primes validées.")
