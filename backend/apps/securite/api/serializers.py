from rest_framework import serializers


class ConnexionSerializer(serializers.Serializer):
    identifiant = serializers.CharField(max_length=150)
    mot_de_passe = serializers.CharField(max_length=128, trim_whitespace=False)


class CodeSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=16)


class UtilisateurSessionSerializer(serializers.Serializer):
    identifiant = serializers.CharField()
    nom_complet = serializers.CharField()
    permissions = serializers.ListField(child=serializers.CharField())


class EtatSessionSerializer(serializers.Serializer):
    authentifie = serializers.BooleanField()
    mfa = serializers.ChoiceField(
        choices=["verifiee", "a_verifier", "a_activer", "non_requise"], allow_null=True
    )
    utilisateur = UtilisateurSessionSerializer(allow_null=True)


class ActivationMfaSerializer(serializers.Serializer):
    uri = serializers.CharField(help_text="URI otpauth:// à scanner")
    cle = serializers.CharField(help_text="Clé à saisir à la main si le scan est impossible")
    qr_svg = serializers.CharField(help_text="QR code au format SVG")


class ConfirmationMfaSerializer(serializers.Serializer):
    codes_secours = serializers.ListField(child=serializers.CharField())
    session = EtatSessionSerializer()
