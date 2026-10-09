from django.contrib import admin
from django.core.exceptions import PermissionDenied

from core.admin_imports import AvecImport

from .admin_saisie import saisir_inventaire, saisir_transfert
from .models import (
    Article,
    ArticleLentille,
    ArticleMonture,
    ArticleProduit,
    ArticleVerre,
    BonSortie,
    CouleurVerre,
    DemandeTransfert,
    DiametreVerre,
    FamilleVerre,
    Inventaire,
    Lentille,
    LigneDemandeTransfert,
    LigneInventaire,
    LigneSortie,
    LigneTransfert,
    MarqueMonture,
    MatiereVerre,
    Monture,
    MouvementStock,
    PlageVerre,
    PrixArticle,
    SousFamilleVerre,
    TransfertStock,
    Verre,
)


class PrixArticleInline(admin.TabularInline):
    model = PrixArticle
    extra = 1


class MontureInline(admin.StackedInline):
    model = Monture
    fields = (
        ("categorie", "marque", "modele"),
        ("couleur", "couleur_verres", "matiere"),
        ("type", "forme", "genre", "tranche_age"),
        ("calibre", "pont", "branche"),
    )


class VerreInline(admin.StackedInline):
    model = Verre
    fields = (
        ("marque", "gamme"),
        ("geometrie", "indice", "matiere"),
        "traitements",
        ("photochromique", "teinte", "diametre"),
        ("fabrication", "diametre_commercial"),
        ("famille_verre", "sous_famille", "couleur"),
    )
    autocomplete_fields = ("famille_verre", "sous_famille", "couleur")


class PlageVerreInline(admin.TabularInline):
    model = PlageVerre
    extra = 1
    fields = (
        "pays",
        "ordre",
        "sphere_debut",
        "sphere_fin",
        "cylindre_debut",
        "cylindre_fin",
        "prix_achat_ht",
        "prix_vente_ttc",
    )


class LentilleInline(admin.StackedInline):
    model = Lentille
    fields = (
        ("categorie", "marque", "modele", "couleur"),
        ("renouvellement", "type", "lentilles_par_boite"),
        ("rayon", "diametre"),
        ("puissance", "cylindre", "axe", "addition"),
    )


CARACTERISTIQUES = {
    Article.Famille.MONTURE: MontureInline,
    Article.Famille.VERRE: VerreInline,
    Article.Famille.LENTILLE: LentilleInline,
}


@admin.register(Article)
class ArticleAdmin(AvecImport, admin.ModelAdmin):
    imports = ("catalogue", "verres")
    list_display = (
        "reference",
        "libelle",
        "famille",
        "marque",
        "fournisseur",
        "code_barres",
        "sur_commande",
        "est_actif",
    )
    list_filter = ("famille", "sur_commande", "fournisseur", "est_actif")
    autocomplete_fields = ("fournisseur",)
    search_fields = (
        "reference",
        "libelle",
        "code_barres",
        "reference_fournisseur",
        "monture__marque",
        "monture__modele",
        "verre__marque",
        "verre__gamme",
        "lentille__marque",
        "lentille__modele",
    )

    def get_inlines(self, request, obj):
        # À la création, la fiche de la famille choisie est la seule enregistrée : les autres
        # restent vides. Ensuite, seule celle de la famille de l'article est proposée.
        if obj is None:
            return [*CARACTERISTIQUES.values(), PrixArticleInline]
        fiche = CARACTERISTIQUES.get(obj.famille)
        if obj.famille == Article.Famille.VERRE:
            return [fiche, PrixArticleInline, PlageVerreInline]
        return [fiche, PrixArticleInline] if fiche else [PrixArticleInline]

    @admin.display(description="marque")
    def marque(self, article):
        fiche = article.caracteristiques
        return fiche.marque if fiche else ""

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("monture", "verre", "lentille", "fournisseur")
        )


class _ArticlesDeLaFamilleAdmin(ArticleAdmin):
    """Les articles d'une famille (Verres, Montures, Lentilles, Produits), avec leur import.

    Mêmes droits que les articles : ce sont les mêmes fiches, triées par famille.
    """

    list_filter = ("sur_commande", "fournisseur", "est_actif")
    exclude = ("famille",)

    @property
    def famille(self):
        return self.model.famille_affichee

    def get_queryset(self, request):
        return super().get_queryset(request).filter(famille=self.famille)

    def get_inlines(self, request, obj):
        fiche = CARACTERISTIQUES.get(self.famille)
        inlines = [fiche, PrixArticleInline] if fiche else [PrixArticleInline]
        return [*inlines, PlageVerreInline] if self.famille == Article.Famille.VERRE else inlines

    def save_model(self, request, obj, form, change):
        obj.famille = self.famille
        super().save_model(request, obj, form, change)

    def _droit(self, request, action):
        return request.user.has_perm(f"stock.{action}_article")

    def has_view_permission(self, request, obj=None):
        return self._droit(request, "view") or self._droit(request, "change")

    def has_add_permission(self, request):
        return self._droit(request, "add")

    def has_change_permission(self, request, obj=None):
        return self._droit(request, "change")

    def has_delete_permission(self, request, obj=None):
        return self._droit(request, "delete")


@admin.register(ArticleVerre)
class ArticleVerreAdmin(_ArticlesDeLaFamilleAdmin):
    imports = ("verres",)


@admin.register(ArticleMonture)
class ArticleMontureAdmin(_ArticlesDeLaFamilleAdmin):
    imports = ("montures",)


@admin.register(ArticleLentille)
class ArticleLentilleAdmin(_ArticlesDeLaFamilleAdmin):
    imports = ("lentilles",)


@admin.register(ArticleProduit)
class ArticleProduitAdmin(_ArticlesDeLaFamilleAdmin):
    imports = ("produits",)


@admin.register(MouvementStock)
class MouvementStockAdmin(AvecImport, admin.ModelAdmin):
    imports = ("stock",)
    list_display = ("horodatage", "magasin", "article", "type", "quantite", "reference")
    list_filter = ("type", "magasin")
    search_fields = ("article__reference", "reference")

    def get_queryset(self, request):
        return MouvementStock.tous.select_related("magasin", "article")

    # Le stock ne se corrige que par un nouveau mouvement, jamais en modifiant l'historique.
    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class LigneTransfertInline(admin.TabularInline):
    model = LigneTransfert
    extra = 0
    can_delete = False


@admin.register(TransfertStock)
class TransfertStockAdmin(admin.ModelAdmin):
    list_display = ("numero", "cree_le", "magasin", "destination", "statut", "recu_le")
    list_filter = ("statut", "magasin", "destination")
    search_fields = ("numero",)
    inlines = [LigneTransfertInline]

    def get_queryset(self, request):
        return TransfertStock.tous.select_related("magasin", "destination")

    # « Ajouter » envoie le transfert par le même service que l'application ; le magasin de
    # destination le réceptionne dans l'application. Un transfert ne se modifie pas.
    def add_view(self, request, form_url="", extra_context=None):
        if not self.has_add_permission(request):
            raise PermissionDenied
        return saisir_transfert(self, request)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class LigneInventaireInline(admin.TabularInline):
    model = LigneInventaire
    extra = 0
    can_delete = False


@admin.register(Inventaire)
class InventaireAdmin(admin.ModelAdmin):
    list_display = ("numero", "cree_le", "magasin", "famille", "statut", "valide_le")
    list_filter = ("statut", "magasin", "famille")
    search_fields = ("numero",)
    inlines = [LigneInventaireInline]

    def get_queryset(self, request):
        return Inventaire.tous.select_related("magasin")

    # « Ajouter » crée l'inventaire (et de premiers comptages) par le même service que
    # l'application ; le comptage et la validation finale se poursuivent dans l'application.
    def add_view(self, request, form_url="", extra_context=None):
        if not self.has_add_permission(request):
            raise PermissionDenied
        return saisir_inventaire(self, request)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# Listes de référence des verres et des montures : on désactive au lieu de supprimer (les
# verres déjà créés gardent leur famille, leur sous-famille et leur couleur).
class _ListeAdmin(AvecImport, admin.ModelAdmin):
    list_filter = ("est_actif",)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MarqueMonture)
class MarqueMontureAdmin(_ListeAdmin):
    imports = ("marques_montures",)
    list_display = ("code", "libelle", "est_actif")
    search_fields = ("code", "libelle")


@admin.register(MatiereVerre)
class MatiereVerreAdmin(_ListeAdmin):
    imports = ("matieres_verres",)
    list_display = ("code", "libelle", "est_actif")
    search_fields = ("code", "libelle")


class SousFamilleInline(admin.TabularInline):
    model = SousFamilleVerre
    fields = ("code", "libelle", "foyer", "est_actif")
    extra = 0
    show_change_link = True

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FamilleVerre)
class FamilleVerreAdmin(_ListeAdmin):
    imports = ("familles_verres",)
    list_display = ("code", "libelle", "fournisseur", "foyer", "est_actif")
    list_filter = ("est_actif", "foyer", "fournisseur")
    search_fields = ("code", "libelle")
    inlines = [SousFamilleInline]


@admin.register(SousFamilleVerre)
class SousFamilleVerreAdmin(_ListeAdmin):
    imports = ("sous_familles_verres",)
    list_display = ("code", "libelle", "famille", "foyer", "est_actif")
    list_filter = ("est_actif", "foyer", "famille__fournisseur")
    search_fields = ("code", "libelle", "famille__libelle")
    autocomplete_fields = ("famille",)


@admin.register(CouleurVerre)
class CouleurVerreAdmin(_ListeAdmin):
    imports = ("couleurs_verres",)
    list_display = ("code", "libelle", "fournisseur", "famille_couleur", "est_actif")
    list_filter = ("est_actif", "famille_couleur", "fournisseur")
    search_fields = ("code", "libelle")


@admin.register(DiametreVerre)
class DiametreVerreAdmin(_ListeAdmin):
    imports = ("diametres_verres",)
    list_display = ("code", "diametre_commercial", "diametre_reel", "fournisseur", "est_actif")
    list_filter = ("est_actif", "fournisseur")
    search_fields = ("code", "diametre_commercial")


class LectureSeule:
    """Saisis et traités depuis l'application, consultés ici."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class LigneSortieInline(LectureSeule, admin.TabularInline):
    model = LigneSortie


@admin.register(BonSortie)
class BonSortieAdmin(LectureSeule, admin.ModelAdmin):
    list_display = ("numero", "cree_le", "magasin", "type", "motif")
    list_filter = ("type", "magasin")
    search_fields = ("numero", "motif")
    inlines = [LigneSortieInline]

    def get_queryset(self, request):
        return BonSortie.tous.select_related("magasin")


class LigneDemandeInline(LectureSeule, admin.TabularInline):
    model = LigneDemandeTransfert


@admin.register(DemandeTransfert)
class DemandeTransfertAdmin(LectureSeule, admin.ModelAdmin):
    list_display = ("numero", "cree_le", "magasin", "aupres_de", "statut", "transfert")
    list_filter = ("statut", "magasin", "aupres_de")
    search_fields = ("numero",)
    inlines = [LigneDemandeInline]

    def get_queryset(self, request):
        return DemandeTransfert.tous.select_related("magasin", "aupres_de", "transfert")
