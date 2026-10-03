import base64
import json

from django import forms
from django.contrib import admin
from django.utils.html import format_html

from .models import Magasin, Pays, Societe, TauxTva
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


LOGO_TAILLE_MAX = 1024 * 1024
LOGO_FORMATS = {b"\x89PNG\r\n\x1a\n": "image/png", b"\xff\xd8\xff": "image/jpeg"}


def type_d_image(contenu):
    """Type MIME d'un PNG, JPEG ou WebP reconnu à ses premiers octets ; ``None`` sinon."""
    for signature, type_mime in LOGO_FORMATS.items():
        if contenu.startswith(signature):
            return type_mime
    if contenu[:4] == b"RIFF" and contenu[8:12] == b"WEBP":
        return "image/webp"
    return None


class SocieteForm(forms.ModelForm):
    site_web = forms.URLField(label="Site web", required=False, assume_scheme="https")
    logo_fichier = forms.FileField(
        label="Logo", required=False, help_text="PNG, JPEG ou WebP, 1 Mo au plus."
    )
    supprimer_logo = forms.BooleanField(label="Supprimer le logo", required=False)

    class Meta:
        model = Societe
        fields = (
            "raison_sociale",
            "responsable",
            "forme_juridique",
            "matricule_fiscal",
            "registre_commerce",
            "numero_cnss",
            "banque",
            "rib",
            "adresse",
            "code_postal",
            "ville",
            "pays",
            "telephone_1",
            "telephone_2",
            "fax",
            "email",
            "site_web",
            "facebook",
            "observation",
            "code_douane",
            "carte_sejour",
        )
        widgets = {
            "adresse": forms.Textarea(attrs={"rows": 3}),
            "observation": forms.Textarea(attrs={"rows": 4}),
        }

    def clean_logo_fichier(self):
        fichier = self.cleaned_data.get("logo_fichier")
        if not fichier:
            return None
        if fichier.size > LOGO_TAILLE_MAX:
            raise forms.ValidationError("Le logo dépasse 1 Mo.")
        contenu = fichier.read()
        type_mime = type_d_image(contenu)
        if type_mime is None:
            raise forms.ValidationError("Choisissez une image PNG, JPEG ou WebP.")
        return contenu, type_mime

    def save(self, commit=True):
        logo = self.cleaned_data.get("logo_fichier")
        if logo:
            self.instance.logo, self.instance.logo_type = logo
        elif self.cleaned_data.get("supprimer_logo"):
            self.instance.logo, self.instance.logo_type = None, ""
        return super().save(commit)


@admin.register(Societe)
class SocieteAdmin(admin.ModelAdmin):
    form = SocieteForm
    list_display = ("code", "raison_sociale", "forme_juridique", "matricule_fiscal", "ville")
    search_fields = ("code", "raison_sociale", "matricule_fiscal")
    readonly_fields = ("code", "apercu_logo")
    fieldsets = (
        (
            "Informations générales",
            {
                "fields": (
                    "code",
                    "raison_sociale",
                    ("responsable", "forme_juridique"),
                    ("matricule_fiscal", "registre_commerce", "numero_cnss"),
                    ("banque", "rib"),
                )
            },
        ),
        ("Logo", {"fields": ("apercu_logo", "logo_fichier", "supprimer_logo")}),
        (
            "Adresse",
            {
                "fields": (
                    "adresse",
                    ("code_postal", "ville", "pays"),
                    ("telephone_1", "telephone_2", "fax"),
                    ("email", "site_web", "facebook"),
                )
            },
        ),
        ("Observation", {"fields": ("observation",)}),
        ("À l'étranger", {"classes": ("collapse",), "fields": ("code_douane", "carte_sejour")}),
    )

    @admin.display(description="Logo actuel")
    def apercu_logo(self, societe):
        if not societe.logo:
            return "Aucun"
        donnees = base64.b64encode(bytes(societe.logo)).decode()
        return format_html(
            '<img src="data:{};base64,{}" alt="Logo" style="max-height:80px">',
            societe.logo_type,
            donnees,
        )


@admin.register(Magasin)
class MagasinAdmin(admin.ModelAdmin):
    list_display = ("code", "nom", "pays", "societe", "ville", "est_actif")
    list_filter = ("pays", "societe", "est_actif")
    search_fields = ("code", "nom", "ville")
