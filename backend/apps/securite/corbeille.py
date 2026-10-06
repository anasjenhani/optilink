"""Corbeille : ce qu'on supprime part d'abord à la corbeille, d'où on peut le restaurer.

Une suppression enregistre l'objet et tout ce que la base supprime avec lui (lignes, fiches
liées), puis le supprime. La restauration recrée le tout à l'identique (mêmes identifiants),
dans une transaction : si un élément lié a disparu entre-temps ou qu'un doublon est apparu,
rien n'est restauré et le message l'explique. Passé le délai de grâce (``CORBEILLE_JOURS``),
la tâche de nuit ``vider_corbeille`` supprime définitivement les éléments expirés.
"""

import datetime
import json

from django.conf import settings
from django.contrib.admin.utils import NestedObjects
from django.core import serializers
from django.db import DEFAULT_DB_ALIAS, IntegrityError, transaction
from django.utils import timezone

from .models import ElementCorbeille

# Ce qui ne passe jamais par la corbeille : la corbeille elle-même, les journaux, les sessions
# et les seconds facteurs (un appareil MFA supprimé ne doit pas pouvoir revenir).
EXCLUS = {
    "securite.elementcorbeille",
    "securite.evenementsecurite",
    "auditlog.logentry",
    "sessions.session",
    "otp_totp.totpdevice",
    "otp_static.staticdevice",
    "otp_static.statictoken",
}


class RestaurationImpossible(Exception):
    pass


def concerne(modele):
    # Un modèle proxy (vue d'un journal, par exemple) suit le modèle qu'il présente.
    return modele._meta.concrete_model._meta.label_lower not in EXCLUS


def _objets_lies(objet):
    """L'objet et tout ce que sa suppression emporte (cascade), dans l'ordre de collecte."""
    collecteur = NestedObjects(using=DEFAULT_DB_ALIAS)
    collecteur.collect([objet])
    objets = []
    for instances in collecteur.data.values():
        objets.extend(instances)
    return objets


def _magasin(objet):
    if objet._meta.label_lower == "reseau.magasin":
        return objet.pk
    return getattr(objet, "magasin_id", None)


@transaction.atomic
def mettre_a_la_corbeille(objet, *, auteur):
    """Enregistre ``objet`` (et ce qui part avec lui) dans la corbeille, puis le supprime."""
    if not concerne(type(objet)):
        objet.delete()
        return None
    objets = _objets_lies(objet)
    element = ElementCorbeille.objects.create(
        app_label=objet._meta.app_label,
        modele=objet._meta.model_name,
        type_libelle=str(objet._meta.verbose_name).capitalize(),
        objet_pk=str(objet.pk),
        libelle=str(objet)[:255],
        magasin_id=_magasin(objet),
        nombre_objets=len(objets),
        donnees=json.loads(serializers.serialize("json", objets)),
        supprime_par=auteur if getattr(auteur, "pk", None) else None,
        expire_le=timezone.now() + datetime.timedelta(days=settings.CORBEILLE_JOURS),
    )
    objet.delete()
    return element


def restaurer(element):
    """Recrée l'élément et ce qui avait été supprimé avec lui ; le retire de la corbeille."""
    try:
        with transaction.atomic():
            for depot in serializers.deserialize("json", json.dumps(element.donnees)):
                modele = type(depot.object)
                if modele._base_manager.filter(pk=depot.object.pk).exists():
                    raise RestaurationImpossible(
                        f"{modele._meta.verbose_name.capitalize()} « {depot.object} » "
                        "existe déjà : rien n'a été restauré."
                    )
                # Les liens plusieurs-à-plusieurs sont dans les données (lignes de la table de
                # liaison, supprimées avec l'objet) : on ne les recrée pas une seconde fois.
                depot.save(save_m2m=False)
            element.delete()
            # Les clés étrangères sont vérifiées à la fin de la transaction : on force la
            # vérification ici pour rendre un message clair.
            with transaction.get_connection().cursor() as curseur:
                if transaction.get_connection().vendor == "postgresql":
                    curseur.execute("SET CONSTRAINTS ALL IMMEDIATE")
    except IntegrityError as erreur:
        raise RestaurationImpossible(
            "Impossible de restaurer : un élément lié a été supprimé définitivement ou un "
            f"doublon existe déjà ({str(erreur).splitlines()[0]})."
        ) from erreur


def vider_expires(maintenant=None):
    """Supprime définitivement les éléments dont le délai de grâce est passé."""
    expires = ElementCorbeille.objects.filter(expire_le__lte=maintenant or timezone.now())
    return expires.delete()[0]
