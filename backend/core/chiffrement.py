"""Chiffrement applicatif des données de santé (prescriptions).

Les clés (Fernet : AES-128-CBC + HMAC-SHA256) viennent de ``PRESCRIPTIONS_CLES`` et ne sont
jamais stockées en base : une copie de la base ou d'une sauvegarde ne suffit pas à lire les
mesures. La première clé chiffre ; les suivantes servent seulement à relire les anciennes
données pendant une rotation de clé.
"""

import json
from functools import cache

from cryptography.fernet import Fernet, MultiFernet
from django.conf import settings


@cache
def _fernet(cles):
    return MultiFernet([Fernet(cle) for cle in cles])


def _courant():
    return _fernet(tuple(settings.PRESCRIPTIONS_CLES))


def chiffrer(donnees):
    texte = json.dumps(donnees, sort_keys=True, separators=(",", ":"))
    return _courant().encrypt(texte.encode()).decode()


def dechiffrer(jeton):
    return json.loads(_courant().decrypt(jeton.encode()))


def nouvelle_cle():
    return Fernet.generate_key().decode()
