"""Modèles de données partagés par tout le pipeline."""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class TypeMurs(StrEnum):
    MURS_OCCUPES = "murs_occupes"
    MURS_LIBRES = "murs_libres"


def identifiant(source: str, id_source: str) -> str:
    """Identifiant stable d'une annonce : hash de (source, id_source)."""
    return hashlib.sha1(f"{source}:{id_source}".encode()).hexdigest()[:16]


@dataclass
class AnnonceBrute:
    """Annonce telle que remontée par une source, avant normalisation."""

    id_source: str
    source: str
    url: str
    titre: str
    ville: str
    code_postal: str
    type_murs: TypeMurs
    prix: float | None = None
    surface_m2: float | None = None
    loyer_mensuel: float | None = None
    honoraires: float | None = None
    image_url: str | None = None
    description: str = ""


@dataclass
class Annonce:
    """Annonce normalisée, puis enrichie et scorée par le pipeline."""

    id: str
    id_source: str
    source: str
    url: str
    titre: str
    ville: str
    code_postal: str
    departement: str
    type_murs: TypeMurs
    prix: float | None
    surface_m2: float | None
    loyer_mensuel: float | None
    honoraires: float | None
    image_url: str | None
    description: str
    date_premiere_vue: str
    date_derniere_vue: str
    urls_multiples: list[str] = field(default_factory=list)

    # Enrichissement
    prix_m2: float | None = None
    loyer_estime: bool = False
    loyer_mensuel_estime: float | None = None  # murs libres : loyer au benchmark local
    rendement_brut_pct: float | None = None
    rendement_acte_en_main_pct: float | None = None
    position_benchmark: str = "inconnu"
    decote_pct: float | None = None            # >0 : sous le prix médian du marché local
    marche_prix_m2_bas: float | None = None
    marche_prix_m2_haut: float | None = None
    temps_trajet_min: int | None = None
    caracteristiques: list[str] = field(default_factory=list)  # extraction, terrasse…
    lecture_prix: str = ""                     # phrase : pourquoi ce prix est haut/bas

    # Scoring
    score: int | None = None
    detail_score: dict[str, float] = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)

    # Exclusion
    exclue: bool = False
    raison_exclusion: str | None = None

    def texte_complet(self) -> str:
        return f"{self.titre} {self.description}"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["type_murs"] = self.type_murs.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Annonce":
        d = dict(d)
        d["type_murs"] = TypeMurs(d["type_murs"])
        return cls(**d)
