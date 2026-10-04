"""Site d'administration d'OptiLink : second facteur obligatoire et onglets horizontaux.

Les applications Django sont regroupées en onglets métier (Ventes, Stock et achats…) affichés
en haut de chaque page, à la place du menu latéral.
"""

from django.urls import reverse
from django_otp.admin import OTPAdminSite

# (identifiant, libellé, applications Django de l'onglet)
ONGLETS = [
    ("ventes", "Ventes", ["ventes", "crm", "optique"]),
    ("stock", "Stock et achats", ["stock", "achats"]),
    ("caisse", "Caisse et banque", ["tresorerie"]),
    ("rh", "RH", ["rh"]),
    ("pilotage", "Alertes et reporting", ["pilotage"]),
    ("reseau", "Réseau", ["reseau"]),
    ("securite", "Sécurité", ["securite", "auth", "otp_totp", "otp_static", "auditlog"]),
]
ONGLET_DE = {app: onglet for onglet, _, apps in ONGLETS for app in apps}


class OptiLinkAdminSite(OTPAdminSite):
    site_header = "OptiLink · Administration"
    site_title = "OptiLink"
    index_title = "Administration"
    enable_nav_sidebar = False

    def _onglet_actif(self, request):
        if request.GET.get("onglet"):
            return request.GET["onglet"]
        # /admin/<application>/… : l'onglet de cette application.
        morceaux = request.path.removeprefix(reverse("admin:index")).split("/")
        return ONGLET_DE.get(morceaux[0], "autres") if morceaux[0] else ""

    def each_context(self, request):
        contexte = super().each_context(request)
        visibles = {app["app_label"] for app in contexte.get("available_apps", [])}
        actif = self._onglet_actif(request)
        onglets = [
            (identifiant, libelle)
            for identifiant, libelle, apps in ONGLETS
            if visibles.intersection(apps)
        ]
        if visibles - set(ONGLET_DE):
            onglets.append(("autres", "Autres"))
        accueil = reverse("admin:index", current_app=self.name)
        contexte["onglets"] = [
            {
                "libelle": libelle,
                "url": f"{accueil}?onglet={identifiant}",
                "actif": identifiant == actif,
            }
            for identifiant, libelle in onglets
        ]
        return contexte

    def get_app_list(self, request, app_label=None):
        """« Modifications des droits » (app securite) rejoint la section du journal d'audit."""
        apps = super().get_app_list(request)
        par_label = {app["app_label"]: app for app in apps}
        journal, securite = par_label.get("auditlog"), par_label.get("securite")
        if journal is not None:
            journal["name"] = "Journal d'audit"
            for modele in journal["models"]:
                if modele["object_name"] == "LogEntry":
                    modele["name"] = "Historique complet des modifications"
            if securite is not None:
                droits = [m for m in securite["models"] if m["object_name"] == "ModificationDroits"]
                securite["models"] = [m for m in securite["models"] if m not in droits]
                journal["models"] = droits + journal["models"]
        if app_label:
            return [app for app in apps if app["app_label"] == app_label]
        return apps

    def index(self, request, extra_context=None):
        reponse = super().index(request, extra_context)
        onglet = request.GET.get("onglet")
        if onglet and hasattr(reponse, "context_data"):
            libelles = {ident: libelle for ident, libelle, _ in ONGLETS} | {"autres": "Autres"}
            reponse.context_data["app_list"] = [
                app
                for app in reponse.context_data["app_list"]
                if ONGLET_DE.get(app["app_label"], "autres") == onglet
            ]
            reponse.context_data["title"] = libelles.get(onglet, self.index_title)
        return reponse
