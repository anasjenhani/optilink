from decimal import Decimal

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from ..models import (
    Avoir,
    Devis,
    Facture,
    Lentilles,
    LigneAvoir,
    LigneDevis,
    LigneVente,
    Lunette,
    Paiement,
    Vente,
)


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
    lunette = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=0,
        help_text="Rang de la lunette (dans ``lunettes``, à partir de 0) qui contient l'article.",
    )
    lentilles = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=0,
        help_text="Rang des lentilles (dans ``lentilles``, à partir de 0) de l'article.",
    )
    role = serializers.ChoiceField(
        choices=LigneVente.Role.choices,
        required=False,
        allow_blank=True,
        help_text="Place de l'article dans la lunette ou les lentilles.",
    )
    numero_lot = serializers.CharField(required=False, allow_blank=True, max_length=40)
    date_peremption = serializers.DateField(required=False, allow_null=True)


def _mesure_mm(aide):
    return serializers.DecimalField(
        max_digits=4,
        decimal_places=1,
        min_value=Decimal("0"),
        max_value=Decimal("60"),
        required=False,
        allow_null=True,
        help_text=aide,
    )


class LunetteSaisieSerializer(serializers.Serializer):
    vision = serializers.ChoiceField(
        choices=Lunette.Vision.choices, required=False, allow_blank=True
    )
    solaire = serializers.BooleanField(default=False)
    inadaptation = serializers.BooleanField(default=False)
    prescription = serializers.UUIDField(
        required=False, allow_null=True, help_text="Ordonnance du client d'où vient la correction."
    )
    oeil_directeur = serializers.ChoiceField(
        choices=Lunette.Oeil.choices, required=False, allow_blank=True
    )
    ecart_d = _mesure_mm("Demi-écart de loin, œil droit (mm).")
    ecart_g = _mesure_mm("Demi-écart de loin, œil gauche (mm).")
    ecart_pres_d = _mesure_mm("Demi-écart de près, œil droit (mm).")
    ecart_pres_g = _mesure_mm("Demi-écart de près, œil gauche (mm).")
    hauteur_d = _mesure_mm("Hauteur de montage, œil droit (mm).")
    hauteur_g = _mesure_mm("Hauteur de montage, œil gauche (mm).")
    observation = serializers.CharField(required=False, allow_blank=True, max_length=1000)
    client_absent = serializers.BooleanField(default=False)


class LentillesSaisieSerializer(serializers.Serializer):
    prescription = serializers.UUIDField(
        required=False, allow_null=True, help_text="Ordonnance de lentilles du client."
    )
    observation = serializers.CharField(required=False, allow_blank=True, max_length=1000)


class LentilleOeilSerializer(serializers.Serializer):
    libelle = serializers.CharField()
    quantite = serializers.IntegerField()
    numero_lot = serializers.CharField()
    date_peremption = serializers.DateField(allow_null=True)
    total_ttc = serializers.DecimalField(max_digits=14, decimal_places=3)


class LentillesSerializer(serializers.ModelSerializer):
    prescription = serializers.UUIDField(
        source="prescription.public_id", read_only=True, default=None
    )
    droite = serializers.SerializerMethodField()
    gauche = serializers.SerializerMethodField()
    total_ttc = serializers.SerializerMethodField()

    class Meta:
        model = Lentilles
        fields = ["numero", "prescription", "observation", "droite", "gauche", "total_ttc"]

    def _oeil(self, lentilles, role):
        ligne = next((x for x in lentilles.lignes.all() if x.role == role), None)
        return LentilleOeilSerializer(ligne).data if ligne else None

    @extend_schema_field(LentilleOeilSerializer(allow_null=True))
    def get_droite(self, lentilles):
        return self._oeil(lentilles, LigneVente.Role.LENTILLE_D)

    @extend_schema_field(LentilleOeilSerializer(allow_null=True))
    def get_gauche(self, lentilles):
        return self._oeil(lentilles, LigneVente.Role.LENTILLE_G)

    @extend_schema_field(OpenApiTypes.DECIMAL)
    def get_total_ttc(self, lentilles):
        return str(sum((x.total_ttc for x in lentilles.lignes.all()), Decimal("0")))


class LentillesClientSerializer(LentillesSerializer):
    """Lentilles dans l'historique d'un client : avec leur visite."""

    id = serializers.SerializerMethodField(help_text="N° : n° de visite / L rang.")
    vente = serializers.UUIDField(source="vente.public_id", read_only=True)
    vente_numero = serializers.CharField(source="vente.numero", read_only=True)
    date = serializers.DateTimeField(source="vente.cree_le", read_only=True)
    peniche = serializers.IntegerField(source="vente.peniche", read_only=True)

    class Meta(LentillesSerializer.Meta):
        fields = [
            "id",
            "vente",
            "vente_numero",
            "date",
            "peniche",
            *LentillesSerializer.Meta.fields,
        ]

    def get_id(self, lentilles) -> str:
        return f"{lentilles.vente.numero}/L{lentilles.numero}"


class LunetteSerializer(serializers.ModelSerializer):
    vision_libelle = serializers.CharField(source="get_vision_display", read_only=True)
    prescription = serializers.UUIDField(
        source="prescription.public_id", read_only=True, default=None
    )
    monture = serializers.SerializerMethodField()
    verre_d = serializers.SerializerMethodField()
    verre_g = serializers.SerializerMethodField()
    supplements_d = serializers.SerializerMethodField()
    supplements_g = serializers.SerializerMethodField()

    class Meta:
        model = Lunette
        fields = [
            "numero",
            "vision",
            "vision_libelle",
            "solaire",
            "inadaptation",
            "prescription",
            "oeil_directeur",
            "ecart_d",
            "ecart_g",
            "ecart_pres_d",
            "ecart_pres_g",
            "hauteur_d",
            "hauteur_g",
            "observation",
            "client_absent",
            "monture",
            "verre_d",
            "verre_g",
            "supplements_d",
            "supplements_g",
        ]

    def _libelles(self, lunette, role):
        return [ligne.libelle for ligne in lunette.lignes.all() if ligne.role == role]

    def get_monture(self, lunette) -> str | None:
        return next(iter(self._libelles(lunette, LigneVente.Role.MONTURE)), None)

    def get_verre_d(self, lunette) -> str | None:
        return next(iter(self._libelles(lunette, LigneVente.Role.VERRE_D)), None)

    def get_verre_g(self, lunette) -> str | None:
        return next(iter(self._libelles(lunette, LigneVente.Role.VERRE_G)), None)

    def get_supplements_d(self, lunette) -> list[str]:
        return self._libelles(lunette, LigneVente.Role.SUPPLEMENT_D)

    def get_supplements_g(self, lunette) -> list[str]:
        return self._libelles(lunette, LigneVente.Role.SUPPLEMENT_G)


class LunetteClientSerializer(LunetteSerializer):
    """Lunette dans l'historique d'un client : avec sa visite."""

    id = serializers.SerializerMethodField(help_text="N° de lunette : n° de visite / rang.")
    vente = serializers.UUIDField(source="vente.public_id", read_only=True)
    vente_numero = serializers.CharField(source="vente.numero", read_only=True)
    date = serializers.DateTimeField(source="vente.cree_le", read_only=True)
    magasin = serializers.CharField(source="vente.magasin.code", read_only=True)
    peniche = serializers.IntegerField(source="vente.peniche", read_only=True)
    statut = serializers.CharField(source="vente.statut", read_only=True)

    class Meta(LunetteSerializer.Meta):
        fields = [
            "id",
            "vente",
            "vente_numero",
            "date",
            "magasin",
            "peniche",
            "statut",
            *LunetteSerializer.Meta.fields,
        ]

    def get_id(self, lunette) -> str:
        return f"{lunette.vente.numero}/{lunette.numero}"


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
    peniche = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1,
        help_text="Commande : n° de la péniche libre où le vendeur range l'équipement.",
    )
    lunettes = LunetteSaisieSerializer(
        many=True, required=False, help_text="Paires de lunettes ; leurs articles sont dans lignes."
    )
    lentilles = LentillesSaisieSerializer(
        many=True, required=False, help_text="Lentilles droite et gauche ; articles dans lignes."
    )


class ReglementSerializer(serializers.Serializer):
    paiements = PaiementSaisieSerializer(many=True, allow_empty=False)


class LivraisonSerializer(serializers.Serializer):
    paiements = PaiementSaisieSerializer(
        many=True, required=False, help_text="Solde encaissé à la livraison, s'il reste dû."
    )


class LigneVenteSerializer(serializers.ModelSerializer):
    article = serializers.UUIDField(source="article.public_id", read_only=True)
    lunette = serializers.IntegerField(
        source="lunette.numero", read_only=True, default=None, help_text="N° de la lunette."
    )
    lentilles = serializers.IntegerField(
        source="lentilles.numero", read_only=True, default=None, help_text="N° des lentilles."
    )
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
            "lunette",
            "lentilles",
            "role",
            "numero_lot",
            "date_peremption",
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
    pris_en_charge = serializers.DecimalField(
        max_digits=14,
        decimal_places=3,
        read_only=True,
        help_text="Part de la CNAM, d'une assurance ou d'une mutuelle (hors refus).",
    )
    reste_a_payer = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    facture = serializers.SerializerMethodField(help_text="N° de la facture, si elle est émise.")
    verres = serializers.SerializerMethodField(
        help_text="Verres commandés au fournisseur : a_commander, commandes ou recus (null sinon)."
    )
    lignes = LigneVenteSerializer(many=True, read_only=True)
    lunettes = LunetteSerializer(many=True, read_only=True)
    lentilles = LentillesSerializer(many=True, read_only=True)
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
            "pris_en_charge",
            "reste_a_payer",
            "statut",
            "livraison_prevue_le",
            "peniche",
            "livree_le",
            "verres",
            "facture",
            "lignes",
            "lunettes",
            "lentilles",
            "paiements",
        ]

    def get_client(self, vente) -> dict | None:
        resume = client_resume(vente.client)
        if resume is not None:
            # Organisme de prise en charge proposé d'office quand on saisit une PEC.
            organisme = vente.client.organisme
            resume["organisme"] = str(organisme.public_id) if organisme else None
        return resume

    def get_facture(self, vente) -> str | None:
        facture = getattr(vente, "facture", None)
        return facture.numero if facture else None

    def get_verres(self, vente) -> str | None:
        from apps.achats.services import etat_verres

        if vente.statut != Vente.Statut.EN_COMMANDE:
            return None
        return etat_verres(vente)


def client_resume(client):
    if client is None:
        return None
    return {
        "id": str(client.public_id),
        "nom": str(client),
        "societe": client.societe,
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
        # Tel qu'imprimé à l'émission, même si la fiche client a changé depuis.
        return {
            "id": str(facture.client.public_id),
            "nom": facture.client_nom,
            "adresse": facture.client_adresse,
            "matricule_fiscal": facture.client_matricule_fiscal,
        }


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
    peniche = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1,
        help_text="Commande : n° de la péniche libre où le vendeur range l'équipement.",
    )


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
