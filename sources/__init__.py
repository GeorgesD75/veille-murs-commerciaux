"""Registre des sources. Ajouter une source = 1 fichier + 1 ligne ici + 1 ligne en config.

century21.fr n'est volontairement pas implémenté en Niveau 1 : robots.txt très
restrictif sur les listings et rubrique commerces non identifiable sans risque
de blocage. Les grands portails (dont Century 21 via SeLoger Bureaux & Commerces)
seront couverts par les alertes email en Phase 4 (module IMAP).
"""
from __future__ import annotations

from functools import partial
from typing import Callable

from pipeline.config import Config
from sources.base import Source
from sources.hektor import SourceFlagship, SourceIburoshop
from sources.mock import SourceMock
from sources.murscommerciaux import SourceMursCommerciaux
from sources.pointdevente import SourcePointDeVente

FABRIQUES: dict[str, Callable[..., Source]] = {
    "mock": SourceMock,
    "pointdevente": SourcePointDeVente,
    "murscommerciaux": SourceMursCommerciaux,
    "iburoshop": SourceIburoshop,
    "flagship": SourceFlagship,
    # Phase 4 : "imap"
}


def sources_actives(config: Config) -> list[tuple[str, Callable[[], Source]]]:
    """Fabriques des sources actives ; les paramètres de config (hors `actif`)
    sont passés au constructeur de la source (ex. max_pages)."""
    actives: list[tuple[str, Callable[[], Source]]] = []
    for nom, params in config.sources.items():
        params = dict(params or {})
        if not params.pop("actif", False) or nom not in FABRIQUES:
            continue
        actives.append((nom, partial(FABRIQUES[nom], **params)))
    return actives
