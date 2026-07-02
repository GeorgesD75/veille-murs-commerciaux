"""Petits utilitaires de normalisation de texte."""
from __future__ import annotations

import unicodedata


def normaliser_texte(texte: str) -> str:
    """Minuscules, sans accents, espaces normalisés — pour comparer des mots-clés."""
    t = unicodedata.normalize("NFKD", texte.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(t.split())


def cle_commune(ville: str) -> str:
    """Clé de recherche d'une commune : 'Saint-Ouen-sur-Seine' -> 'saint ouen sur seine'.

    Les arrondissements parisiens ('Paris 18e', 'Paris 75018') sont ramenés à 'paris'.
    """
    t = normaliser_texte(ville).replace("-", " ")
    t = " ".join(t.split())
    if t.startswith("paris"):
        return "paris"
    return t
