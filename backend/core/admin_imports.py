"""Imports Excel / CSV dans l'administration du serveur (/admin/).

Chaque liste concernée (fournisseurs, articles, bons de réception, clients, utilisateurs…) a
un bouton « Importer » : modèles Excel et CSV à télécharger, puis « Vérifier » et
« Importer », comme dans l'application. Le fichier vérifié est gardé une heure côté serveur :
l'import enregistre exactement ce qui a été vérifié, sans le renvoyer.
"""

import hmac
from collections.abc import Callable
from dataclasses import dataclass

from django.contrib import messages
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

from apps.achats.imports import importer_fournisseurs, importer_receptions
from apps.crm.imports import importer_clients
from apps.optique.imports import importer_ophtalmologues
from apps.reseau.models import Magasin
from apps.securite.imports import importer_utilisateurs
from apps.stock.imports import (
    FichierIllisible,
    importer_catalogue,
    importer_stock,
    jeton_de_verification,
    lire_tableau,
)
from apps.stock.imports_referentiels import LISTES, importer_liste
from apps.stock.models import Article

from .modeles_import import MODELES, fichier_csv, fichier_xlsx

DUREE = 3600


@dataclass(frozen=True)
class Traitement:
    """Droits exigés, magasin à choisir (droit vérifié sur ce magasin) et import à lancer."""

    permissions: tuple
    lancer: Callable
    droit_magasin: str = ""
    piece: bool = False
    aide: str = ""


TRAITEMENTS = {
    "catalogue": Traitement(
        (
            "stock.add_article",
            "stock.change_article",
            "stock.add_prixarticle",
            "stock.change_prixarticle",
        ),
        lambda lignes, m, u, piece, apercu: importer_catalogue(lignes, pays=m.pays, apercu=apercu),
        droit_magasin="stock.view_article",
        aide="Prix et TVA dans le pays du magasin choisi.",
    ),
    "verres": Traitement(
        (
            "stock.add_article",
            "stock.change_article",
            "stock.add_prixarticle",
            "stock.change_prixarticle",
        ),
        lambda lignes, m, u, piece, apercu: importer_catalogue(
            lignes, pays=m.pays, apercu=apercu, famille=Article.Famille.VERRE
        ),
        droit_magasin="stock.view_article",
        aide="Prix et TVA dans le pays du magasin choisi.",
    ),
    **{
        quoi: Traitement(
            (
                "stock.add_article",
                "stock.change_article",
                "stock.add_prixarticle",
                "stock.change_prixarticle",
            ),
            lambda lignes, m, u, piece, apercu, famille=famille: importer_catalogue(
                lignes, pays=m.pays, apercu=apercu, famille=famille
            ),
            droit_magasin="stock.view_article",
            aide="Prix et TVA dans le pays du magasin choisi.",
        )
        for quoi, famille in (
            ("montures", Article.Famille.MONTURE),
            ("lentilles", Article.Famille.LENTILLE),
            ("produits", Article.Famille.DIVERS),
        )
    },
    "stock": Traitement(
        ("stock.add_mouvementstock",),
        lambda lignes, m, u, piece, apercu: importer_stock(
            lignes, magasin=m, utilisateur=u, piece=piece, apercu=apercu
        ),
        droit_magasin="stock.add_mouvementstock",
        piece=True,
    ),
    "clients": Traitement(
        ("crm.add_client", "crm.change_client"),
        lambda lignes, m, u, piece, apercu: importer_clients(lignes, magasin=m, apercu=apercu),
        droit_magasin="crm.add_client",
    ),
    "fournisseurs": Traitement(
        ("achats.add_fournisseur", "achats.change_fournisseur"),
        lambda lignes, m, u, piece, apercu: importer_fournisseurs(
            lignes, pays=m.pays, apercu=apercu
        ),
        droit_magasin="achats.add_fournisseur",
        aide="Le pays du magasin choisi est le pays par défaut des fournisseurs.",
    ),
    "receptions": Traitement(
        ("achats.add_bonreception",),
        lambda lignes, m, u, piece, apercu: importer_receptions(
            lignes, magasin=m, utilisateur=u, apercu=apercu
        ),
        droit_magasin="achats.add_bonreception",
    ),
    "ophtalmologues": Traitement(
        ("optique.add_ophtalmologue", "optique.change_ophtalmologue"),
        lambda lignes, m, u, piece, apercu: importer_ophtalmologues(lignes, apercu=apercu),
        aide="Le fichier « Medecin » de l'ancien logiciel s'importe tel quel.",
    ),
    "utilisateurs": Traitement(
        ("securite.add_utilisateur", "securite.add_affectation"),
        lambda lignes, m, u, piece, apercu: importer_utilisateurs(
            lignes, demandeur=u, apercu=apercu
        ),
    ),
}


def _traitement_liste(quoi):
    modele = LISTES[quoi].modele._meta.model_name
    return Traitement(
        (f"stock.add_{modele}", f"stock.change_{modele}"),
        lambda lignes, m, u, piece, apercu: importer_liste(quoi, lignes, apercu=apercu),
    )


TRAITEMENTS |= {quoi: _traitement_liste(quoi) for quoi in LISTES}


def _magasins(utilisateur, traitement):
    if not traitement.droit_magasin:
        return []
    return [
        m
        for m in Magasin.tous.select_related("pays").order_by("nom")
        if utilisateur.has_perm(traitement.droit_magasin, m)
    ]


class AvecImport:
    """À mettre avant ``admin.ModelAdmin`` : ajoute « Importer » à la liste."""

    imports: tuple = ()
    change_list_template = "admin/change_list_import.html"

    def get_urls(self):
        info = (self.model._meta.app_label, self.model._meta.model_name)
        propres = [
            path(
                "importer/<str:type_import>/",
                self.admin_site.admin_view(self.page_import),
                name=f"{info[0]}_{info[1]}_importer",
            ),
            path(
                "importer/<str:type_import>/modele.<str:extension>",
                self.admin_site.admin_view(self.modele_import),
                name=f"{info[0]}_{info[1]}_modele",
            ),
        ]
        return propres + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        info = (self.model._meta.app_label, self.model._meta.model_name)
        boutons = [
            {
                "url": reverse(f"admin:{info[0]}_{info[1]}_importer", args=[t]),
                "libelle": f"Importer : {MODELES[t].titre.lower()}",
            }
            for t in self.imports
            if request.user.has_perms(TRAITEMENTS[t].permissions)
        ]
        return super().changelist_view(request, {**(extra_context or {}), "imports": boutons})

    def _traitement(self, request, type_import):
        if type_import not in self.imports:
            raise Http404
        traitement = TRAITEMENTS[type_import]
        if not request.user.has_perms(traitement.permissions):
            raise PermissionDenied
        return traitement

    def modele_import(self, request, type_import, extension):
        self._traitement(request, type_import)
        if extension not in ("xlsx", "csv"):
            raise Http404
        modele = MODELES[type_import]
        if extension == "csv":
            reponse = HttpResponse(fichier_csv(modele), content_type="text/csv; charset=utf-8")
        else:
            reponse = HttpResponse(
                fichier_xlsx(modele),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        reponse["Content-Disposition"] = f'attachment; filename="modele-{type_import}.{extension}"'
        return reponse

    def page_import(self, request, type_import):
        traitement = self._traitement(request, type_import)
        magasins = _magasins(request.user, traitement)
        if traitement.droit_magasin and not magasins:
            raise PermissionDenied
        choisi = request.POST.get("magasin", "")
        magasin = next((m for m in magasins if str(m.public_id) == choisi), None)
        if magasin is None and magasins:
            magasin = magasins[0]
        piece = request.POST.get("piece", "")[:60] if traitement.piece else ""
        rapport, jeton, nom = None, "", ""
        contexte_jeton = (type_import, request.user.pk, magasin.pk if magasin else "", piece)

        if request.method == "POST":
            if "importer" in request.POST:
                jeton = request.POST.get("jeton", "")
                garde = cache.get(f"import-admin:{request.user.pk}:{jeton}")
                if not garde or not hmac.compare_digest(
                    jeton_de_verification(garde["contenu"], *contexte_jeton), jeton
                ):
                    messages.error(request, "Vérifiez de nouveau le fichier avant de l'importer.")
                    return redirect(request.path)
                nom, contenu, apercu = garde["nom"], garde["contenu"], False
            else:
                fichier = request.FILES.get("fichier")
                if fichier is None:
                    messages.error(request, "Choisissez un fichier Excel (.xlsx) ou CSV.")
                    return redirect(request.path)
                nom, contenu, apercu = fichier.name, fichier.read(), True
            try:
                lignes = lire_tableau(SimpleUploadedFile(nom, contenu))
            except FichierIllisible as erreur:
                messages.error(request, str(erreur))
                return redirect(request.path)
            rapport = traitement.lancer(lignes, magasin, request.user, piece, apercu)
            if apercu and not rapport.erreurs:
                jeton = jeton_de_verification(contenu, *contexte_jeton)
                cache.set(
                    f"import-admin:{request.user.pk}:{jeton}",
                    {"nom": nom, "contenu": contenu},
                    DUREE,
                )
            elif not apercu:
                cache.delete(f"import-admin:{request.user.pk}:{jeton}")
                jeton = ""

        info = (self.model._meta.app_label, self.model._meta.model_name)
        modele = MODELES[type_import]
        contexte = {
            **self.admin_site.each_context(request),
            "title": f"Importer : {modele.titre.lower()}",
            "opts": self.model._meta,
            "modele": modele,
            "aide": traitement.aide,
            "obligatoires": [c for c in modele.colonnes if c in modele.obligatoires],
            "url_excel": reverse(f"admin:{info[0]}_{info[1]}_modele", args=[type_import, "xlsx"]),
            "url_csv": reverse(f"admin:{info[0]}_{info[1]}_modele", args=[type_import, "csv"]),
            "url_liste": reverse(f"admin:{info[0]}_{info[1]}_changelist"),
            "magasins": magasins,
            "magasin": magasin,
            "piece": piece if traitement.piece else None,
            "rapport": rapport,
            "jeton": jeton,
            "nom": nom,
        }
        return TemplateResponse(request, "admin/import.html", contexte)
