import json

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin

from apps.reseau.models import Magasin
from core.admin_imports import AvecImport

from .corbeille import RestaurationImpossible, concerne, mettre_a_la_corbeille, restaurer
from .models import Affectation, ElementCorbeille, EvenementSecurite, Utilisateur


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
    list_display = (
        "username",
        "first_name",
        "last_name",
        "profils",
        "is_active",
        "is_staff",
        "last_login",
    )
    list_filter = (
        "is_active",
        ("affectations__role", admin.RelatedOnlyFieldListFilter),
        "is_staff",
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .prefetch_related(
                "affectations__role", "affectations__magasin", "affectations__societe"
            )
        )

    @admin.display(description="profils")
    def profils(self, utilisateur):
        """« Vendeur (1, C) » : chaque profil avec les magasins ou sociétés où il s'applique."""
        perimetres = {}
        for a in utilisateur.affectations.all():
            cible = a.magasin.code if a.magasin else a.societe or "tout le réseau"
            perimetres.setdefault(a.role.name, []).append(str(cible))
        return " ; ".join(f"{p} ({', '.join(sorted(c))})" for p, c in sorted(perimetres.items()))

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
