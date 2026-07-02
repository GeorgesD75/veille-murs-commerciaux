"""Registre des sources. Ajouter une source = 1 fichier + 1 ligne ici + 1 ligne en config."""
from __future__ import annotations

from typing import Callable

from pipeline.config import Config
from sources.base import Source
from sources.mock import SourceMock

FABRIQUES: dict[str, Callable[[], Source]] = {
    "mock": SourceMock,
    # Phase 2 : "pointdevente", "murscommerciaux", "iburoshop", "flagship", "century21"
    # Phase 4 : "imap"
}


def sources_actives(config: Config) -> list[Source]:
    actives: list[Source] = []
    for nom, params in config.sources.items():
        if (params or {}).get("actif") and nom in FABRIQUES:
            actives.append(FABRIQUES[nom]())
    return actives
