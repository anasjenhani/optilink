import json

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.contrib.contenttypes.models import ContentType
from django.utils.html import format_html_join

from apps.reseau.models import Magasin
from core.admin_imports import AvecImport

from .corbeille import RestaurationImpossible, concerne, mettre_a_la_corbeille, restaurer
from .journal_droits import decrire, libelles_permissions, type_d_objet
from .models import (
    Affectation,
    ElementCorbeille,
    EvenementSecurite,
    ModificationDroits,
    Utilisateur,
)


class AffectationForm(forms.ModelForm):
    """Portée magasin : la société affichée est celle du magasin, remplie d'office.

    L'écran la remplit dès le choix du magasin (affectations.js). Seul le magasin est
    enregistré : la société suit donc le magasin s'il change un jour de société.
    """

    class Meta:
        model = Affectation
        fields = ["role", "portee", "magasin", "societe", "debut", "fin"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "magasin" in self.fields:
            societes = {
                str(pk): str(societe or "")
                for pk, societe in Magasin.tous.values_list("pk", "societe_id")
            }
            self.fields["magasin"].widget.attrs["data-societes"] = json.dumps(societes)
        instance = self.instance
        if instance.portee == Affectation.Portee.MAGASIN and instance.magasin_id:
            self.initial["societe"] = instance.magasin.societe_id

    def clean(self):
        donnees = super().clean()
        if donnees.get("portee") == Affectation.Portee.MAGASIN:
            donnees["societe"] = None
            self.instance.societe = None
        return donnees


class AffectationInline(admin.TabularInline):
    model = Affectation
    form = AffectationForm
    extra = 0

    class Media:
        js = ("securite/affectations.js",)


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
    list_display = ("username", "first_name", "last_name", "is_active", "is_staff", "last_login")
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


class AvecCorbeille:
    """Suppressions de l'administration : l'élément part à la corbeille, restaurable."""

    def delete_model(self, request, obj):
        if not concerne(type(obj)):
            return super().delete_model(request, obj)
        mettre_a_la_corbeille(obj, auteur=request.user)
        messages.info(
            request,
            f"« {obj} » est dans la corbeille (Sécurité › Corbeille) : restaurable pendant "
            f"{settings.CORBEILLE_JOURS} jours.",
        )

    def delete_queryset(self, request, queryset):
        if not concerne(queryset.model):
            return super().delete_queryset(request, queryset)
        for obj in queryset:
            mettre_a_la_corbeille(obj, auteur=request.user)


def brancher_corbeille(site):
    """Fait passer par la corbeille les suppressions de toutes les pages de l'administration."""
    for modele, model_admin in site._registry.items():
        classe = type(model_admin)
        if concerne(modele) and not issubclass(classe, AvecCorbeille):
            model_admin.__class__ = type(classe.__name__, (AvecCorbeille, classe), {})


@admin.register(ElementCorbeille)
class ElementCorbeilleAdmin(admin.ModelAdmin):
    list_display = ("supprime_le", "type_libelle", "libelle", "supprime_par", "expire_le")
    list_filter = ("type_libelle",)
    search_fields = ("libelle",)
    readonly_fields = [f.name for f in ElementCorbeille._meta.fields]
    actions = ["restaurer_elements"]

    def get_queryset(self, request):
        elements = super().get_queryset(request).select_related("supprime_par")
        if request.user.is_superuser:
            return elements
        # Chacun ne voit que ce qu'il aurait le droit de recréer.
        visibles = [e.pk for e in elements if request.user.has_perm(e.permission_ajout, e)]
        return elements.filter(pk__in=visibles)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Restaurer les éléments choisis", permissions=["restaurer"])
    def restaurer_elements(self, request, queryset):
        restaures = 0
        for element in queryset:
            try:
                restaurer(element)
                restaures += 1
            except RestaurationImpossible as erreur:
                self.message_user(request, f"{element} : {erreur}", messages.ERROR)
        if restaures:
            self.message_user(request, f"{restaures} élément(s) restauré(s).", messages.SUCCESS)

    def has_restaurer_permission(self, request):
        return request.user.has_perm("securite.restaurer_elementcorbeille")
