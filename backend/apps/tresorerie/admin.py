from django.contrib import admin
from django.utils import timezone

from apps.reseau.admin import AvecListeBanques
from apps.reseau.models import Magasin

from .api.views import magasins_couverts
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
    fields = ("magasin", "categorie", "motif", "beneficiaire", "montant")

    def get_queryset(self, request):
        return DepenseCaisse.tous.select_related("magasin", "cloture")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "magasin":
            kwargs["queryset"] = Magasin.tous.filter(
                pk__in=magasins_couverts(request.user, "tresorerie.add_depensecaisse")
            ).order_by("nom")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.saisie_par = request.user
            obj.payee_le = timezone.now()
        super().save_model(request, obj, form, change)

    # Comme dans l'application : modifiable ou supprimable tant que la caisse n'est pas
    # clôturée ; ensuite la dépense fait partie de la clôture (pièce comptable).
    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and (
            obj is None or obj.cloture_id is None
        )

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and (
            obj is None or obj.cloture_id is None
        )

    def get_actions(self, request):
        # La suppression groupée ne verrait pas les dépenses déjà clôturées.
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions


@admin.register(CompteTresorerie)
class CompteTresorerieAdmin(AvecListeBanques, admin.ModelAdmin):
    def pays_de_la_fiche(self, donnees, instance):
        societe = donnees.get("societe") or getattr(instance, "societe", None)
        return getattr(societe, "pays", None)

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
