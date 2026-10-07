from django.contrib import admin
from django.core.exceptions import PermissionDenied

from core.admin_imports import AvecImport

from .admin_saisie import saisir_inventaire, saisir_transfert
from .models import (
    Article,
    Inventaire,
    Lentille,
    LigneInventaire,
    LigneTransfert,
    Monture,
    MouvementStock,
    PlageVerre,
    PrixArticle,
    TransfertStock,
    Verre,
)


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
        ("fabrication", "diametre_commercial"),
    )


class PlageVerreInline(admin.TabularInline):
    model = PlageVerre
    extra = 1
    fields = (
        "pays",
        "ordre",
        "sphere_debut",
        "sphere_fin",
        "cylindre_debut",
        "cylindre_fin",
        "prix_achat_ht",
        "prix_vente_ttc",
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
        if obj.famille == Article.Famille.VERRE:
            return [fiche, PrixArticleInline, PlageVerreInline]
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


class LigneTransfertInline(admin.TabularInline):
    model = LigneTransfert
    extra = 0
    can_delete = False


@admin.register(TransfertStock)
class TransfertStockAdmin(admin.ModelAdmin):
    list_display = ("numero", "cree_le", "magasin", "destination", "statut", "recu_le")
    list_filter = ("statut", "magasin", "destination")
    search_fields = ("numero",)
    inlines = [LigneTransfertInline]

    def get_queryset(self, request):
        return TransfertStock.tous.select_related("magasin", "destination")

    # « Ajouter » envoie le transfert par le même service que l'application ; le magasin de
    # destination le réceptionne dans l'application. Un transfert ne se modifie pas.
    def add_view(self, request, form_url="", extra_context=None):
        if not self.has_add_permission(request):
            raise PermissionDenied
        return saisir_transfert(self, request)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class LigneInventaireInline(admin.TabularInline):
    model = LigneInventaire
    extra = 0
    can_delete = False


@admin.register(Inventaire)
class InventaireAdmin(admin.ModelAdmin):
    list_display = ("numero", "cree_le", "magasin", "famille", "statut", "valide_le")
    list_filter = ("statut", "magasin", "famille")
    search_fields = ("numero",)
    inlines = [LigneInventaireInline]

    def get_queryset(self, request):
        return Inventaire.tous.select_related("magasin")

    # « Ajouter » crée l'inventaire (et de premiers comptages) par le même service que
    # l'application ; le comptage et la validation finale se poursuivent dans l'application.
    def add_view(self, request, form_url="", extra_context=None):
        if not self.has_add_permission(request):
            raise PermissionDenied
        return saisir_inventaire(self, request)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
