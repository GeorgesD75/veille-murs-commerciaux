"""Loyer estimé à partir de baux RÉELS voisins, pas d'une moyenne de zone.

Pour un local vide (murs libres, aucun loyer connu), le pipeline proposait
jusqu'ici un loyer estimé au référentiel statique de zone (data/benchmarks.json
— une moyenne département/commune, parfois large). C'est une estimation
FAIBLE : elle ne dit rien de la rue précise.

Ce module cherche mieux : les loyers RÉELS (murs occupés, bail en cours) des
autres annonces du même code postal, collectées par ce même outil. Quand il y
en a assez pour être solide (au moins deux, une médiane pour ignorer un
éventuel cas hors norme), l'estimation devient « basée sur N baux voisins
réels » — nettement plus fiable qu'une moyenne de zone, et présentée comme
telle (pénalité d'incertitude réduite au scoring, texte dédié au dashboard).
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from pipeline.modeles import Annonce, TypeMurs

MIN_COMPARABLES = 2  # en dessous, pas assez solide pour remplacer le référentiel de zone


@dataclass(frozen=True)
class LoyersComparables:
    """Loyers/m²/an réels (baux prouvés), regroupés par code postal."""

    par_code_postal: dict[str, list[float]]

    @classmethod
    def depuis(cls, annonces: Iterable[Annonce]) -> "LoyersComparables":
        groupes: dict[str, list[float]] = defaultdict(list)
        for a in annonces:
            if (
                a.type_murs is TypeMurs.MURS_OCCUPES
                and a.loyer_mensuel
                and a.surface_m2
                and a.code_postal
            ):
                groupes[a.code_postal].append(a.loyer_mensuel * 12 / a.surface_m2)
        return cls({cp: valeurs for cp, valeurs in groupes.items()})

    def pour(self, code_postal: str) -> tuple[float, int] | None:
        """(médiane €/m²/an, nombre de baux) si assez solide, sinon None."""
        valeurs = self.par_code_postal.get(code_postal, [])
        if len(valeurs) < MIN_COMPARABLES:
            return None
        return round(statistics.median(valeurs), 1), len(valeurs)
