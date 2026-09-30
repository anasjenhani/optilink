from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Affectation, Utilisateur


class AffectationInline(admin.TabularInline):
    model = Affectation
    extra = 0


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    inlines = [AffectationInline]
