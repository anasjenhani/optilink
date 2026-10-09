"""Liste, fiche et historique des visites ; reçus de règlement ; reste dû par vendeur."""

import django_filters
from django.db.models import Q
from rest_framework import serializers

from ..models import Paiement, Vente
from ..suivi import etat
from .serializers import VenteSerializer
from .suivi import LIBELLES


class VenteFiltre(django_filters.FilterSet):
    """Recherche de visites : magasin, période, client, vendeur, statut, facturée ou non."""

    numero = django_filters.CharFilter()
    statut = django_filters.ChoiceFilter(choices=Vente.Statut.choices)
    peniche = django_filters.NumberFilter()
    magasin__public_id = django_filters.UUIDFilter()
    magasin = django_filters.UUIDFilter(field_name="magasin__public_id")
    client = django_filters.UUIDFilter(field_name="client__public_id")
    vendeur = django_filters.CharFilter(field_name="vendeur__username")
    du = django_filters.DateFilter(field_name="cree_le__date", lookup_expr="gte")
    au = django_filters.DateFilter(field_name="cree_le__date", lookup_expr="lte")
    facturee = django_filters.BooleanFilter(method="filtrer_facturee")
    recherche = django_filters.CharFilter(
        method="chercher", help_text="N° de visite, nom, prénom, téléphone ou n° de fiche client."
    )

    class Meta:
        model = Vente
        fields = []

    def filtrer_facturee(self, queryset, name, valeur):
        # Facture de la vente seule, ou facture groupée / récapitulative du mois.
        facturee = Q(facture__isnull=False) | Q(facture_groupee__isnull=False)
        if valeur is None:
            return queryset
        return queryset.filter(facturee) if valeur else queryset.exclude(facturee)

    def chercher(self, queryset, name, valeur):
        valeur = valeur.strip()
        if not valeur:
            return queryset
        telephone = Q(client__telephone__icontains=valeur) | Q(
            client__telephone_2__icontains=valeur
        )
        if valeur.isdigit():
            # Un nombre seul : n° de fiche client, fin du n° de visite (« 12 » → …-000012),
            # ou morceau de téléphone à partir de 4 chiffres.
            condition = Q(client__numero=int(valeur)) | Q(numero__endswith=valeur.zfill(6))
            return queryset.filter(condition | telephone if len(valeur) >= 4 else condition)
        return queryset.filter(
            Q(numero__icontains=valeur)
            | Q(client__nom__icontains=valeur)
            | Q(client__prenom__icontains=valeur)
            | telephone
        )


def _nom(utilisateur):
    if utilisateur is None:
        return ""
    return utilisateur.get_full_name() or utilisateur.get_username()


class VerreFicheSerializer(serializers.Serializer):
    """Verre commandé au fournisseur pour une ligne de la visite."""

    id = serializers.IntegerField(source="pk", help_text="À donner pour déclarer une casse.")
    ligne = serializers.IntegerField(source="ligne_vente_id")
    libelle = serializers.CharField(source="ligne_vente.libelle")
    commande_fournisseur = serializers.CharField(source="commande.numero")
    fournisseur = serializers.CharField(source="commande.fournisseur.nom")
    statut = serializers.CharField(source="commande.statut")
    recu_le = serializers.DateTimeField(source="commande.recue_le", allow_null=True)
    casse = serializers.SerializerMethodField(help_text="Cause de la casse, si le verre est cassé.")

    def get_casse(self, ligne) -> str | None:
        casse = getattr(ligne, "casse", None)
        return casse.get_cause_display() if casse else None


class EtapeFicheSerializer(serializers.Serializer):
    etape = serializers.CharField()
    etape_libelle = serializers.CharField(source="get_etape_display")
    observation = serializers.CharField()
    le = serializers.DateTimeField()
    par = serializers.SerializerMethodField()

    def get_par(self, etape) -> str:
        return _nom(etape.par)


class PaiementFicheSerializer(serializers.Serializer):
    mode = serializers.CharField()
    mode_libelle = serializers.CharField(source="get_mode_display")
    montant = serializers.DecimalField(max_digits=14, decimal_places=3)
    recu_le = serializers.DateTimeField()
    recu_par = serializers.SerializerMethodField()
    reference = serializers.CharField()
    statut = serializers.CharField()
    statut_libelle = serializers.CharField(source="get_statut_display")

    def get_recu_par(self, paiement) -> str:
        return _nom(paiement.recu_par)


class PecFicheSerializer(serializers.Serializer):
    organisme = serializers.CharField(source="organisme.nom")
    montant = serializers.DecimalField(max_digits=14, decimal_places=3)
    numero_dossier = serializers.CharField()
    statut_libelle = serializers.CharField(source="get_statut_display")


class AvoirFicheSerializer(serializers.Serializer):
    numero = serializers.CharField()
    cree_le = serializers.DateTimeField()
    annulation = serializers.BooleanField()
    motif = serializers.CharField()
    total_ttc = serializers.DecimalField(max_digits=14, decimal_places=3)
    montant_rembourse = serializers.DecimalField(max_digits=14, decimal_places=3)


class ClientFicheSerializer(serializers.Serializer):
    id = serializers.UUIDField(source="public_id")
    numero = serializers.IntegerField()
    nom = serializers.CharField(source="__str__")
    telephone = serializers.CharField()
    organisme = serializers.CharField(source="organisme.nom", allow_null=True, default=None)
    numero_affilie = serializers.CharField()


class FicheVisiteSerializer(VenteSerializer):
    """Tout ce qu'on sait d'une visite : articles, règlements, PEC, suivi, verres, avoirs."""

    magasin_nom = serializers.CharField(source="magasin.nom", read_only=True)
    vendeur_nom = serializers.SerializerMethodField()
    client_fiche = serializers.SerializerMethodField()
    etat = serializers.SerializerMethodField(help_text="Étape du suivi (commandes seulement).")
    etat_libelle = serializers.SerializerMethodField()
    reglements = serializers.SerializerMethodField()
    prises_en_charge = serializers.SerializerMethodField()
    etapes = serializers.SerializerMethodField()
    verres_commandes = serializers.SerializerMethodField()
    avoirs = serializers.SerializerMethodField()

    class Meta(VenteSerializer.Meta):
        fields = [
            *VenteSerializer.Meta.fields,
            "magasin_nom",
            "vendeur_nom",
            "client_fiche",
            "etat",
            "etat_libelle",
            "reglements",
            "prises_en_charge",
            "etapes",
            "verres_commandes",
            "avoirs",
        ]

    def get_vendeur_nom(self, vente) -> str:
        return _nom(vente.vendeur)

    def get_client_fiche(self, vente) -> ClientFicheSerializer(allow_null=True):
        return ClientFicheSerializer(vente.client).data if vente.client else None

    def _commande(self, vente):
        return vente.statut == Vente.Statut.EN_COMMANDE or vente.peniche is not None

    def get_etat(self, vente) -> str | None:
        return etat(vente) if self._commande(vente) else None

    def get_etat_libelle(self, vente) -> str | None:
        return LIBELLES[etat(vente)] if self._commande(vente) else None

    def get_reglements(self, vente) -> PaiementFicheSerializer(many=True):
        return PaiementFicheSerializer(vente.paiements.all(), many=True).data

    def get_prises_en_charge(self, vente) -> PecFicheSerializer(many=True):
        return PecFicheSerializer(vente.prises_en_charge.all(), many=True).data

    def get_etapes(self, vente) -> EtapeFicheSerializer(many=True):
        return EtapeFicheSerializer(vente.etapes.all(), many=True).data

    def get_verres_commandes(self, vente) -> VerreFicheSerializer(many=True):
        from apps.achats.models import LigneCommandeFournisseur

        lignes = (
            LigneCommandeFournisseur.objects.filter(ligne_vente__vente=vente)
            .select_related("ligne_vente", "commande__fournisseur", "casse")
            .order_by("pk")
        )
        return VerreFicheSerializer(lignes, many=True).data

    def get_avoirs(self, vente) -> AvoirFicheSerializer(many=True):
        return AvoirFicheSerializer(vente.avoirs.all(), many=True).data


class RecuSerializer(serializers.Serializer):
    """Reçu d'un règlement, à réimprimer."""

    id = serializers.IntegerField(source="pk")
    recu_le = serializers.DateTimeField()
    mode = serializers.CharField()
    mode_libelle = serializers.CharField(source="get_mode_display")
    montant = serializers.DecimalField(max_digits=14, decimal_places=3)
    recu_par = serializers.SerializerMethodField()
    vente = serializers.UUIDField(source="vente.public_id")
    vente_numero = serializers.CharField(source="vente.numero")
    devise = serializers.CharField(source="vente.devise")
    total_ttc = serializers.DecimalField(source="vente.total_ttc", max_digits=14, decimal_places=3)
    deja_regle = serializers.SerializerMethodField(
        help_text="Réglé sur la visite avant ce règlement."
    )
    reste_apres = serializers.SerializerMethodField(
        help_text="Reste dû par le client juste après ce règlement (hors PEC)."
    )
    client = serializers.SerializerMethodField()
    magasin = serializers.SerializerMethodField()

    def _avant(self, paiement):
        return sum(
            (
                p.montant
                for p in paiement.vente.paiements.all()
                if (p.recu_le, p.pk) < (paiement.recu_le, paiement.pk)
            ),
            paiement.montant * 0,
        )

    def get_deja_regle(self, paiement) -> str:
        return str(self._avant(paiement))

    def get_reste_apres(self, paiement) -> str:
        vente = paiement.vente
        return str(
            vente.total_ttc - vente.pris_en_charge - self._avant(paiement) - paiement.montant
        )

    def get_recu_par(self, paiement) -> str:
        return _nom(paiement.recu_par)

    def get_client(self, paiement) -> dict | None:
        client = paiement.vente.client
        if client is None:
            return None
        return {"numero": client.numero, "nom": str(client), "telephone": client.telephone}

    def get_magasin(self, paiement) -> dict:
        magasin = paiement.vente.magasin
        societe = magasin.societe
        return {
            "nom": magasin.nom,
            "adresse": " ".join(
                filter(None, [magasin.adresse, magasin.code_postal, magasin.ville])
            ),
            "telephone": magasin.telephone,
            "societe": societe.raison_sociale,
            "matricule_fiscal": societe.matricule_fiscal,
        }


def recus(ventes):
    return (
        Paiement.objects.filter(vente__in=ventes)
        .select_related("vente__magasin__societe", "vente__client", "recu_par")
        .prefetch_related("vente__paiements", "vente__prises_en_charge")
        .order_by("-recu_le", "-pk")
    )


class ResteVendeurSerializer(serializers.Serializer):
    vendeur = serializers.CharField()
    vendeur_nom = serializers.CharField()
    nombre = serializers.IntegerField(help_text="Commandes en cours avec un reste dû.")
    total_ttc = serializers.DecimalField(max_digits=14, decimal_places=3)
    reste = serializers.DecimalField(max_digits=14, decimal_places=3)
    commandes = serializers.ListField(child=serializers.DictField())


def reste_par_vendeur(ventes):
    """Commandes en cours non soldées, regroupées par vendeur, le plus gros reste d'abord."""
    groupes = {}
    for vente in ventes:
        reste = vente.reste_a_payer
        if reste <= 0:
            continue
        cle = vente.vendeur.get_username()
        groupe = groupes.setdefault(
            cle,
            {
                "vendeur": cle,
                "vendeur_nom": _nom(vente.vendeur),
                "nombre": 0,
                "total_ttc": 0,
                "reste": 0,
                "commandes": [],
            },
        )
        groupe["nombre"] += 1
        groupe["total_ttc"] += vente.total_ttc
        groupe["reste"] += reste
        groupe["commandes"].append(
            {
                "id": str(vente.public_id),
                "numero": vente.numero,
                "cree_le": vente.cree_le.isoformat(),
                "client": str(vente.client) if vente.client else None,
                "telephone": vente.client.telephone if vente.client else "",
                "total_ttc": str(vente.total_ttc),
                "reste": str(reste),
            }
        )
    return sorted(groupes.values(), key=lambda g: g["reste"], reverse=True)
