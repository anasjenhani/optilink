from django.contrib import admin
from django.core.exceptions import PermissionDenied

from apps.reseau.admin import AvecListeVilles
from core.admin_imports import AvecImport

from .admin_saisie import saisir_facture, saisir_reception, saisir_retour
from .models import (
    BonReception,
    BonRetour,
    CasseVerre,
    CommandeFournisseur,
    FactureAchat,
    Fournisseur,
    LigneCommandeFournisseur,
    LigneReception,
    LigneRetour,
)


@admin.register(Fournisseur)
class FournisseurAdmin(AvecListeVilles, AvecImport, admin.ModelAdmin):
    imports = ("fournisseurs",)
    list_display = ("code", "nom", "ville", "telephone", "fournisseur_verres", "est_actif")
    list_filter = ("pays", "fournisseur_verres", "est_actif")
    search_fields = ("nom", "=code", "matricule_fiscal")
    readonly_fields = ("code",)


class LigneReceptionInline(admin.TabularInline):
    model = LigneReception
    extra = 0


@admin.register(BonReception)
class BonReceptionAdmin(AvecImport, admin.ModelAdmin):
    imports = ("receptions",)
    list_display = ("numero", "date_saisie", "fournisseur", "numero_bl", "etat", "total_ttc")
    list_filter = ("magasin", "etat", "fournisseur")
    search_fields = ("numero", "numero_bl", "numero_facture")
    inlines = [LigneReceptionInline]

    def get_queryset(self, request):
        return BonReception.tous.select_related("magasin", "fournisseur")

    # « Ajouter » ouvre une saisie simple qui passe par le même service que l'application.
    # Un bon validé ne se modifie plus (stock et verres déjà reçus).
    def add_view(self, request, form_url="", extra_context=None):
        if not self.has_add_permission(request):
            raise PermissionDenied
        return saisir_reception(self, request)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class BonFactureInline(admin.TabularInline):
    model = BonReception
    fk_name = "facture"
    fields = ("numero", "numero_bl", "date_bl", "total_net_ht", "total_tva", "total_ttc")
    readonly_fields = fields
    extra = 0
    can_delete = False


@admin.register(FactureAchat)
class FactureAchatAdmin(admin.ModelAdmin):
    list_display = (
        "numero",
        "date_entree",
        "fournisseur",
        "reference_fournisseur",
        "total_ttc",
        "paiement",
    )
    list_filter = ("magasin", "paiement", "fournisseur")
    search_fields = ("numero", "reference_fournisseur", "fournisseur__nom")
    inlines = [BonFactureInline]

    def get_queryset(self, request):
        return FactureAchat.tous.select_related("magasin", "fournisseur")

    # « Ajouter » ouvre une saisie simple (même service que l'application : BL marqués
    # facturés). Une facture validée ne se modifie plus.
    def add_view(self, request, form_url="", extra_context=None):
        if not self.has_add_permission(request):
            raise PermissionDenied
        return saisir_facture(self, request)

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


class LigneRetourInline(admin.TabularInline):
    model = LigneRetour
    extra = 0
    can_delete = False


@admin.register(BonRetour)
class BonRetourAdmin(admin.ModelAdmin):
    list_display = ("numero", "date_retour", "fournisseur", "motif", "etat", "total_ttc")
    list_filter = ("magasin", "etat", "fournisseur")
    search_fields = ("numero", "fournisseur__nom", "motif")
    inlines = [LigneRetourInline]

    def get_queryset(self, request):
        return BonRetour.tous.select_related("magasin", "fournisseur")

    # « Ajouter » renvoie des articles du stock par le même service que l'application ; les
    # non conformes d'un bon de réception se renvoient dans l'application.
    def add_view(self, request, form_url="", extra_context=None):
        if not self.has_add_permission(request):
            raise PermissionDenied
        return saisir_retour(self, request)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CasseVerre)
class CasseVerreAdmin(admin.ModelAdmin):
    list_display = ("cree_le", "vente", "ligne_commande", "cause", "declaree_par")
    list_filter = ("cause",)
    search_fields = ("vente__numero",)

    def get_queryset(self, request):
        return CasseVerre.objects.select_related("vente", "ligne_commande__article", "declaree_par")

    # Une casse se déclare depuis la visite, dans l'application (le verre repasse à commander).
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
