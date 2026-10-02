from django.contrib import admin

from .models import Client


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = (
        "nom",
        "prenom",
        "societe",
        "telephone",
        "email",
        "magasin_origine",
        "est_actif",
    )
    list_filter = ("est_actif", "magasin_origine")
    search_fields = (
        "nom",
        "prenom",
        "telephone",
        "telephone_2",
        "email",
        "societe",
        "matricule_fiscal",
    )

    # Un client garde son historique d'achats et ses ordonnances : on le désactive.
    def has_delete_permission(self, request, obj=None):
        return False
