"""Petits extracteurs partagés par les parsers (nombres, surfaces, loyers, type de murs)."""
from __future__ import annotations

import re

from pipeline.modeles import TypeMurs
from pipeline.texte import normaliser_texte

_NOMBRE = re.compile(r"\d[\d\s  .,]*")
_LOYER_ANNUEL = re.compile(
    r"loyer\s+annuel[^0-9€]{0,25}(\d[\d\s  .,]*)", re.IGNORECASE
)
# « Vendu loué : 2 087 € », « loyer : 1 500 €/mois », « loyer mensuel 900 € »…
_LOYER_GENERIQUE = re.compile(
    r"(?:vendus?\s+lou[ée]s?|lou[ée]s?\s*:|loyer(?:\s+mensuel)?)\s*:?"
    r"[^0-9€%]{0,15}(\d[\d\s  .,]*)\s*€\s*(/\s*an\b|annuel)?",
    re.IGNORECASE,
)
_RENTABILITE = re.compile(r"rentabilit\w*[^0-9%]{0,30}(\d+(?:[.,]\d+)?)\s*%", re.IGNORECASE)
# « 43 m² », « 147m2 », « 20.00 m 2 » (exposant recollé avec un espace)
_SURFACE = re.compile(r"(\d+(?:[.,]\d+)?)\s*m\s*(?:²|2)(?![\da-z])", re.IGNORECASE)

RENDEMENT_MAX_PLAUSIBLE = 0.20  # au-delà de 20 %/an, la donnée est suspecte

_MOTS_OCCUPES = (
    "vendu occupe", "vendus occupes", "vendue occupee", "murs occupes", "vendu loue",
    "vendus loues", "vendue louee", "locataire en place", "occupe par", "occupes par",
)
_MOTS_LIBRES = (
    "vendu libre", "vendus libres", "vendue libre", "murs libres",
    "libre de toute occupation", "local vide", "local libre",
)


def extraire_nombre(texte: str | None) -> float | None:
    """Premier nombre d'un texte, aux formats français.

    « 360 000 € » -> 360000 ; « 515.000 € » -> 515000 (milliers à point, PAP) ;
    « 2 333,83 » -> 2333.83 ; « 8.7% » -> 8.7 ; « 1.250.000 » -> 1250000.
    """
    if not texte:
        return None
    trouve = _NOMBRE.search(texte)
    if not trouve:
        return None
    brut = re.sub(r"[\s  ]", "", trouve.group(0))
    if "," in brut:  # la virgule est la décimale, les points sont des milliers
        brut = brut.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", brut):  # 515.000, 1.250.000
        brut = brut.replace(".", "")
    elif brut.count(".") > 1:
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
    """Loyer mensuel déduit d'un texte d'annonce, avec garde-fous.

    Priorité au « loyer annuel : … » explicite ; sinon formes génériques
    (« vendu loué : 2 087 € », « loyer : 1 500 €/mois »). Un loyer qui
    impliquerait plus de 20 % de rendement annuel est réinterprété comme
    annuel, puis écarté s'il reste aberrant.
    """
    texte = texte or ""
    trouve = _LOYER_ANNUEL.search(texte)
    if trouve:
        annuel = extraire_nombre(trouve.group(1))
        if annuel and (prix is None or annuel < prix):
            return round(annuel / 12, 2)
        return None

    trouve = _LOYER_GENERIQUE.search(texte)
    if not trouve:
        return None
    valeur = extraire_nombre(trouve.group(1))
    if not valeur:
        return None
    if trouve.group(2):  # « /an », « annuel »
        valeur /= 12
    if prix:
        if valeur * 12 / prix > RENDEMENT_MAX_PLAUSIBLE:
            valeur /= 12
        if valeur * 12 / prix > RENDEMENT_MAX_PLAUSIBLE:
            return None
    return round(valeur, 2)


def rentabilite_depuis_texte(texte: str | None) -> float | None:
    """« rentabilité (avant révision) 7% » -> 7.0 (bornée à une plage plausible)."""
    trouve = _RENTABILITE.search(texte or "")
    if not trouve:
        return None
    pct = float(trouve.group(1).replace(",", "."))
    return pct if 2.0 <= pct <= 15.0 else None


def deviner_type_murs(texte: str) -> TypeMurs:
    """Murs occupés ou libres, d'après le texte de l'annonce.

    L'ordre compte : « libre de toute occupation » contient « occupation »,
    donc les mots-clés occupés sont des formes précises (« occupé par »…).
    """
    t = normaliser_texte(texte)
    if any(mot in t for mot in _MOTS_OCCUPES):
        return TypeMurs.MURS_OCCUPES
    if any(mot in t for mot in _MOTS_LIBRES):
        return TypeMurs.MURS_LIBRES
    if "bail" in t:  # un bail décrit sans autre précision = probablement loué
        return TypeMurs.MURS_OCCUPES
    return TypeMurs.MURS_LIBRES
