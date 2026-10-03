"""Alertes et reporting dans l'administration du serveur (/admin/).

Deux entrées « Pilotage » sans table : chacune affiche une page calculée à la demande, dans
le périmètre (droits et magasins) de l'utilisateur connecté.
"""

import csv
from datetime import date

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from . import reporting
from .alertes import alertes, magasins_couverts
from .models import Alerte, Reporting

# Où traiter chaque alerte dans l'administration.
LISTES = {
    "commandes_en_retard": "ventes_vente",
    "stock_faible": "stock_mouvementstock",
    "clotures_rejetees": "tresorerie_cloturecaisse",
    "clotures_a_verifier": "tresorerie_cloturecaisse",
    "versements_en_retard": "tresorerie_operationtresorerie",
    "conges_a_decider": "rh_demandeconge",
    "acomptes_a_decider": "rh_acompte",
    "primes_a_valider": "rh_prime",
}


class PageCalculee(admin.ModelAdmin):
    """Une page en lecture seule à la place de la liste habituelle."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_module_permission(self, request):
        return self.has_view_permission(request)

    def verifier(self, request):
        # La liste habituelle vérifie ce droit ; la page qui la remplace doit le faire aussi.
        if not self.has_view_permission(request):
            raise PermissionDenied


@admin.register(Alerte)
class AlerteAdmin(PageCalculee):
    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_staff

    def changelist_view(self, request, extra_context=None):
        self.verifier(request)
        lignes = alertes(request.user)
        for ligne in lignes:
            try:
                ligne["lien"] = reverse(f"admin:{LISTES[ligne['code']]}_changelist")
            except (KeyError, NoReverseMatch):
                ligne["lien"] = ""
        contexte = {
            **self.admin_site.each_context(request),
            "title": "Alertes du jour",
            "opts": self.model._meta,
            "alertes": lignes,
        }
        return TemplateResponse(request, "admin/pilotage/alertes.html", contexte)


def _date(texte, defaut):
    try:
        return date.fromisoformat(texte) if texte else defaut
    except ValueError:
        return defaut


@admin.register(Reporting)
class ReportingAdmin(PageCalculee):
    def has_view_permission(self, request, obj=None):
        return request.user.is_staff and request.user.has_perm("ventes.consulter_reporting")

    def changelist_view(self, request, extra_context=None):
        self.verifier(request)
        aujourdhui = timezone.localdate()
        du = _date(request.GET.get("du"), aujourdhui.replace(day=1))
        au = _date(request.GET.get("au"), aujourdhui)
        if du > au:
            du, au = au, du
        magasins = sorted(
            magasins_couverts(request.user, "ventes.consulter_reporting").values(),
            key=lambda m: m.nom,
        )
        choisi = request.GET.get("magasin", "")
        selection = [m for m in magasins if not choisi or str(m.public_id) == choisi]
        sections = reporting.rapport(selection, du, au)
        if request.GET.get("format") == "csv":
            return _csv(sections, du, au)
        contexte = {
            **self.admin_site.each_context(request),
            "title": "Reporting des ventes",
            "opts": self.model._meta,
            "du": du,
            "au": au,
            "magasins": magasins,
            "choisi": choisi,
            "sections": sections,
            "requete": request.GET.urlencode(),
        }
        return TemplateResponse(request, "admin/pilotage/reporting.html", contexte)


def _csv(sections, du, au):
    """Le détail du reporting, à ouvrir dans Excel (séparateur « ; », virgule décimale)."""
    reponse = HttpResponse(content_type="text/csv; charset=utf-8")
    reponse["Content-Disposition"] = f'attachment; filename="reporting-{du}-{au}.csv"'
    reponse.write("﻿")
    ecrire = csv.writer(reponse, delimiter=";").writerow
    nombre = lambda valeur: str(valeur).replace(".", ",")  # noqa: E731
    for s in sections:
        ecrire([f"Reporting du {du:%d/%m/%Y} au {au:%d/%m/%Y}", s["devise"]])
        for libelle, cle in (
            ("Chiffre d'affaires TTC", "ca_ttc"),
            ("Chiffre d'affaires HT", "ca_ht"),
            ("Avoirs TTC", "avoirs_ttc"),
            ("CA net TTC", "ca_net_ttc"),
            ("Nombre de ventes", "nombre_ventes"),
            ("Panier moyen", "panier_moyen"),
        ):
            ecrire([libelle, nombre(s[cle])])
        for titre, lignes, colonnes in (
            ("Par magasin", s["par_magasin"], ("magasin", "nombre", "ca_ttc")),
            ("Par vendeur", s["par_vendeur"], ("vendeur", "nombre", "ca_ttc")),
            ("Par famille", s["par_famille"], ("famille", "quantite", "ca_ttc")),
            ("Encaissements", s["encaissements"], ("mode", "montant")),
            ("Par jour", s["par_jour"], ("jour", "nombre", "ca_ttc")),
        ):
            ecrire([])
            ecrire([titre])
            for ligne in lignes:
                ecrire([ligne[colonnes[0]], *(nombre(ligne[c]) for c in colonnes[1:])])
        ecrire([])
    return reponse
