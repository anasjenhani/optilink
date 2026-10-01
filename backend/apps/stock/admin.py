from django.contrib import admin

from .models import Article, MouvementStock, PrixArticle


class PrixArticleInline(admin.TabularInline):
    model = PrixArticle
    extra = 1


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    inlines = [PrixArticleInline]
    list_display = ("reference", "libelle", "famille", "est_actif")
    list_filter = ("famille", "est_actif")
    search_fields = ("reference", "libelle", "code_barres")


@admin.register(MouvementStock)
class MouvementStockAdmin(admin.ModelAdmin):
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
