from django.contrib import admin

from .models import (
    BonReception,
    CommandeFournisseur,
    Fournisseur,
    LigneCommandeFournisseur,
    LigneReception,
)


@admin.register(Fournisseur)
class FournisseurAdmin(admin.ModelAdmin):
    list_display = ("code", "nom", "ville", "telephone", "fournisseur_verres", "est_actif")
    list_filter = ("pays", "fournisseur_verres", "est_actif")
    search_fields = ("nom", "=code", "matricule_fiscal")
    readonly_fields = ("code",)


class LigneReceptionInline(admin.TabularInline):
    model = LigneReception
    extra = 0


@admin.register(BonReception)
class BonReceptionAdmin(admin.ModelAdmin):
    list_display = ("numero", "date_saisie", "fournisseur", "numero_bl", "etat", "total_ttc")
    list_filter = ("magasin", "etat", "fournisseur")
    search_fields = ("numero", "numero_bl", "numero_facture")
    inlines = [LigneReceptionInline]

    def get_queryset(self, request):
        return BonReception.tous.select_related("magasin", "fournisseur")

    # Un bon de réception se saisit dans l'application (stock et verres reçus en même temps).
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class LigneCommandeFournisseurInline(admin.TabularInline):
    model = LigneCommandeFournisseur
    extra = 0


@admin.register(CommandeFournisseur)
class CommandeFournisseurAdmin(admin.ModelAdmin):
    list_display = ("numero", "magasin", "fournisseur", "statut", "cree_le", "recue_le")
    list_filter = ("magasin", "statut", "fournisseur")
    search_fields = ("numero", "reference_fournisseur")
    inlines = [LigneCommandeFournisseurInline]

    def get_queryset(self, request):
        return CommandeFournisseur.tous.select_related("magasin", "fournisseur")

    # Une commande fournisseur se passe et se réceptionne depuis l'application.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
