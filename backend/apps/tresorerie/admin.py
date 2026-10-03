from django.contrib import admin

from .models import ClotureCaisse, CompteTresorerie, DepenseCaisse, OperationTresorerie


@admin.register(ClotureCaisse)
class ClotureCaisseAdmin(admin.ModelAdmin):
    list_display = ("numero", "magasin", "fin", "statut", "cloturee_par", "verifiee_par")
    list_filter = ("statut", "magasin")
    search_fields = ("numero",)

    # Pièce comptable : elle se consulte, elle se corrige dans l'application.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DepenseCaisse)
class DepenseCaisseAdmin(admin.ModelAdmin):
    list_display = ("payee_le", "magasin", "categorie", "motif", "montant", "cloture")
    list_filter = ("categorie", "magasin")

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CompteTresorerie)
class CompteTresorerieAdmin(admin.ModelAdmin):
    list_display = ("nom", "type", "societe", "banque", "magasin", "est_actif")
    list_filter = ("type", "societe", "est_actif")
    search_fields = ("nom", "rib")


@admin.register(OperationTresorerie)
class OperationTresorerieAdmin(admin.ModelAdmin):
    list_display = ("numero", "type", "statut", "source", "destination", "montant", "reference")
    list_filter = ("type", "statut", "societe")
    search_fields = ("numero", "reference")

    # Les opérations suivent des règles (soldes, clôtures) : elles passent par l'application.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
