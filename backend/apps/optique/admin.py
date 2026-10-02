from django.contrib import admin

from .models import AccesPrescription

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
