"""Saisie manuelle dans l'administration du serveur (/admin/) : inventaire, transfert de stock.

Le bouton « Ajouter » de la liste des inventaires crée l'inventaire (magasin, périmètre) et peut
enregistrer de premiers comptages. Tout passe par les mêmes services que l'application ; le
comptage, la vérification et la validation finale se poursuivent dans Stock › Inventaire.
"""

from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse

from apps.achats.admin_saisie import ChoixMagasin, _page, magasins_autorises
from apps.achats.models import Fournisseur
from apps.reseau.models import Magasin

from .inventaires import InventaireImpossible, compter, ouvrir_inventaire, trouver_article
from .models import Article, Monture
from .transferts import TransfertImpossible, envoyer_transfert


class InventaireForm(forms.Form):
    magasin = ChoixMagasin(queryset=Magasin.tous.none())
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
        ordre = sorted(magasins, key=lambda m: (not m.est_depot, m.nom))
        self.fields["magasin"].queryset = Magasin.tous.filter(pk__in=[m.pk for m in ordre])
        self.fields["magasin"].initial = ordre[0].pk if ordre else None
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
                    magasin=donnees["magasin"],
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
                f"Inventaire {inventaire.numero} créé ({inventaire.magasin.nom}). Le comptage, "
                "la vérification et la validation finale se font dans l'application, "
                "Stock › Inventaire.",
            )
            return redirect(reverse("admin:stock_inventaire_change", args=[inventaire.pk]))
    return _page(
        model_admin,
        request,
        titre="Ajouter un inventaire",
        aide="Choisissez le magasin (ou le dépôt) et ce que couvre l'inventaire : tout le stock, "
        "une famille, une marque, une nature de monture ou un fournisseur. Les premiers comptages "
        "sont facultatifs ; le même article saisi deux fois s'additionne.",
        entete=entete,
        lignes=lignes,
        titre_lignes="Premiers comptages (facultatif)",
        aide_lignes="Les lignes laissées vides sont ignorées.",
    )


class TransfertForm(forms.Form):
    magasin = ChoixMagasin(label="Magasin de départ", queryset=Magasin.tous.none())
    destination = ChoixMagasin(queryset=Magasin.tous.none())
    observation = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)

    def __init__(self, *args, magasins, **kwargs):
        super().__init__(*args, **kwargs)
        ordre = sorted(magasins, key=lambda m: (not m.est_depot, m.nom))
        self.fields["magasin"].queryset = Magasin.tous.filter(pk__in=[m.pk for m in ordre])
        self.fields["magasin"].initial = ordre[0].pk if ordre else None
        societes = {m.societe_id for m in ordre}
        self.fields["destination"].queryset = Magasin.tous.filter(
            societe_id__in=societes, est_actif=True
        ).order_by("nom")


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
                magasin=donnees["magasin"],
                destination=donnees["destination"],
                lignes=[ligne for ligne in lignes.cleaned_data if ligne],
                auteur=request.user,
                observation=donnees["observation"],
            )
        except TransfertImpossible as erreur:
            entete.add_error(None, str(erreur))
        else:
            messages.success(
                request,
                f"Transfert {transfert.numero} envoyé à {transfert.destination.nom} : les articles "
                "sont sortis du stock de départ. Le magasin les réceptionne dans l'application.",
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
