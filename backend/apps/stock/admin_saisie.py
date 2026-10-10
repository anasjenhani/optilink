"""Saisie manuelle dans l'administration du serveur (/admin/) : inventaire, transfert de stock.

Le bouton « Ajouter » de la liste des inventaires crée l'inventaire (dépôt, périmètre) et peut
enregistrer de premiers comptages. Tout passe par les mêmes services que l'application ; le
comptage, la vérification et la validation finale se poursuivent dans Stock › Inventaire.
"""

from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse

from apps.achats.admin_saisie import _page, magasins_autorises
from apps.achats.models import Fournisseur
from apps.reseau.models import Depot

from .inventaires import InventaireImpossible, compter, ouvrir_inventaire, trouver_article
from .models import Article, Monture
from .transferts import TransfertImpossible, envoyer_transfert


class ChoixDepot(forms.ModelChoiceField):
    def label_from_instance(self, depot):
        return f"{depot.code} {depot.nom} ({depot.get_type_display()}, {depot.magasin.nom})"


def _depots(magasins):
    """Dépôts actifs des magasins, le dépôt central d'abord."""
    return sorted(
        Depot.objects.filter(magasin__in=magasins, est_actif=True).select_related("magasin"),
        key=lambda d: (d.type != Depot.Type.CENTRAL, d.magasin.nom, d.code),
    )


class InventaireForm(forms.Form):
    depot = ChoixDepot(label="Dépôt", queryset=Depot.objects.none())
    famille = forms.ChoiceField(
        choices=[("", "Tout le stock"), *Article.Famille.choices], required=False
    )
    marque = forms.CharField(
        label="Marque monture", max_length=100, required=False, help_text="Vide : toutes."
    )
    nature = forms.ChoiceField(choices=[("", "Toutes"), *Monture.Categorie.choices], required=False)
    fournisseur = forms.ModelChoiceField(
        queryset=Fournisseur.objects.none(), required=False, empty_label="Tous"
    )
    observation = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)

    def __init__(self, *args, magasins, **kwargs):
        super().__init__(*args, **kwargs)
        # Le dépôt central d'abord, comme dans l'application.
        ordre = _depots(magasins)
        self.fields["depot"].queryset = Depot.objects.filter(pk__in=[d.pk for d in ordre])
        self.fields["depot"].initial = ordre[0].pk if ordre else None
        self.fields["fournisseur"].queryset = Fournisseur.objects.filter(est_actif=True).order_by(
            "nom"
        )


class LigneInventaireForm(forms.Form):
    article = forms.CharField(label="Code-barres ou référence", max_length=60)
    quantite = forms.IntegerField(label="Quantité comptée", min_value=0, initial=1)
    observation = forms.CharField(max_length=200, required=False)

    def clean_article(self):
        try:
            return trouver_article(self.cleaned_data["article"])
        except InventaireImpossible as erreur:
            raise forms.ValidationError(str(erreur)) from None


LignesInventaire = forms.formset_factory(LigneInventaireForm, extra=5)


def saisir_inventaire(model_admin, request):
    """Page « Ajouter un inventaire » de l'administration."""
    magasins = magasins_autorises(request.user, "stock.add_inventaire")
    if not magasins:
        raise PermissionDenied
    entete = InventaireForm(request.POST or None, magasins=magasins)
    lignes = LignesInventaire(request.POST or None, prefix="lignes")
    if request.method == "POST" and entete.is_valid() and lignes.is_valid():
        donnees = entete.cleaned_data
        try:
            with transaction.atomic():
                inventaire = ouvrir_inventaire(
                    magasin=donnees["depot"].magasin,
                    depot=donnees["depot"],
                    auteur=request.user,
                    famille=donnees["famille"],
                    marque=donnees["marque"],
                    nature=donnees["nature"],
                    fournisseur=donnees["fournisseur"],
                    observation=donnees["observation"],
                )
                for ligne in lignes.cleaned_data:
                    if ligne:
                        compter(
                            inventaire,
                            ligne["article"],
                            quantite=ligne["quantite"],
                            remplacer=ligne["quantite"] == 0,
                            observation=ligne["observation"] or None,
                        )
        except InventaireImpossible as erreur:
            entete.add_error(None, str(erreur))
        else:
            messages.success(
                request,
                f"Inventaire {inventaire.numero} créé ({inventaire.depot.nom}). Le comptage, "
                "la vérification et la validation finale se font dans l'application, "
                "Stock › Inventaire.",
            )
            return redirect(reverse("admin:stock_inventaire_change", args=[inventaire.pk]))
    return _page(
        model_admin,
        request,
        titre="Ajouter un inventaire",
        aide="Choisissez le dépôt et ce que couvre l'inventaire : tout le stock, "
        "une famille, une marque, une nature de monture ou un fournisseur. Les premiers comptages "
        "sont facultatifs ; le même article saisi deux fois s'additionne.",
        entete=entete,
        lignes=lignes,
        titre_lignes="Premiers comptages (facultatif)",
        aide_lignes="Les lignes laissées vides sont ignorées.",
    )


class TransfertForm(forms.Form):
    depot_origine = ChoixDepot(label="Dépôt de départ", queryset=Depot.objects.none())
    depot_destination = ChoixDepot(label="Dépôt destinataire", queryset=Depot.objects.none())
    observation = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)

    def __init__(self, *args, magasins, **kwargs):
        super().__init__(*args, **kwargs)
        ordre = _depots(magasins)
        self.fields["depot_origine"].queryset = Depot.objects.filter(pk__in=[d.pk for d in ordre])
        self.fields["depot_origine"].initial = ordre[0].pk if ordre else None
        societes = {m.societe_id for m in magasins}
        self.fields["depot_destination"].queryset = (
            Depot.objects.filter(
                magasin__societe_id__in=societes, magasin__est_actif=True, est_actif=True
            )
            .select_related("magasin")
            .order_by("magasin__nom", "code")
        )


class LigneTransfertForm(forms.Form):
    article = forms.CharField(label="Code-barres ou référence", max_length=60)
    quantite = forms.IntegerField(label="Quantité", min_value=1, initial=1)

    def clean_article(self):
        try:
            return trouver_article(self.cleaned_data["article"])
        except InventaireImpossible as erreur:
            raise forms.ValidationError(str(erreur)) from None


LignesTransfert = forms.formset_factory(LigneTransfertForm, extra=5, min_num=1, validate_min=True)


def saisir_transfert(model_admin, request):
    """Page « Ajouter un transfert de stock » : l'envoi (réception dans l'application)."""
    magasins = magasins_autorises(request.user, "stock.add_transfertstock")
    if not magasins:
        raise PermissionDenied
    entete = TransfertForm(request.POST or None, magasins=magasins)
    lignes = LignesTransfert(request.POST or None, prefix="lignes")
    if request.method == "POST" and entete.is_valid() and lignes.is_valid():
        donnees = entete.cleaned_data
        try:
            transfert = envoyer_transfert(
                magasin=donnees["depot_origine"].magasin,
                destination=donnees["depot_destination"].magasin,
                depot_origine=donnees["depot_origine"],
                depot_destination=donnees["depot_destination"],
                lignes=[ligne for ligne in lignes.cleaned_data if ligne],
                auteur=request.user,
                observation=donnees["observation"],
            )
        except TransfertImpossible as erreur:
            entete.add_error(None, str(erreur))
        else:
            messages.success(
                request,
                f"Transfert {transfert.numero} envoyé au dépôt {transfert.depot_destination.nom} : "
                "les articles sont sortis du dépôt de départ. Le magasin les réceptionne dans "
                "l'application.",
            )
            return redirect(reverse("admin:stock_transfertstock_change", args=[transfert.pk]))
    return _page(
        model_admin,
        request,
        titre="Ajouter un transfert de stock",
        aide="Le transfert est envoyé dès l'enregistrement. Le magasin de destination le "
        "réceptionne dans l'application, Stock › Liste des Transferts.",
        entete=entete,
        lignes=lignes,
        titre_lignes="Articles envoyés",
    )
