from django.contrib import admin

from core.admin_imports import AvecImport

from .models import AccesPrescription, Ophtalmologue

# Les ordonnances elles-mêmes ne sont pas dans l'administration : elles ne se lisent que dans
# l'application, où chaque consultation est journalisée.


@admin.register(AccesPrescription)
class AccesPrescriptionAdmin(admin.ModelAdmin):
    list_display = ("horodatage", "utilisateur", "action", "prescription", "adresse_ip")
    list_filter = ("action",)
    search_fields = ("utilisateur__username",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Ophtalmologue)
class OphtalmologueAdmin(AvecImport, admin.ModelAdmin):
    imports = ("ophtalmologues",)
    list_display = ("nom", "telephone", "telephone_2", "ville", "anciens_codes", "est_actif")
    list_filter = ("est_actif",)
    search_fields = ("nom", "cle", "telephone", "telephone_2", "anciens_codes")

    # Les ordonnances gardent le nom du médecin : on le désactive au lieu de le supprimer.
    def has_delete_permission(self, request, obj=None):
        return False
