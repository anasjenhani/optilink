from rest_framework import serializers

from ..models import Etape
from ..suivi import LIVREE, type_de_commande

ETATS = [*Etape.choices, (LIVREE, "Livrée")]
LIBELLES = dict(ETATS)


class ClientLigneSerializer(serializers.Serializer):
    numero = serializers.IntegerField()
    nom = serializers.CharField()
    telephone = serializers.CharField()


def _client(vente):
    client = vente.client
    if client is None:
        return None
    return {"numero": client.numero, "nom": str(client), "telephone": client.telephone}


class SuiviSerializer(serializers.Serializer):
    """Une commande au suivi qualité."""

    id = serializers.UUIDField(source="public_id")
    numero = serializers.CharField(help_text="N° de visite (ticket).")
    magasin = serializers.CharField(source="magasin.code")
    cree_le = serializers.DateTimeField()
    client = serializers.SerializerMethodField()
    peniche = serializers.IntegerField(allow_null=True)
    monture = serializers.SerializerMethodField(help_text="Référence et code-barres de la monture.")
    type = serializers.SerializerMethodField(help_text="verre, lentille ou autre.")
    stockable = serializers.SerializerMethodField(
        help_text="Faux si un article est commandé pour le client (verres…)."
    )
    etat = serializers.SerializerMethodField()
    etat_libelle = serializers.SerializerMethodField()
    observation = serializers.SerializerMethodField(help_text="Dernière observation saisie.")
    livraison_prevue_le = serializers.DateField(allow_null=True)
    reste_a_payer = serializers.DecimalField(max_digits=14, decimal_places=3)

    def get_client(self, vente) -> ClientLigneSerializer(allow_null=True):
        return _client(vente)

    def get_monture(self, vente) -> dict | None:
        for ligne in vente.lignes.all():
            if ligne.article.famille == "monture":
                return {
                    "reference": ligne.article.reference,
                    "code_barres": ligne.article.code_barres,
                }
        return None

    def get_type(self, vente) -> str:
        return type_de_commande(vente)

    def get_stockable(self, vente) -> bool:
        return not any(ligne.article.sur_commande for ligne in vente.lignes.all())

    def get_etat(self, vente) -> str:
        return self.context["etats"][vente.pk]

    def get_etat_libelle(self, vente) -> str:
        return LIBELLES[self.context["etats"][vente.pk]]

    def get_observation(self, vente) -> str:
        etapes = [e for e in vente.etapes.all() if e.observation]
        return etapes[-1].observation if etapes else ""


class EtapeSaisieSerializer(serializers.Serializer):
    etape = serializers.ChoiceField(choices=Etape.choices)
    observation = serializers.CharField(required=False, allow_blank=True, max_length=300)


class LigneJourneeSerializer(serializers.Serializer):
    id = serializers.UUIDField(source="public_id")
    numero = serializers.CharField()
    cree_le = serializers.DateTimeField()
    client = serializers.SerializerMethodField()
    vendeur = serializers.SerializerMethodField()
    total_ttc = serializers.DecimalField(max_digits=14, decimal_places=3)
    regle = serializers.DecimalField(max_digits=14, decimal_places=3)
    pec_client = serializers.SerializerMethodField(
        help_text="Organisme de prise en charge du client (CNAM, assurance, mutuelle)."
    )
    pec_visite = serializers.SerializerMethodField(help_text="Part prise en charge sur la visite.")
    reste = serializers.SerializerMethodField()
    soldee = serializers.SerializerMethodField()
    livree = serializers.SerializerMethodField()
    commande = serializers.SerializerMethodField(help_text="Vrai pour une commande (acompte).")
    facture = serializers.SerializerMethodField()

    def get_client(self, vente) -> ClientLigneSerializer(allow_null=True):
        return _client(vente)

    def get_vendeur(self, vente) -> str:
        return vente.vendeur.get_full_name() or vente.vendeur.get_username()

    def get_pec_client(self, vente) -> str | None:
        organisme = vente.client.organisme if vente.client else None
        return organisme.nom if organisme else None

    def get_pec_visite(self, vente) -> str:
        return str(vente.pris_en_charge)

    def get_reste(self, vente) -> str:
        return str(vente.total_ttc - vente.regle - vente.pris_en_charge)

    def get_soldee(self, vente) -> bool:
        return vente.regle + vente.pris_en_charge >= vente.total_ttc

    def get_livree(self, vente) -> bool:
        return vente.statut == vente.Statut.LIVREE

    def get_commande(self, vente) -> bool:
        return vente.statut == vente.Statut.EN_COMMANDE or vente.peniche is not None

    def get_facture(self, vente) -> str | None:
        facture = getattr(vente, "facture", None) or vente.facture_groupee
        return facture.numero if facture else None


class ModeMontantSerializer(serializers.Serializer):
    mode = serializers.CharField()
    montant = serializers.DecimalField(max_digits=14, decimal_places=3)


class JourneeSerializer(serializers.Serializer):
    date = serializers.DateField()
    magasin = serializers.CharField()
    devise = serializers.CharField()
    nombre_ventes = serializers.IntegerField()
    total_ventes = serializers.DecimalField(max_digits=14, decimal_places=3)
    regle_sur_ventes = serializers.DecimalField(max_digits=14, decimal_places=3)
    pris_en_charge = serializers.DecimalField(
        max_digits=14, decimal_places=3, help_text="Part des organismes sur les ventes du jour."
    )
    reste_sur_ventes = serializers.DecimalField(max_digits=14, decimal_places=3)
    encaisse = serializers.DecimalField(
        max_digits=14, decimal_places=3, help_text="Tous les règlements reçus ce jour-là."
    )
    encaisse_par_mode = ModeMontantSerializer(many=True)
    ventes = LigneJourneeSerializer(many=True)
