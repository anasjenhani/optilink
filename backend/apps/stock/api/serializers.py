from django.forms.models import model_to_dict
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.reseau.models import Magasin

from ..models import Article, Lentille, Monture, MouvementStock, Verre


def _signe(valeur):
    return f"+{valeur}" if valeur > 0 else str(valeur)


def decrire(fiche):
    """Résumé d'une fiche sur une ligne, dans la notation des opticiens."""
    if fiche is None:
        return ""
    morceaux = [" ".join(filter(None, [fiche.marque, getattr(fiche, "modele", "")]))]
    if isinstance(fiche, Monture):
        mesures = ""
        if fiche.calibre and fiche.pont:
            mesures = f"{fiche.calibre}□{fiche.pont}" + (
                f"-{fiche.branche}" if fiche.branche else ""
            )
        morceaux += [
            fiche.couleur,
            mesures,
            fiche.get_matiere_display() if fiche.matiere else "",
            fiche.get_type_display() if fiche.type else "",
            "" if fiche.categorie == Monture.Categorie.OPTIQUE else fiche.get_categorie_display(),
        ]
    elif isinstance(fiche, Verre):
        morceaux = [
            " ".join(filter(None, [fiche.marque, fiche.gamme])),
            fiche.get_geometrie_display(),
            f"indice {fiche.indice}" if fiche.indice else "",
            fiche.get_matiere_display() if fiche.matiere else "",
            fiche.traitements,
            "photochromique" if fiche.photochromique else "",
        ]
    elif isinstance(fiche, Lentille):
        puissance = ""
        if fiche.puissance is not None:
            puissance = _signe(fiche.puissance)
            if fiche.cylindre:
                puissance += f" ({_signe(fiche.cylindre)} à {fiche.axe}°)"
            if fiche.addition:
                puissance += f" add {_signe(fiche.addition)}"
        morceaux += [
            fiche.get_renouvellement_display(),
            fiche.get_type_display(),
            f"R {fiche.rayon}" if fiche.rayon else "",
            f"Ø {fiche.diametre}" if fiche.diametre else "",
            puissance,
            f"boîte de {fiche.lentilles_par_boite}" if fiche.lentilles_par_boite else "",
        ]
    return " · ".join(m for m in morceaux if m)


class ArticleSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    fournisseur = serializers.SlugRelatedField(slug_field="nom", read_only=True)
    stock = serializers.IntegerField(
        read_only=True, allow_null=True, help_text="Quantité en stock du magasin demandé."
    )
    prix_vente_ttc = serializers.DecimalField(
        max_digits=14,
        decimal_places=3,
        read_only=True,
        allow_null=True,
        help_text="Prix dans le pays du magasin demandé.",
    )
    taux_tva = serializers.DecimalField(
        max_digits=5, decimal_places=2, read_only=True, allow_null=True
    )
    devise = serializers.CharField(read_only=True, allow_null=True)
    description = serializers.SerializerMethodField(
        help_text="Caractéristiques résumées sur une ligne."
    )
    caracteristiques = serializers.SerializerMethodField(
        help_text="Fiche de la famille (monture, verre, lentille) ; null pour un article divers."
    )

    class Meta:
        model = Article
        fields = [
            "id",
            "reference",
            "libelle",
            "famille",
            "description",
            "caracteristiques",
            "code_barres",
            "fournisseur",
            "reference_fournisseur",
            "sur_commande",
            "prix_vente_ttc",
            "taux_tva",
            "devise",
            "stock",
        ]

    def get_description(self, article) -> str:
        return decrire(article.caracteristiques)

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_caracteristiques(self, article):
        fiche = article.caracteristiques
        if fiche is None:
            return None
        donnees = model_to_dict(fiche, exclude=["article"])
        return {
            cle: str(v) if v is not None and not isinstance(v, (bool, int, str)) else v
            for cle, v in donnees.items()
        }


class MouvementStockSerializer(serializers.ModelSerializer):
    magasin = serializers.SlugRelatedField(slug_field="public_id", queryset=Magasin.objects)
    article = serializers.SlugRelatedField(slug_field="public_id", queryset=Article.objects)
    type = serializers.ChoiceField(
        choices=[MouvementStock.Type.RECEPTION, MouvementStock.Type.AJUSTEMENT]
    )
    # Pour la consultation : les ventes, retours et transferts ont aussi leurs mouvements.
    type_libelle = serializers.CharField(source="get_type_display", read_only=True)
    magasin_nom = serializers.CharField(source="magasin.nom", read_only=True)
    article_reference = serializers.CharField(source="article.reference", read_only=True)
    article_libelle = serializers.CharField(source="article.libelle", read_only=True)
    utilisateur = serializers.CharField(
        source="utilisateur.get_username", read_only=True, default=""
    )

    class Meta:
        model = MouvementStock
        fields = [
            "id",
            "magasin",
            "magasin_nom",
            "article",
            "article_reference",
            "article_libelle",
            "quantite",
            "type",
            "type_libelle",
            "reference",
            "utilisateur",
            "horodatage",
        ]
        read_only_fields = ["id", "horodatage"]

    def get_fields(self):
        champs = super().get_fields()
        # Évalués à chaque requête pour appliquer le périmètre de l'utilisateur.
        champs["magasin"].queryset = Magasin.objects.all()
        champs["article"].queryset = Article.objects.filter(est_actif=True)
        return champs

    def validate(self, donnees):
        if donnees["quantite"] == 0:
            raise serializers.ValidationError({"quantite": "La quantité ne peut pas être nulle."})
        if donnees["article"].sur_commande:
            raise serializers.ValidationError(
                {"article": "Article commandé pour chaque client : il n'a pas de stock."}
            )
        if donnees["type"] == MouvementStock.Type.RECEPTION and donnees["quantite"] < 0:
            raise serializers.ValidationError({"quantite": "Une réception est positive."})
        return donnees
