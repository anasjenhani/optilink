from django.contrib import admin

from core.admin_imports import AvecImport

from .models import Article, Lentille, Monture, MouvementStock, PrixArticle, Verre


class PrixArticleInline(admin.TabularInline):
    model = PrixArticle
    extra = 1


class MontureInline(admin.StackedInline):
    model = Monture
    fields = (
        ("categorie", "marque", "modele"),
        ("couleur", "couleur_verres", "matiere"),
        ("type", "forme", "genre", "tranche_age"),
        ("calibre", "pont", "branche"),
    )


class VerreInline(admin.StackedInline):
    model = Verre
    fields = (
        ("marque", "gamme"),
        ("geometrie", "indice", "matiere"),
        "traitements",
        ("photochromique", "teinte", "diametre"),
    )


class LentilleInline(admin.StackedInline):
    model = Lentille
    fields = (
        ("marque", "modele"),
        ("renouvellement", "type", "lentilles_par_boite"),
        ("rayon", "diametre"),
        ("puissance", "cylindre", "axe", "addition"),
    )


CARACTERISTIQUES = {
    Article.Famille.MONTURE: MontureInline,
    Article.Famille.VERRE: VerreInline,
    Article.Famille.LENTILLE: LentilleInline,
}


@admin.register(Article)
class ArticleAdmin(AvecImport, admin.ModelAdmin):
    imports = ("catalogue", "verres")
    list_display = (
        "reference",
        "libelle",
        "famille",
        "marque",
        "fournisseur",
        "code_barres",
        "sur_commande",
        "est_actif",
    )
    list_filter = ("famille", "sur_commande", "fournisseur", "est_actif")
    autocomplete_fields = ("fournisseur",)
    search_fields = (
        "reference",
        "libelle",
        "code_barres",
        "reference_fournisseur",
        "monture__marque",
        "monture__modele",
        "verre__marque",
        "verre__gamme",
        "lentille__marque",
        "lentille__modele",
    )

    def get_inlines(self, request, obj):
        # À la création, la fiche de la famille choisie est la seule enregistrée : les autres
        # restent vides. Ensuite, seule celle de la famille de l'article est proposée.
        if obj is None:
            return [*CARACTERISTIQUES.values(), PrixArticleInline]
        fiche = CARACTERISTIQUES.get(obj.famille)
        return [fiche, PrixArticleInline] if fiche else [PrixArticleInline]

    @admin.display(description="marque")
    def marque(self, article):
        fiche = article.caracteristiques
        return fiche.marque if fiche else ""

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("monture", "verre", "lentille", "fournisseur")
        )


@admin.register(MouvementStock)
class MouvementStockAdmin(AvecImport, admin.ModelAdmin):
    imports = ("stock",)
    list_display = ("horodatage", "magasin", "article", "type", "quantite", "reference")
    list_filter = ("type", "magasin")
    search_fields = ("article__reference", "reference")

    def get_queryset(self, request):
        return MouvementStock.tous.select_related("magasin", "article")

    # Le stock ne se corrige que par un nouveau mouvement, jamais en modifiant l'historique.
    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
