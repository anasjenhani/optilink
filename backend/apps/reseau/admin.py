import base64
import json

from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.utils.html import format_html, format_html_join

from .banques import valider_banque
from .models import Banque, Depot, Magasin, Pays, Societe, TauxTva, Ville
from .pays_du_monde import CHAMPS, pays_du_monde
from .villes import normaliser, valider_ville

OBLIGATOIRES = ("code_numerique", "code", "nom", "devise")


class ListeVilles(forms.TextInput):
    """Champ ville : on tape les premières lettres et on choisit dans la liste des villes."""

    def render(self, name, value, attrs=None, renderer=None):
        identifiant = f"villes-{name}"
        attrs = {**(attrs or {}), "list": identifiant, "autocomplete": "off"}
        noms = sorted(
            Ville.objects.filter(est_active=True).values_list("nom", flat=True), key=normaliser
        )
        options = format_html_join("", '<option value="{}">', ((nom,) for nom in noms))
        return super().render(name, value, attrs, renderer) + format_html(
            '<datalist id="{}">{}</datalist>', identifiant, options
        )


class AvecListeVilles:
    """Fiches de l'administration : la ville se choisit dans la liste (Réseau › Villes)."""

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "ville":
            kwargs["widget"] = ListeVilles()
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def get_form(self, request, obj=None, **kwargs):
        formulaire = super().get_form(request, obj, **kwargs)

        class AvecVille(formulaire):
            def clean(self):
                donnees = super().clean()
                if donnees.get("ville"):
                    pays = donnees.get("pays") or getattr(self.instance, "pays", None)
                    try:
                        donnees["ville"] = valider_ville(donnees["ville"], pays)
                    except ValidationError as erreur:
                        self.add_error("ville", erreur)
                return donnees

        return AvecVille


class ListeBanques(forms.TextInput):
    """Champ banque : on tape le sigle ou le nom et on choisit dans la liste des banques."""

    def render(self, name, value, attrs=None, renderer=None):
        identifiant = f"banques-{name}"
        attrs = {**(attrs or {}), "list": identifiant, "autocomplete": "off"}
        banques = Banque.objects.filter(est_active=True).order_by("nom")
        options = format_html_join(
            "", '<option value="{}">{}</option>', ((b.nom, b.sigle) for b in banques)
        )
        return super().render(name, value, attrs, renderer) + format_html(
            '<datalist id="{}">{}</datalist>', identifiant, options
        )


class AvecListeBanques:
    """Fiches de l'administration : la banque se choisit dans la liste (Réseau › Banques) et
    doit aller avec le RIB ; sans banque, elle est déduite du RIB."""

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "banque":
            kwargs["widget"] = ListeBanques()
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def pays_de_la_fiche(self, donnees, instance):
        return donnees.get("pays") or getattr(instance, "pays", None)

    def get_form(self, request, obj=None, **kwargs):
        formulaire = super().get_form(request, obj, **kwargs)
        model_admin = self

        class AvecBanque(formulaire):
            def clean(self):
                donnees = super().clean()
                if "banque" in donnees:
                    pays = model_admin.pays_de_la_fiche(donnees, self.instance)
                    try:
                        donnees["banque"] = valider_banque(
                            donnees["banque"], donnees.get("rib", ""), pays
                        )
                    except ValidationError as erreur:
                        for champ, messages in erreur.message_dict.items():
                            self.add_error(champ if champ in self.fields else None, messages)
                return donnees

        return AvecBanque


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
class SocieteAdmin(AvecListeVilles, AvecListeBanques, admin.ModelAdmin):
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


class DepotInline(admin.TabularInline):
    """Le dépôt de vente est créé avec le magasin ; on y ajoute un dépôt central, casse…"""

    model = Depot
    fields = ("code", "nom", "type", "est_actif")
    show_change_link = True  # adresse, ville, téléphone : sur la fiche du dépôt
    extra = 0
    can_delete = False


@admin.register(Magasin)
class MagasinAdmin(AvecListeVilles, admin.ModelAdmin):
    list_display = ("code", "nom", "depots_du_magasin", "pays", "societe", "ville", "est_actif")
    list_filter = ("pays", "societe", "est_actif")
    search_fields = ("code", "nom", "ville")
    inlines = [DepotInline]

    @admin.display(description="dépôts")
    def depots_du_magasin(self, magasin):
        return ", ".join(d.code for d in magasin.depots.all() if d.est_actif)

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("depots")


# Un dépôt ne se supprime pas (son stock et ses mouvements y restent) : on le désactive.
@admin.register(Depot)
class DepotAdmin(AvecListeVilles, admin.ModelAdmin):
    # Les colonnes de l'ancien logiciel : CodeDepot, Libelle, Adresse, Ville, Tel,
    # EtatInventaire, CodeMagasin ; puis le type et l'état.
    list_display = (
        "code",
        "nom",
        "adresse",
        "ville",
        "telephone",
        "etat_inventaire",
        "code_magasin",
        "type",
        "est_actif",
    )
    list_filter = ("type", "magasin__societe", "est_actif")
    search_fields = ("code", "nom", "ville", "magasin__code", "magasin__nom")
    fields = ("code", "nom", "adresse", "ville", "telephone", "magasin", "type", "est_actif")

    @admin.display(description="code magasin", ordering="magasin__code")
    def code_magasin(self, depot):
        return f"{depot.magasin.code} {depot.magasin.nom}"

    @admin.display(description="inventaire en cours", boolean=True)
    def etat_inventaire(self, depot):
        return depot.inventaire_en_cours

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("magasin")

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Ville)
class VilleAdmin(admin.ModelAdmin):
    list_display = ("nom", "pays", "est_active")
    list_filter = ("pays", "est_active")
    list_editable = ("est_active",)
    search_fields = ("nom",)


@admin.register(Banque)
class BanqueAdmin(admin.ModelAdmin):
    list_display = ("code", "sigle", "nom", "pays", "est_active")
    list_filter = ("pays", "est_active")
    list_editable = ("est_active",)
    search_fields = ("code", "sigle", "nom")
    ordering = ("pays", "code")
