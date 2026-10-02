from django.contrib import admin

from .models import LigneVente, Paiement, Vente


class LigneVenteInline(admin.TabularInline):
    model = LigneVente
    extra = 0


class PaiementInline(admin.TabularInline):
    model = Paiement
    extra = 0


@admin.register(Vente)
class VenteAdmin(admin.ModelAdmin):
    list_display = ("numero", "magasin", "vendeur", "total_ttc", "cree_le")
    list_filter = ("magasin",)
    search_fields = ("numero",)
    inlines = [LigneVenteInline, PaiementInline]

    def get_queryset(self, request):
        return Vente.tous.select_related("magasin", "vendeur")

    # Une facture ne se crée qu'en caisse et ne se modifie jamais.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
