from rest_framework import serializers

MONTANT = {"max_digits": 16, "decimal_places": 3}


class AlerteSerializer(serializers.Serializer):
    code = serializers.CharField()
    gravite = serializers.ChoiceField(choices=["haute", "moyenne", "info"])
    titre = serializers.CharField()
    detail = serializers.CharField()
    magasin = serializers.CharField(help_text="Vide pour une alerte de toute la société.")
    nombre = serializers.IntegerField()
    module = serializers.CharField(help_text="Onglet de l'application où traiter l'alerte.")
    ecran = serializers.CharField(help_text="Bouton de cet onglet.")


class LigneMagasinSerializer(serializers.Serializer):
    magasin = serializers.CharField()
    ca_ttc = serializers.DecimalField(**MONTANT)
    nombre = serializers.IntegerField()


class LigneJourSerializer(serializers.Serializer):
    jour = serializers.DateField()
    ca_ttc = serializers.DecimalField(**MONTANT)
    nombre = serializers.IntegerField()


class LigneVendeurSerializer(serializers.Serializer):
    vendeur = serializers.CharField()
    ca_ttc = serializers.DecimalField(**MONTANT)
    nombre = serializers.IntegerField()


class LigneFamilleSerializer(serializers.Serializer):
    famille = serializers.CharField()
    ca_ttc = serializers.DecimalField(**MONTANT)
    quantite = serializers.IntegerField()


class LigneEncaissementSerializer(serializers.Serializer):
    mode = serializers.CharField()
    montant = serializers.DecimalField(**MONTANT)


class SectionReportingSerializer(serializers.Serializer):
    devise = serializers.CharField()
    ca_ttc = serializers.DecimalField(**MONTANT)
    ca_ht = serializers.DecimalField(**MONTANT)
    avoirs_ttc = serializers.DecimalField(**MONTANT)
    ca_net_ttc = serializers.DecimalField(**MONTANT)
    nombre_ventes = serializers.IntegerField()
    panier_moyen = serializers.DecimalField(**MONTANT)
    par_magasin = LigneMagasinSerializer(many=True)
    par_jour = LigneJourSerializer(many=True)
    par_vendeur = LigneVendeurSerializer(many=True)
    par_famille = LigneFamilleSerializer(many=True)
    encaissements = LigneEncaissementSerializer(many=True)
