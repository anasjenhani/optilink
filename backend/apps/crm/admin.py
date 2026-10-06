from django.contrib import admin

from core.admin_imports import AvecImport

from .models import Client, Organisme


@admin.register(Client)
class ClientAdmin(AvecImport, admin.ModelAdmin):
    imports = ("clients",)
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


@admin.register(Organisme)
class OrganismeAdmin(admin.ModelAdmin):
    list_display = ("nom", "type", "pays", "est_actif")
    list_filter = ("type", "pays", "est_actif")
    search_fields = ("nom",)
    # Supprimable tant qu'aucun client ni aucune prise en charge ne le cite (sinon : désactiver).
