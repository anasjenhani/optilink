"""Périmètre magasin de la requête en cours.

Le périmètre est l'ensemble des magasins qu'un utilisateur a le droit de voir :
- ``None`` : aucun filtre (tout le réseau, ou code hors requête HTTP : tâches Celery, commandes) ;
- un ``frozenset`` d'identifiants : seuls ces magasins sont visibles (vide = aucun).

Il est posé par ``PerimetreMagasinMiddleware`` et appliqué par ``ParMagasinManager``.
"""

from contextlib import contextmanager
from contextvars import ContextVar

_perimetre: ContextVar[frozenset[int] | None] = ContextVar("perimetre_magasin", default=None)


def perimetre_actuel() -> frozenset[int] | None:
    return _perimetre.get()


def definir_perimetre(magasin_ids):
    valeur = None if magasin_ids is None else frozenset(magasin_ids)
    return _perimetre.set(valeur)


def reinitialiser_perimetre(jeton) -> None:
    _perimetre.reset(jeton)


@contextmanager
def perimetre(magasin_ids):
    jeton = definir_perimetre(magasin_ids)
    try:
        yield
    finally:
        reinitialiser_perimetre(jeton)
