"""Fiche article (monture, verre, lentille, divers) : création et modification dans l'application.

La fiche reprend celle de l'ancien logiciel : en-tête (code, fournisseur, matière, famille…),
puis l'onglet « Détail prix » (prix d'achat, remise, TVA, marge, prix de vente) dans le pays du
magasin choisi, le stock par magasin et les mouvements.
"""

import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError as ErreurModele
from django.db import transaction
from django.db.models import Max, Sum
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from apps.achats.models import BonReception, Fournisseur, LigneReception
from apps.reseau.models import Magasin, TauxTva

from ..models import Article, Lentille, Monture, MouvementStock, PrixArticle, Verre

PREFIXE_CODE_INTERNE = "2"  # EAN-13 commençant par 2 : codes réservés à l'usage interne.


def cle_ean13(douze_chiffres):
    somme = sum(int(c) * (3 if i % 2 else 1) for i, c in enumerate(douze_chiffres))
    return str((10 - somme % 10) % 10)


def prochain_code_interne():
    """Code-barres EAN-13 interne suivant (2000000000015, 2000000000022…)."""
    codes = Article.objects.filter(
        code_barres__startswith=PREFIXE_CODE_INTERNE, code_barres__regex=r"^\d{13}$"
    ).aggregate(dernier=Max("code_barres"))["dernier"]
    suivant = int(codes[:12]) + 1 if codes else int(PREFIXE_CODE_INTERNE + "0" * 10 + "1")
    base = str(suivant)
    return base + cle_ean13(base)


def _texte(valeur):
    return None if valeur is None else str(valeur)


def prochaine_reference(famille):
    prefixe = {"monture": "MON", "verre": "VER", "lentille": "LEN"}.get(famille, "ART")
    numeros = [
        int(r.rsplit("-", 1)[1])
        for r in Article.objects.filter(reference__regex=rf"^{prefixe}-\d+$").values_list(
            "reference", flat=True
        )
    ]
    return f"{prefixe}-{max(numeros, default=0) + 1:06d}"


class MontureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Monture
        fields = [
            "categorie",
            "marque",
            "modele",
            "couleur",
            "couleur_verres",
            "matiere",
            "type",
            "forme",
            "genre",
            "tranche_age",
            "calibre",
            "pont",
            "branche",
        ]


class VerreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Verre
        fields = [
            "marque",
            "gamme",
            "geometrie",
            "indice",
            "matiere",
            "traitements",
            "photochromique",
            "teinte",
            "diametre",
            "diametre_commercial",
            "fabrication",
        ]


class LentilleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lentille
        fields = [
            "categorie",
            "marque",
            "modele",
            "couleur",
            "renouvellement",
            "type",
            "rayon",
            "diametre",
            "puissance",
            "cylindre",
            "axe",
            "addition",
            "lentilles_par_boite",
        ]


# Familles qui ont leurs caractéristiques à part ; le champ de la fiche porte le nom de la famille.
CARACTERISTIQUES = {
    Article.Famille.MONTURE: Monture,
    Article.Famille.VERRE: Verre,
    Article.Famille.LENTILLE: Lentille,
}


class PrixSerializer(serializers.Serializer):
    """Prix dans le pays du magasin choisi."""

    prix_achat_ht = serializers.DecimalField(
        max_digits=14, decimal_places=3, allow_null=True, required=False, min_value=Decimal(0)
    )
    taux_remise_achat = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        min_value=Decimal(0),
        max_value=Decimal(100),
    )
    taux_tva = serializers.DecimalField(max_digits=5, decimal_places=2)
    prix_vente_ttc = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal(0))


class FicheArticleSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    reference = serializers.CharField(
        max_length=40, required=False, allow_blank=True, help_text="Attribuée si vide."
    )
    libelle = serializers.CharField(
        max_length=200,
        required=False,
        allow_blank=True,
        help_text="Marque, modèle, couleur et taille si vide.",
    )
    code_barres = serializers.CharField(
        max_length=40,
        required=False,
        allow_blank=True,
        help_text="Code-barres ; un code interne EAN-13 est attribué aux montures si vide.",
    )
    fournisseur = serializers.SlugRelatedField(
        slug_field="public_id", queryset=Fournisseur.objects.all()
    )
    fournisseur_nom = serializers.CharField(source="fournisseur.nom", read_only=True)
    fournisseur_code = serializers.IntegerField(source="fournisseur.code", read_only=True)
    stockable = serializers.BooleanField(
        required=False, help_text="Vendu sur le stock du magasin (sinon commandé pour le client)."
    )
    monture = MontureSerializer(required=False)
    verre = VerreSerializer(required=False)
    lentille = LentilleSerializer(required=False)
    prix = serializers.SerializerMethodField()
    nouveau_prix = PrixSerializer(write_only=True, required=False, source="prix_saisi")
    dernier_achat = serializers.SerializerMethodField()
    stocks = serializers.SerializerMethodField()
    cree_par = serializers.SlugRelatedField(slug_field="username", read_only=True)

    class Meta:
        model = Article
        fields = [
            "id",
            "reference",
            "libelle",
            "famille",
            "code_barres",
            "fournisseur",
            "fournisseur_nom",
            "fournisseur_code",
            "reference_fournisseur",
            "est_actif",
            "stockable",
            "suivi_numero_serie",
            "promotion",
            "etui_special",
            "fodec",
            "observation",
            "monture",
            "verre",
            "lentille",
            "prix",
            "nouveau_prix",
            "dernier_achat",
            "stocks",
            "cree_par",
            "cree_le",
            "modifie_le",
        ]
        read_only_fields = ["cree_le", "modifie_le"]

    def to_representation(self, article):
        donnees = super().to_representation(article)
        donnees["stockable"] = not article.sur_commande
        return donnees

    @property
    def pays(self):
        return self.context["magasin"].pays

    def get_prix(self, article) -> dict | None:
        tarif = article.prix.filter(pays=self.pays).select_related("tva").first()
        if tarif is None:
            return None
        return {
            "prix_achat_ht": _texte(tarif.prix_achat_ht),
            "taux_remise_achat": _texte(tarif.taux_remise_achat),
            "taux_tva": _texte(tarif.tva.taux),
            "prix_vente_ttc": _texte(tarif.prix_vente_ttc),
        }

    def get_dernier_achat(self, article) -> dict | None:
        ligne = (
            LigneReception.objects.filter(
                article=article, non_conforme=False, bon__in=BonReception.objects.all()
            )
            .select_related("bon")
            .order_by("-bon__date_bl", "-id")
            .first()
        )
        if ligne is None:
            return None
        net = ligne.net_ht / ligne.quantite if ligne.quantite else ligne.net_ht
        return {
            "prix_achat_ht": _texte(ligne.prix_achat_ht),
            "taux_remise": _texte(ligne.taux_remise),
            "net_ht": _texte(net.quantize(Decimal("0.001"))),
            "date_bl": ligne.bon.date_bl,
            "numero_bl": ligne.bon.numero_bl,
        }

    def get_stocks(self, article) -> list:
        quantites = dict(
            MouvementStock.objects.filter(article=article)
            .values("depot")
            .annotate(total=Sum("quantite"))
            .values_list("depot", "total")
        )
        return [
            {"magasin": m.nom, "depot": d.nom, "stock": quantites.get(d.pk, 0)}
            for m in Magasin.objects.prefetch_related("depots").order_by("nom")
            for d in m.depots.all()
            if d.est_actif or quantites.get(d.pk)
        ]

    def validate_reference(self, valeur):
        valeur = valeur.strip()
        # Majuscules et minuscules comptent pour une même référence (CL.S.40235 = cl.s.40235).
        autre = Article.objects.filter(reference__iexact=valeur).exclude(pk=self._pk).first()
        if valeur and autre:
            raise serializers.ValidationError(
                f"Cette référence est déjà celle d'un autre article ({autre.reference})."
            )
        return valeur

    def validate_code_barres(self, valeur):
        valeur = valeur.strip()
        autre = Article.objects.filter(code_barres=valeur).exclude(pk=self._pk).first()
        if valeur and autre:
            raise serializers.ValidationError(
                f"Ce code est déjà celui de l'article {autre.reference}."
            )
        return valeur

    @property
    def _pk(self):
        return self.instance.pk if self.instance else None

    def validate(self, donnees):
        famille = donnees.get("famille", getattr(self.instance, "famille", None))
        if self.instance and "famille" in donnees and donnees["famille"] != self.instance.famille:
            raise serializers.ValidationError({"famille": "La famille d'un article ne change pas."})
        if "monture" in donnees and famille != Article.Famille.MONTURE:
            raise serializers.ValidationError({"monture": "Réservé aux montures."})
        for cle in ("verre", "lentille"):
            if cle in donnees and famille != cle:
                raise serializers.ValidationError(
                    {cle: f"Réservé aux articles de la famille {cle}."}
                )
        prix = donnees.get("prix_saisi")
        if prix is not None:
            taux = TauxTva.objects.filter(pays=self.pays, taux=prix["taux_tva"]).first()
            if taux is None:
                permis = ", ".join(
                    f"{t:g}" for t in self.pays.taux_tva.values_list("taux", flat=True)
                )
                raise serializers.ValidationError(
                    {"nouveau_prix": {"taux_tva": f"Taux du pays : {permis}."}}
                )
            prix["tva"] = taux
        return donnees

    @transaction.atomic
    def create(self, donnees):
        return self._enregistrer(Article(cree_par=self.context["request"].user), donnees)

    @transaction.atomic
    def update(self, article, donnees):
        return self._enregistrer(article, donnees)

    def _enregistrer(self, article, donnees):
        saisies = {cle: donnees.pop(cle, None) for cle in CARACTERISTIQUES}
        prix = donnees.pop("prix_saisi", None)
        if "stockable" in donnees:
            article.sur_commande = not donnees.pop("stockable")
        for champ, valeur in donnees.items():
            setattr(article, champ, valeur)
        if not article.reference:
            article.reference = prochaine_reference(article.famille)
        if not article.code_barres and article.famille == Article.Famille.MONTURE:
            article.code_barres = prochain_code_interne()

        fiche = None
        modele = CARACTERISTIQUES.get(article.famille)
        if modele is not None:
            fiche = getattr(article, article.famille, None) if article.pk else None
            fiche = fiche or modele()
            for champ, valeur in (saisies[article.famille] or {}).items():
                setattr(fiche, champ, valeur)
        if not article.libelle:
            article.libelle = self._libelle(article, fiche)
        self._sauver(article)
        if fiche is not None:
            fiche.article = article
            # Erreurs des montures sans clé, comme avant ; sous « verre » ou « lentille » sinon.
            self._sauver(fiche, None if modele is Monture else article.famille)
        if prix is not None:
            tarif = PrixArticle.objects.filter(article=article, pays=self.pays).first()
            tarif = tarif or PrixArticle(article=article, pays=self.pays)
            tarif.tva = prix["tva"]
            tarif.prix_vente_ttc = prix["prix_vente_ttc"]
            if "prix_achat_ht" in prix:
                tarif.prix_achat_ht = prix["prix_achat_ht"]
            if "taux_remise_achat" in prix:
                tarif.taux_remise_achat = prix["taux_remise_achat"]
            self._sauver(tarif, "nouveau_prix")
        return article

    @staticmethod
    def _libelle(article, fiche):
        if fiche is None:
            return article.reference
        if isinstance(fiche, Verre):
            indice = "" if fiche.indice is None else format(Decimal(fiche.indice).normalize(), "f")
            geometrie = fiche.get_geometrie_display()
            morceaux = [fiche.marque, fiche.gamme, geometrie, indice, fiche.traitements]
            return " ".join(m for m in morceaux if m)[:200] or article.reference
        if isinstance(fiche, Lentille):
            morceaux = [fiche.marque, fiche.modele, fiche.get_renouvellement_display()]
            return " ".join(m for m in morceaux if m)[:200] or article.reference
        taille = f"{fiche.calibre}" + (f"□{fiche.pont}" if fiche.pont else "")
        morceaux = [fiche.marque, fiche.modele, fiche.couleur, taille if fiche.calibre else ""]
        return " ".join(m for m in morceaux if m)[:200] or article.reference

    @staticmethod
    def _sauver(objet, cle=None):
        try:
            objet.full_clean()
        except ErreurModele as erreur:
            details = erreur.message_dict if hasattr(erreur, "message_dict") else erreur.messages
            raise serializers.ValidationError({cle: details} if cle else details) from erreur
        objet.save()


MAGASIN = OpenApiParameter(
    "magasin",
    OpenApiTypes.UUID,
    required=True,
    description="Magasin dont le pays donne les prix (et la TVA)",
)


@extend_schema_view(
    retrieve=extend_schema(parameters=[MAGASIN]),
    create=extend_schema(parameters=[MAGASIN]),
    partial_update=extend_schema(parameters=[MAGASIN]),
)
class FicheArticleViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Fiche article à créer ou modifier (toutes familles), prix dans le pays du magasin.

    Pas de suppression : un article servi par des ventes ou du stock se désactive (est_actif).
    """

    serializer_class = FicheArticleSerializer
    lookup_field = "public_id"
    http_method_names = ["get", "post", "patch"]
    permissions_requises = {
        "retrieve": "stock.view_article",
        "mouvements": ["stock.view_article", "stock.view_mouvementstock"],
        "suggestions": "stock.view_article",
        "create": ["stock.add_article", "stock.add_prixarticle"],
        "partial_update": [
            "stock.change_article",
            "stock.add_prixarticle",
            "stock.change_prixarticle",
        ],
    }

    def get_queryset(self):
        return Article.objects.select_related(
            "monture", "verre", "lentille", "fournisseur", "cree_par"
        )

    def get_serializer_context(self):
        contexte = super().get_serializer_context()
        if getattr(self, "swagger_fake_view", False):
            contexte["magasin"] = None  # Génération du schéma, sans requête réelle.
        else:
            try:
                magasin = uuid.UUID(self.request.query_params.get("magasin", ""))
            except ValueError:
                raise NotFound("Préciser le magasin (?magasin=).") from None
            contexte["magasin"] = get_object_or_404(
                Magasin.objects.select_related("pays"), public_id=magasin
            )
        return contexte

    @extend_schema(responses=OpenApiTypes.OBJECT)
    @action(detail=False)
    def suggestions(self, request):
        """Valeurs déjà saisies sur les montures, proposées à la saisie (marques, formes…)."""
        champs = ["marque", "modele", "forme", "couleur", "couleur_verres"]
        return Response(
            {
                champ: list(
                    Monture.objects.exclude(**{champ: ""})
                    .order_by(champ)
                    .values_list(champ, flat=True)
                    .distinct()[:500]
                )
                for champ in champs
            }
        )

    @extend_schema(responses=OpenApiTypes.OBJECT)
    @action(detail=True)
    def mouvements(self, request, public_id=None):
        """Détail des mouvements de l'article dans les magasins accessibles, les plus récents."""
        article = self.get_object()
        mouvements = (
            MouvementStock.objects.filter(article=article)
            .select_related("magasin", "depot", "utilisateur")
            .order_by("-horodatage")[:200]
        )
        return Response(
            [
                {
                    "horodatage": m.horodatage,
                    "magasin": m.magasin.nom,
                    "depot": m.depot.nom,
                    "type": m.get_type_display(),
                    "quantite": m.quantite,
                    "reference": m.reference,
                    "utilisateur": m.utilisateur.username if m.utilisateur else "",
                }
                for m in mouvements
            ]
        )
