from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Affectation, EvenementSecurite, Utilisateur


class AffectationInline(admin.TabularInline):
    model = Affectation
    extra = 0


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    inlines = [AffectationInline]
    # Les droits se donnent par affectation (rôle + périmètre), jamais directement au compte.
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Identité", {"fields": ("first_name", "last_name", "email")}),
        ("Statut", {"fields": ("is_active", "is_staff", "is_superuser")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    readonly_fields = ("last_login", "date_joined")
    list_filter = ("is_active", "is_staff", "is_superuser")

    # Un compte garde son historique d'audit : on le désactive, on ne le supprime pas.
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EvenementSecurite)
class EvenementSecuriteAdmin(admin.ModelAdmin):
    list_display = ("horodatage", "type", "identifiant", "adresse_ip")
    list_filter = ("type",)
    search_fields = ("identifiant", "adresse_ip")
    date_hierarchy = "horodatage"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
