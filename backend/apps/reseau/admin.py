from django.contrib import admin

from .models import Magasin, Pays, Region, TauxTva


class TauxTvaInline(admin.TabularInline):
    model = TauxTva
    extra = 1


@admin.register(Pays)
class PaysAdmin(admin.ModelAdmin):
    inlines = [TauxTvaInline]
    list_display = ("code", "nom", "devise", "decimales", "timbre_fiscal")


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ("code", "nom")
    search_fields = ("code", "nom")


@admin.register(Magasin)
class MagasinAdmin(admin.ModelAdmin):
    list_display = ("code", "nom", "pays", "region", "ville", "est_actif")
    list_filter = ("pays", "region", "est_actif")
    search_fields = ("code", "nom", "ville")
