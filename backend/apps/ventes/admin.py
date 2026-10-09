from django.contrib import admin

from .models import (
    Avoir,
    BordereauPec,
    Devis,
    DossierSav,
    EtapeCommande,
    EvenementSav,
    Facture,
    LigneAvoir,
    LigneDevis,
    LigneVente,
    Paiement,
    PriseEnCharge,
    Vente,
)


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


class Consultation(admin.ModelAdmin):
    """Consultation seule : ces données se saisissent dans l'application, avec ses contrôles."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PriseEnCharge)
class PriseEnChargeAdmin(Consultation):
    list_display = ("vente", "organisme", "montant", "numero_dossier", "statut", "cree_le")
    list_filter = ("statut", "organisme")
    search_fields = ("vente__numero", "numero_dossier")

    def get_queryset(self, request):
        return PriseEnCharge.objects.select_related("vente", "organisme")


@admin.register(EtapeCommande)
class EtapeCommandeAdmin(Consultation):
    list_display = ("vente", "etape", "le", "par", "observation")
    list_filter = ("etape",)
    search_fields = ("vente__numero",)

    def get_queryset(self, request):
        return EtapeCommande.objects.select_related("vente", "par")


@admin.register(BordereauPec)
class BordereauPecAdmin(Consultation):
    list_display = ("numero", "magasin", "organisme", "statut", "envoye_le", "regle_le")
    list_filter = ("statut", "organisme")
    search_fields = ("numero", "reference_reglement")

    def get_queryset(self, request):
        return BordereauPec.objects.select_related("magasin", "organisme")


class EvenementSavInline(admin.TabularInline):
    model = EvenementSav
    extra = 0
    fields = ("le", "etape", "commentaire", "par")
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(DossierSav)
class DossierSavAdmin(Consultation):
    list_display = ("numero", "magasin", "client", "designation", "motif", "etape", "cree_le")
    list_filter = ("etape", "motif", "sous_garantie")
    search_fields = ("numero", "designation", "client__nom", "client__prenom")
    inlines = [EvenementSavInline]

    def get_queryset(self, request):
        return DossierSav.objects.select_related("magasin", "client")
