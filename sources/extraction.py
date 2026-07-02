"""Petits extracteurs partagés par les parsers (nombres, loyers, rendements)."""
from __future__ import annotations

import re

_NOMBRE = re.compile(r"\d[\d\s  .,]*")
_LOYER_ANNUEL = re.compile(
    r"loyer\s+annuel[^0-9€]{0,25}(\d[\d\s  .,]*)", re.IGNORECASE
)
_RENTABILITE = re.compile(r"rentabilit\w*[^0-9%]{0,30}(\d+(?:[.,]\d+)?)\s*%", re.IGNORECASE)
_SURFACE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:m²|m2)", re.IGNORECASE)


def extraire_nombre(texte: str | None) -> float | None:
    """Premier nombre d'un texte : « 360 000 € Net vendeur » -> 360000.0."""
    if not texte:
        return None
    trouve = _NOMBRE.search(texte)
    if not trouve:
        return None
    brut = re.sub(r"[\s  ]", "", trouve.group(0)).replace(",", ".")
    if brut.count(".") > 1:  # points utilisés comme séparateurs de milliers
        entier, _, decimales = brut.rpartition(".")
        brut = entier.replace(".", "") + "." + decimales
    brut = brut.rstrip(".")
    try:
        return float(brut)
    except ValueError:
        return None


def extraire_surface(texte: str | None) -> float | None:
    """Première surface « NN m² » d'un texte."""
    if not texte:
        return None
    trouve = _SURFACE.search(texte)
    return float(trouve.group(1).replace(",", ".")) if trouve else None


def loyer_mensuel_depuis_texte(texte: str | None, prix: float | None) -> float | None:
    """« Loyer annuel : 43 470 € HT HC » -> 3622.5 €/mois (si plausible vs prix)."""
    trouve = _LOYER_ANNUEL.search(texte or "")
    if not trouve:
        return None
    annuel = extraire_nombre(trouve.group(1))
    if annuel and (prix is None or annuel < prix):
        return round(annuel / 12, 2)
    return None


def rentabilite_depuis_texte(texte: str | None) -> float | None:
    """« rentabilité (avant révision) 7% » -> 7.0 (bornée à une plage plausible)."""
    trouve = _RENTABILITE.search(texte or "")
    if not trouve:
        return None
    pct = float(trouve.group(1).replace(",", "."))
    return pct if 2.0 <= pct <= 15.0 else None
