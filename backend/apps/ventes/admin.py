from django.contrib import admin

from .models import Avoir, Devis, Facture, LigneAvoir, LigneDevis, LigneVente, Paiement, Vente


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

    # Une vente ne se crée qu'en caisse et ne se modifie jamais.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Facture)
class FactureAdmin(admin.ModelAdmin):
    list_display = ("numero", "magasin", "client", "net_a_payer", "devise", "cree_le")
    list_filter = ("magasin",)
    search_fields = ("numero", "client__nom")

    def get_queryset(self, request):
        return Facture.tous.select_related("magasin", "client")

    # Une facture se génère depuis l'application et ne se modifie jamais.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class LigneDevisInline(admin.TabularInline):
    model = LigneDevis
    extra = 0


@admin.register(Devis)
class DevisAdmin(admin.ModelAdmin):
    list_display = (
        "numero",
        "magasin",
        "client",
        "total_ttc",
        "devise",
        "statut",
        "valable_jusqu_au",
    )
    list_filter = ("magasin", "statut")
    search_fields = ("numero", "client__nom")
    inlines = [LigneDevisInline]

    def get_queryset(self, request):
        return Devis.tous.select_related("magasin", "client")

    # Un devis s'établit et change de statut depuis l'application.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class LigneAvoirInline(admin.TabularInline):
    model = LigneAvoir
    extra = 0


@admin.register(Avoir)
class AvoirAdmin(admin.ModelAdmin):
    list_display = ("numero", "magasin", "vente", "total_ttc", "montant_rembourse", "cree_le")
    list_filter = ("magasin", "annulation")
    search_fields = ("numero", "vente__numero")
    inlines = [LigneAvoirInline]

    def get_queryset(self, request):
        return Avoir.tous.select_related("magasin", "vente")

    # Un avoir s'émet depuis l'application et ne se modifie jamais.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
