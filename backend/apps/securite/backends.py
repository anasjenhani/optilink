from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import Permission
from django.db.models import Q


def magasin_de(obj):
    """Identifiant du magasin auquel un objet est rattaché, ou ``None`` s'il n'en a pas."""
    from apps.reseau.models import Magasin

    if isinstance(obj, Magasin):
        return obj.pk
    return getattr(obj, "magasin_id", None)


class PermissionsParAffectationBackend(ModelBackend):
    """Authentification Django classique ; permissions tirées des rôles des affectations en cours.

    Sans objet, un utilisateur a une permission si l'un de ses rôles la donne. Sur un objet
    rattaché à un magasin, seuls les rôles dont le périmètre couvre ce magasin comptent : un
    responsable à Lille et vendeur à Arras n'a que les droits de vendeur sur Arras.
    """

    def _get_user_permissions(self, user_obj):
        # Pas de permission individuelle : tout passe par un rôle, pour rester auditable.
        return Permission.objects.none()

    def _get_group_permissions(self, user_obj):
        return Permission.objects.filter(group__affectations__in=user_obj.affectations_actives())

    def has_perm(self, user_obj, perm, obj=None):
        if obj is None:
            return super().has_perm(user_obj, perm)
        magasin_id = magasin_de(obj)
        if magasin_id is None:
            return super().has_perm(user_obj, perm)
        if not user_obj.is_active or user_obj.is_anonymous:
            return False
        return perm in self._permissions_sur_magasin(user_obj, magasin_id)

    def _permissions_sur_magasin(self, user_obj, magasin_id):
        from apps.reseau.models import Magasin

        cache = user_obj.__dict__.setdefault("_perm_cache_par_magasin", {})
        if magasin_id not in cache:
            region_id = (
                Magasin.tous.filter(pk=magasin_id).values_list("region_id", flat=True).first()
            )
            couvrantes = user_obj.affectations_actives().filter(
                Q(portee="reseau")
                | Q(portee="magasin", magasin_id=magasin_id)
                | Q(portee="region", region_id=region_id)
            )
            perms = Permission.objects.filter(group__affectations__in=couvrantes).values_list(
                "content_type__app_label", "codename"
            )
            cache[magasin_id] = {f"{app}.{code}" for app, code in perms}
        return cache[magasin_id]
