from django.contrib import admin

from .models import Magasin, Region


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ("code", "nom")
    search_fields = ("code", "nom")


@admin.register(Magasin)
class MagasinAdmin(admin.ModelAdmin):
    list_display = ("code", "nom", "region", "ville", "est_actif")
    list_filter = ("region", "est_actif")
    search_fields = ("code", "nom", "ville")
