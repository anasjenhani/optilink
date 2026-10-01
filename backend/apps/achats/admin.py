from django.contrib import admin

from .models import CommandeFournisseur, Fournisseur, LigneCommandeFournisseur


@admin.register(Fournisseur)
class FournisseurAdmin(admin.ModelAdmin):
    list_display = ("nom", "pays", "telephone", "email", "est_actif")
    list_filter = ("pays", "est_actif")
    search_fields = ("nom",)


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
