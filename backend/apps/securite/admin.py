from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.contenttypes.models import ContentType
from django.utils.html import format_html_join

from core.admin_imports import AvecImport

from .journal_droits import decrire, libelles_permissions, type_d_objet
from .models import Affectation, EvenementSecurite, ModificationDroits, Utilisateur


class AffectationInline(admin.TabularInline):
    model = Affectation
    extra = 0


@admin.register(Utilisateur)
class UtilisateurAdmin(AvecImport, UserAdmin):
    imports = ("utilisateurs",)
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


class TypeDroitsFiltre(admin.SimpleListFilter):
    title = "type"
    parameter_name = "type"

    def lookups(self, request, model_admin):
        return [("group", "Profil"), ("affectation", "Profil donné"), ("utilisateur", "Compte")]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(content_type__model=self.value())
        return queryset


ACTIONS = {0: "Création", 1: "Modification", 2: "Suppression"}


class ActionDroitsFiltre(admin.SimpleListFilter):
    title = "action"
    parameter_name = "action"

    def lookups(self, request, model_admin):
        return [(str(cle), libelle) for cle, libelle in ACTIONS.items()]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(action=int(self.value()))
        return queryset


@admin.register(ModificationDroits)
class ModificationDroitsAdmin(admin.ModelAdmin):
    """Qui a changé quels droits, quand : privilèges des profils, profils donnés, comptes."""

    list_display = (
        "date",
        "auteur",
        "action_lisible",
        "type_lisible",
        "objet",
        "detail",
    )
    list_filter = (TypeDroitsFiltre, ActionDroitsFiltre)
    search_fields = ("object_repr", "actor__username")
    date_hierarchy = "timestamp"
    list_per_page = 50

    def get_queryset(self, request):
        types = ContentType.objects.filter(
            app_label__in=["auth", "securite"], model__in=["group", "affectation", "utilisateur"]
        )
        self._libelles = libelles_permissions()
        return (
            super()
            .get_queryset(request)
            .filter(content_type__in=types)
            .select_related("actor", "content_type")
        )

    @admin.display(description="date", ordering="timestamp")
    def date(self, entree):
        return entree.timestamp

    @admin.display(description="concerne", ordering="object_repr")
    def objet(self, entree):
        return entree.object_repr

    @admin.display(description="auteur", ordering="actor__username")
    def auteur(self, entree):
        return entree.actor or "système"

    @admin.display(description="action", ordering="action")
    def action_lisible(self, entree):
        return ACTIONS.get(entree.action, entree.get_action_display())

    @admin.display(description="type")
    def type_lisible(self, entree):
        return type_d_objet(entree)

    @admin.display(description="détail")
    def detail(self, entree):
        return format_html_join(
            "", "<div>{}</div>", ((ligne,) for ligne in decrire(entree, self._libelles))
        )

    # Vue du journal d'audit : on la lit, on ne la modifie pas.
    def has_view_permission(self, request, obj=None):
        return request.user.has_perm("auditlog.view_logentry")

    def has_module_permission(self, request):
        return self.has_view_permission(request)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
