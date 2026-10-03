from django.contrib import admin

from .models import Acompte, DemandeConge, Employe, Pointage, Prime


@admin.register(Employe)
class EmployeAdmin(admin.ModelAdmin):
    list_display = ("matricule", "nom", "prenom", "poste", "magasin", "date_embauche")
    list_filter = ("magasin",)
    search_fields = ("matricule", "nom", "prenom", "cin")


@admin.register(Pointage)
class PointageAdmin(admin.ModelAdmin):
    list_display = ("date", "employe", "statut", "arrivee", "depart")
    list_filter = ("statut", "magasin")

    def has_add_permission(self, request):
        return False


@admin.register(DemandeConge)
class DemandeCongeAdmin(admin.ModelAdmin):
    list_display = ("employe", "type", "debut", "fin", "jours", "statut", "decidee_par")
    list_filter = ("statut", "type", "magasin")

    # Le solde et les chevauchements sont vérifiés par l'application.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Acompte)
class AcompteAdmin(admin.ModelAdmin):
    list_display = ("employe", "montant", "mois", "statut", "decide_par", "verse_le")
    list_filter = ("statut", "magasin")

    # Le plafond et les décisions sont vérifiés par l'application.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Prime)
class PrimeAdmin(admin.ModelAdmin):
    list_display = ("employe", "type", "montant", "mois", "statut", "validee_par")
    list_filter = ("statut", "type", "magasin")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
