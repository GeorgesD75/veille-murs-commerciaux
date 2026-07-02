"""Chargement de la configuration (config.yaml)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

RACINE = Path(__file__).resolve().parent.parent


class Config:
    """Accès au contenu de config.yaml, avec quelques raccourcis typés."""

    def __init__(self, donnees: dict[str, Any]) -> None:
        self.donnees = donnees

    @classmethod
    def charger(cls, chemin: Path | None = None) -> "Config":
        chemin = chemin or RACINE / "config.yaml"
        with open(chemin, encoding="utf-8") as f:
            return cls(yaml.safe_load(f))

    def __getitem__(self, cle: str) -> Any:
        return self.donnees[cle]

    @property
    def budget(self) -> dict[str, Any]:
        return self.donnees["budget"]

    @property
    def zone(self) -> dict[str, Any]:
        return self.donnees["zone"]

    @property
    def filtres(self) -> dict[str, Any]:
        return self.donnees["filtres"]

    @property
    def deduplication(self) -> dict[str, Any]:
        return self.donnees["deduplication"]

    @property
    def scoring(self) -> dict[str, Any]:
        return self.donnees["scoring"]

    @property
    def sources(self) -> dict[str, Any]:
        return self.donnees["sources"]
