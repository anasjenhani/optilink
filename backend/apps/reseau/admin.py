import json

from django import forms
from django.contrib import admin

from .models import Magasin, Pays, Region, TauxTva
from .pays_du_monde import CHAMPS, pays_du_monde

OBLIGATOIRES = ("code_numerique", "code", "nom", "devise")


class PaysForm(forms.ModelForm):
    """Le choix d'un pays de la liste remplit codes, devise, décimales, indicatif et fuseau.

    L'écran les remplit dès le choix (pays_du_monde.js) ; sans JavaScript, l'enregistrement
    complète les champs laissés tels quels. Ce qui a été tapé à la main est gardé, et une fiche
    modifiée sans changer de pays dans la liste n'est pas réécrite.
    """

    pays_du_monde = forms.ChoiceField(
        label="Pays",
        required=False,
        help_text="Remplit automatiquement le code ISO, la devise et les autres champs ci-dessous.",
    )

    class Meta:
        model = Pays
        fields = (
            *CHAMPS,
            "timbre_fiscal",
            "libelle_identifiant_prescripteur",
            "format_identifiant_prescripteur",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        liste = pays_du_monde()
        champ = self.fields["pays_du_monde"]
        champ.choices = [("", "— Choisir un pays —")] + [
            (numerique, f"{p['nom']} — {numerique} · {p['devise']}")
            for numerique, p in liste.items()
        ]
        champ.widget.attrs["data-pays"] = json.dumps(liste, ensure_ascii=False)
        if self.instance.pk:
            champ.initial = self.instance.code_numerique
        for nom in OBLIGATOIRES:
            self.fields[nom].required = False

    def clean(self):
        donnees = super().clean()
        choisi = pays_du_monde().get(donnees.get("pays_du_monde") or "")
        if choisi and "pays_du_monde" in self.changed_data:
            for nom in CHAMPS:
                if nom not in self.changed_data or donnees.get(nom) in (None, ""):
                    donnees[nom] = choisi[nom]
        for nom in OBLIGATOIRES:
            if not donnees.get(nom):
                self.add_error(nom, "Choisissez un pays dans la liste, ou remplissez ce champ.")
        return donnees


class TauxTvaInline(admin.TabularInline):
    model = TauxTva
    extra = 1


@admin.register(Pays)
class PaysAdmin(admin.ModelAdmin):
    form = PaysForm
    inlines = [TauxTvaInline]
    list_display = ("nom", "code_numerique", "code", "devise", "decimales", "timbre_fiscal")
    search_fields = ("nom", "code_numerique", "code", "devise")
    fieldsets = (
        (None, {"fields": ("pays_du_monde",)}),
        (
            "Identité et monnaie",
            {
                "fields": (
                    ("code_numerique", "code"),
                    "nom",
                    ("devise", "decimales"),
                    ("indicatif_telephonique", "fuseau_horaire"),
                )
            },
        ),
        ("Fiscalité", {"fields": ("timbre_fiscal",)}),
        (
            "Ordonnances",
            {"fields": ("libelle_identifiant_prescripteur", "format_identifiant_prescripteur")},
        ),
    )

    class Media:
        js = ("reseau/pays_du_monde.js",)


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ("code", "nom")
    search_fields = ("code", "nom")


@admin.register(Magasin)
class MagasinAdmin(admin.ModelAdmin):
    list_display = ("code", "nom", "pays", "region", "ville", "est_actif")
    list_filter = ("pays", "region", "est_actif")
    search_fields = ("code", "nom", "ville")
