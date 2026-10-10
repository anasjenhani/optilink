from rest_framework import serializers

from ..models import Banque, Depot, Magasin, Pays, Societe, Ville


class PaysSerializer(serializers.ModelSerializer):
    taux_tva = serializers.SlugRelatedField(
        slug_field="taux", many=True, read_only=True, help_text="Taux de TVA du pays."
    )

    class Meta:
        model = Pays
        fields = [
            "code_numerique",
            "code",
            "nom",
            "devise",
            "decimales",
            "indicatif_telephonique",
            "timbre_fiscal",
            "libelle_identifiant_prescripteur",
            "taux_tva",
        ]


class DepotSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)

    class Meta:
        model = Depot
        fields = ["id", "code", "nom", "adresse", "ville", "telephone", "type"]


class MagasinSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    societe = serializers.CharField(source="societe.raison_sociale", read_only=True)
    societe_id = serializers.UUIDField(source="societe.public_id", read_only=True)
    pays = PaysSerializer(read_only=True)
    depots = serializers.SerializerMethodField(help_text="Dépôts actifs du magasin.")
    depot_central = serializers.SerializerMethodField(
        help_text="Le magasin abrite le dépôt central : les achats de la société s'y saisissent."
    )
    type = serializers.SerializerMethodField(
        help_text="« depot » : site sans dépôt de vente (dépôt central seul)."
    )

    class Meta:
        model = Magasin
        fields = [
            "id",
            "code",
            "nom",
            "societe",
            "societe_id",
            "pays",
            "adresse",
            "code_postal",
            "ville",
            "telephone",
            "nombre_peniches",
            "type",
            "depot_central",
            "depots",
            "est_actif",
        ]

    def _actifs(self, magasin):
        return [d for d in magasin.depots.all() if d.est_actif]

    def get_depots(self, magasin) -> list[dict]:
        return DepotSerializer(self._actifs(magasin), many=True).data

    def get_depot_central(self, magasin) -> bool:
        return any(d.type == Depot.Type.CENTRAL for d in self._actifs(magasin))

    def get_type(self, magasin) -> str:
        if any(d.type == Depot.Type.VENTE for d in self._actifs(magasin)):
            return "magasin"
        return "depot"


class SocieteSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)

    class Meta:
        model = Societe
        fields = ["id", "code", "raison_sociale"]


class VilleSerializer(serializers.ModelSerializer):
    pays = serializers.CharField(source="pays.code", read_only=True)

    class Meta:
        model = Ville
        fields = ["id", "nom", "pays"]


class BanqueSerializer(serializers.ModelSerializer):
    pays = serializers.CharField(source="pays.code", read_only=True)

    class Meta:
        model = Banque
        fields = ["id", "code", "nom", "sigle", "pays"]
