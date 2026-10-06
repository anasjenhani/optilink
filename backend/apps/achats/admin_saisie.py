"""Saisie manuelle dans l'administration du serveur (/admin/) : bon de réception, facture achat,
bon retour fournisseur.

Le bouton « Ajouter » de ces listes ouvre un formulaire simple. L'enregistrement passe par
les mêmes services que l'application (contrôles, numéro, stock, totaux figés).
"""

from decimal import Decimal

from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse

from apps.reseau.models import Magasin
from apps.ventes.services import _aujourd_hui

from .factures import FactureImpossible, enregistrer_facture, timbre_par_defaut
from .imports import _article
from .models import BonReception, Fournisseur
from .receptions import ReceptionImpossible, enregistrer_reception, taux_tva_par_defaut
from .retours import RetourImpossible, enregistrer_retour

DECIMAL = {"max_digits": 12, "decimal_places": 3}
TAUX = {"max_digits": 5, "decimal_places": 2, "min_value": 0, "max_value": 100}


def magasins_autorises(utilisateur, permission):
    return [
        m
        for m in Magasin.tous.select_related("pays").order_by("nom")
        if utilisateur.has_perm(permission, m)
    ]


class ChoixMagasin(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.nom


class EnteteReceptionForm(forms.Form):
    magasin = ChoixMagasin(queryset=Magasin.tous.none())
    fournisseur = forms.ModelChoiceField(queryset=Fournisseur.objects.filter(est_actif=True))
    numero_bl = forms.CharField(label="N° du BL", max_length=60)
    date_bl = forms.DateField(label="Date du BL", widget=forms.DateInput(attrs={"type": "date"}))
    taux_remise_ex = forms.DecimalField(
        label="Remise exceptionnelle (%)", initial=Decimal("0"), **TAUX
    )
    observation = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)

    def __init__(self, *args, magasins, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["magasin"].queryset = Magasin.tous.filter(pk__in=[m.pk for m in magasins])
        self.fields["magasin"].initial = magasins[0].pk if magasins else None
        self.fields["fournisseur"].queryset = Fournisseur.objects.filter(est_actif=True).order_by(
            "nom"
        )


class LigneReceptionForm(forms.Form):
    article = forms.CharField(label="Code-barres ou référence", max_length=60)
    quantite = forms.IntegerField(label="Quantité", min_value=1, initial=1)
    prix_achat_ht = forms.DecimalField(label="Prix d'achat HT", min_value=0, **DECIMAL)
    taux_remise = forms.DecimalField(label="Remise %", required=False, **TAUX)
    taux_tva = forms.DecimalField(
        label="TVA %", required=False, help_text="Vide : taux de l'article.", **TAUX
    )
    numero_serie = forms.CharField(label="N° de série", max_length=60, required=False)
    numero_lot = forms.CharField(label="N° de lot", max_length=60, required=False)

    def clean_article(self):
        texte = self.cleaned_data["article"].strip()
        return _article({"code_barres": texte, "reference": texte})


LignesReception = forms.formset_factory(LigneReceptionForm, extra=3, min_num=1, validate_min=True)


def saisir_reception(model_admin, request):
    """Page « Ajouter un bon de réception » de l'administration."""
    magasins = magasins_autorises(request.user, "achats.add_bonreception")
    if not magasins:
        raise PermissionDenied
    entete = EnteteReceptionForm(request.POST or None, magasins=magasins)
    lignes = LignesReception(request.POST or None, prefix="lignes")
    if request.method == "POST" and entete.is_valid() and lignes.is_valid():
        donnees = entete.cleaned_data
        details = [
            {
                "article": ligne["article"],
                "quantite": ligne["quantite"],
                "prix_achat_ht": ligne["prix_achat_ht"],
                "taux_remise": ligne["taux_remise"] or Decimal("0"),
                "taux_tva": ligne["taux_tva"],
                "non_conforme": False,
                "motif": "",
                "numero_serie": ligne["numero_serie"],
                "numero_lot": ligne["numero_lot"],
            }
            for ligne in lignes.cleaned_data
            if ligne
        ]
        magasin = donnees["magasin"]
        sans_taux = [d["article"] for d in details if d["taux_tva"] is None]
        defauts = taux_tva_par_defaut(sans_taux, magasin.pays) if sans_taux else {}
        for d in details:
            if d["taux_tva"] is None:
                d["taux_tva"] = defauts[d["article"].pk]
        try:
            with transaction.atomic():
                bon = enregistrer_reception(
                    magasin=magasin,
                    fournisseur=donnees["fournisseur"],
                    numero_bl=donnees["numero_bl"],
                    date_bl=donnees["date_bl"],
                    lignes=details,
                    auteur=request.user,
                    taux_remise_ex=donnees["taux_remise_ex"],
                    observation=donnees["observation"],
                )
        except (ReceptionImpossible, ValidationError) as erreur:
            message = erreur.messages if isinstance(erreur, ValidationError) else str(erreur)
            entete.add_error(None, message)
        else:
            messages.success(
                request,
                f"Bon de réception {bon.numero} enregistré (BL {bon.numero_bl}, "
                f"{bon.total_ttc} TTC). Les articles sont entrés en stock.",
            )
            return redirect(reverse("admin:achats_bonreception_change", args=[bon.pk]))
    return _page(
        model_admin,
        request,
        titre="Ajouter un bon de réception",
        aide="Pour les articles en stock (montures, lentilles, produits). Les verres commandés "
        "pour un client se reçoivent dans l'application avec « Importer Bon Commande ».",
        entete=entete,
        lignes=lignes,
    )


class FactureAchatForm(forms.Form):
    magasin = ChoixMagasin(queryset=Magasin.tous.none())
    fournisseur = forms.ModelChoiceField(queryset=Fournisseur.objects.all())
    reference_fournisseur = forms.CharField(
        label="Référence fournisseur", max_length=60, help_text="Le n° de sa facture."
    )
    date_reference = forms.DateField(
        label="Date référence", widget=forms.DateInput(attrs={"type": "date"})
    )
    date_entree = forms.DateField(
        label="Date d'entrée",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Vide : aujourd'hui.",
    )
    bons = forms.ModelMultipleChoiceField(
        label="Bons de livraison (BL) à facturer",
        queryset=BonReception.tous.none(),
        widget=forms.CheckboxSelectMultiple,
    )
    taux_remise_ex = forms.DecimalField(
        label="Taux remise exceptionnelle (%)", initial=Decimal("0"), **TAUX
    )
    frais_supplementaires = forms.DecimalField(
        label="Frais supplémentaires", initial=Decimal("0"), min_value=0, **DECIMAL
    )
    timbre_fiscal = forms.DecimalField(
        label="Timbre fiscal",
        required=False,
        min_value=0,
        help_text="Vide : celui du pays si la fiche du fournisseur le prévoit.",
        **DECIMAL,
    )
    ajustement = forms.DecimalField(
        label="Ajustement du total", initial=Decimal("0"), help_text="Écart d'arrondi.", **DECIMAL
    )
    observation = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)

    def __init__(self, *args, magasins, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["magasin"].queryset = Magasin.tous.filter(pk__in=[m.pk for m in magasins])
        self.fields["magasin"].initial = magasins[0].pk if magasins else None
        self.fields["fournisseur"].queryset = Fournisseur.objects.order_by("nom")
        bons = (
            BonReception.tous.filter(magasin__in=magasins, facture__isnull=True)
            .select_related("fournisseur", "magasin")
            .order_by("fournisseur__nom", "date_bl", "sequence")
        )
        self.fields["bons"].queryset = bons
        self.fields["bons"].label_from_instance = lambda b: (
            f"{b.fournisseur.nom} : BL {b.numero_bl} du {b.date_bl:%d/%m/%Y} "
            f"({b.numero}, {b.magasin.nom}), {b.total_ttc} TTC"
        )


def saisir_facture(model_admin, request):
    """Page « Ajouter une facture achat » de l'administration."""
    magasins = magasins_autorises(request.user, "achats.add_factureachat")
    if not magasins:
        raise PermissionDenied
    formulaire = FactureAchatForm(request.POST or None, magasins=magasins)
    if request.method == "POST" and formulaire.is_valid():
        donnees = formulaire.cleaned_data
        magasin, fournisseur = donnees["magasin"], donnees["fournisseur"]
        timbre = donnees["timbre_fiscal"]
        if timbre is None:
            timbre = timbre_par_defaut(fournisseur, magasin.pays)
        try:
            with transaction.atomic():
                facture = enregistrer_facture(
                    magasin=magasin,
                    fournisseur=fournisseur,
                    reference_fournisseur=donnees["reference_fournisseur"],
                    date_reference=donnees["date_reference"],
                    date_entree=donnees["date_entree"] or _aujourd_hui(magasin.pays),
                    bons=[b.public_id for b in donnees["bons"]],
                    auteur=request.user,
                    taux_remise_ex=donnees["taux_remise_ex"],
                    frais=donnees["frais_supplementaires"],
                    timbre=timbre,
                    ajustement=donnees["ajustement"],
                    observation=donnees["observation"],
                )
        except FactureImpossible as erreur:
            formulaire.add_error(None, str(erreur))
        else:
            messages.success(
                request,
                f"Facture achat {facture.numero} enregistrée ({facture.total_ttc} TTC). "
                "Ses BL sont marqués « Facturé ».",
            )
            return redirect(reverse("admin:achats_factureachat_change", args=[facture.pk]))
    return _page(
        model_admin,
        request,
        titre="Ajouter une facture achat",
        aide="Cochez les BL du fournisseur que regroupe sa facture. Les totaux se calculent à "
        "partir des BL ; utilisez « Ajustement du total » pour retrouver le total de la facture "
        "papier.",
        entete=formulaire,
    )


class EnteteRetourForm(forms.Form):
    magasin = ChoixMagasin(queryset=Magasin.tous.none())
    fournisseur = forms.ModelChoiceField(queryset=Fournisseur.objects.filter(est_actif=True))
    date_retour = forms.DateField(
        label="Date du retour", widget=forms.DateInput(attrs={"type": "date"}), required=False
    )
    motif = forms.CharField(max_length=200, required=False)
    observation = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)

    def __init__(self, *args, magasins, **kwargs):
        super().__init__(*args, **kwargs)
        # Le dépôt central d'abord : c'est lui qui renvoie au fournisseur.
        ordre = sorted(magasins, key=lambda m: (not m.est_depot, m.nom))
        self.fields["magasin"].queryset = Magasin.tous.filter(pk__in=[m.pk for m in ordre])
        self.fields["magasin"].initial = ordre[0].pk if ordre else None
        self.fields["fournisseur"].queryset = Fournisseur.objects.filter(est_actif=True).order_by(
            "nom"
        )


class LigneRetourForm(forms.Form):
    article = forms.CharField(label="Code-barres ou référence", max_length=60)
    quantite = forms.IntegerField(label="Quantité", min_value=1, initial=1)
    prix_achat_ht = forms.DecimalField(label="Prix d'achat HT", min_value=0, **DECIMAL)
    taux_remise = forms.DecimalField(label="Remise %", required=False, **TAUX)
    taux_tva = forms.DecimalField(
        label="TVA %", required=False, help_text="Vide : taux de l'article.", **TAUX
    )
    motif = forms.CharField(max_length=200, required=False)

    def clean_article(self):
        texte = self.cleaned_data["article"].strip()
        return _article({"code_barres": texte, "reference": texte})


LignesRetour = forms.formset_factory(LigneRetourForm, extra=3, min_num=1, validate_min=True)


def saisir_retour(model_admin, request):
    """Page « Ajouter un bon retour fournisseur » de l'administration (articles du stock)."""
    magasins = magasins_autorises(request.user, "achats.add_bonretour")
    if not magasins:
        raise PermissionDenied
    entete = EnteteRetourForm(request.POST or None, magasins=magasins)
    lignes = LignesRetour(request.POST or None, prefix="lignes")
    if request.method == "POST" and entete.is_valid() and lignes.is_valid():
        donnees = entete.cleaned_data
        magasin = donnees["magasin"]
        details = [
            {
                "article": ligne["article"],
                "quantite": ligne["quantite"],
                "prix_achat_ht": ligne["prix_achat_ht"],
                "taux_remise": ligne["taux_remise"] or Decimal("0"),
                "taux_tva": ligne["taux_tva"],
                "motif": ligne["motif"],
            }
            for ligne in lignes.cleaned_data
            if ligne
        ]
        sans_taux = [d["article"] for d in details if d["taux_tva"] is None]
        defauts = taux_tva_par_defaut(sans_taux, magasin.pays) if sans_taux else {}
        for d in details:
            if d["taux_tva"] is None:
                d["taux_tva"] = defauts[d["article"].pk]
        try:
            with transaction.atomic():
                bon = enregistrer_retour(
                    magasin=magasin,
                    fournisseur=donnees["fournisseur"],
                    lignes=details,
                    auteur=request.user,
                    date_retour=donnees["date_retour"],
                    motif=donnees["motif"],
                    observation=donnees["observation"],
                )
        except (RetourImpossible, ValidationError) as erreur:
            message = erreur.messages if isinstance(erreur, ValidationError) else str(erreur)
            entete.add_error(None, message)
        else:
            messages.success(
                request,
                f"Bon retour {bon.numero} enregistré ({bon.total_ttc} TTC). "
                "Les articles sont sortis du stock.",
            )
            return redirect(reverse("admin:achats_bonretour_change", args=[bon.pk]))
    return _page(
        model_admin,
        request,
        titre="Ajouter un bon retour fournisseur",
        aide="Pour renvoyer des articles du stock. Les articles non conformes d'un bon de "
        "réception se renvoient dans l'application, Stock › Bon Retour Fournisseur.",
        entete=entete,
        lignes=lignes,
        titre_lignes="Articles renvoyés",
    )


def _page(
    model_admin,
    request,
    *,
    titre,
    aide,
    entete,
    lignes=None,
    titre_lignes="Articles reçus",
    aide_lignes="Les lignes laissées vides sont ignorées. TVA vide : taux de l'article dans le "
    "pays du magasin.",
):
    opts = model_admin.model._meta
    contexte = {
        **model_admin.admin_site.each_context(request),
        "title": titre,
        "opts": opts,
        "aide": aide,
        "entete": entete,
        "lignes": lignes,
        "titre_lignes": titre_lignes,
        "aide_lignes": aide_lignes,
        "url_liste": reverse(f"admin:{opts.app_label}_{opts.model_name}_changelist"),
    }
    return TemplateResponse(request, "admin/saisie_achat.html", contexte)
