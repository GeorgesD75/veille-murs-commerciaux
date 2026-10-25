"""Estimation par loyers annoncés de locaux occupés de surface voisine.

Même code postal, au moins deux annonces, médiane ; annonces revues dans les
30 jours si la date de référence est fournie. Aucun bail n'est consulté :
ces loyers déclaratifs ne prouvent pas le revenu d'un autre bien.
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from pipeline.modeles import Annonce, TypeMurs

MIN_COMPARABLES = 2  # en dessous, pas assez solide pour remplacer le référentiel de zone


@dataclass(frozen=True)
class LoyersComparables:
    """Loyers/m²/an déclaratifs regroupés par code postal et surface."""

    par_code_postal: dict[str, list[float]]
    par_surface: dict[str, list[tuple[float, float]]] = field(default_factory=dict)

    @classmethod
    def depuis(cls, annonces: Iterable[Annonce], maintenant: datetime | None = None) -> "LoyersComparables":
        groupes: dict[str, list[float]] = defaultdict(list)
        surfaces: dict[str, list[tuple[float, float]]] = defaultdict(list)
        for a in annonces:
            if maintenant is not None and datetime.fromisoformat(a.date_derniere_vue) < maintenant - timedelta(days=30):
                continue
            if (
                a.type_murs is TypeMurs.MURS_OCCUPES
                and not a.loyer_estime
                and a.loyer_origine != "rendement"
                and not a.conflits_donnees
                and a.etat_detail not in {"retiree", "redirection_liste"}
                and not a.exclue
                and a.loyer_mensuel
                and a.surface_m2
                and a.code_postal
                and a.loyer_mensuel > 0 and a.surface_m2 > 0
            ):
                taux = a.loyer_mensuel * 12 / a.surface_m2
                groupes[a.code_postal].append(taux)
                surfaces[a.code_postal].append((a.surface_m2, taux))
        return cls(dict(groupes), dict(surfaces))

    def pour(self, code_postal: str, surface_m2: float | None = None) -> tuple[float, int] | None:
        """(médiane €/m²/an, nombre d'annonces) si au moins deux, sinon None."""
        valeurs = self.par_code_postal.get(code_postal, [])
        if surface_m2 and self.par_surface:
            # Un local de 25 m² ne se valorise pas au loyer/m² d'un entrepôt de 500 m².
            valeurs = [taux for surface, taux in self.par_surface.get(code_postal, [])
                       if surface_m2 / 2 <= surface <= surface_m2 * 2]
        if len(valeurs) < MIN_COMPARABLES:
            return None
        return round(statistics.median(valeurs), 1), len(valeurs)
