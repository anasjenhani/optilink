"""Pays du monde avec leur monnaie, pour pré-remplir la fiche d'un pays dans l'administration.

pays_du_monde.json : codes ISO 3166-1 (numérique et alpha-2), noms français (CLDR), monnaie
en vigueur et ses décimales (ISO 4217), indicatif téléphonique (libphonenumber) et fuseau
horaire principal (IANA). Les taux de TVA et le droit de timbre restent à saisir : ils ne
figurent dans aucune norme.
"""

import json
from functools import cache
from pathlib import Path

FICHIER = Path(__file__).with_name("pays_du_monde.json")

# Champs du modèle Pays que la liste remplit.
CHAMPS = (
    "code_numerique",
    "code",
    "nom",
    "devise",
    "decimales",
    "indicatif_telephonique",
    "fuseau_horaire",
)


@cache
def pays_du_monde():
    """Pays par code ISO numérique (« 788 » pour la Tunisie), triés par nom."""
    return {p["code_numerique"]: p for p in json.loads(FICHIER.read_text(encoding="utf-8"))}
