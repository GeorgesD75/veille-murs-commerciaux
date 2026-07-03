"""Enrichissement : prix/m², rendements, position vs benchmark local."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pipeline.modeles import Annonce, TypeMurs

# Frais d'acquisition (notaire, enregistrement…) retenus pour le rendement « acte en main ».
TAUX_FRAIS_ACQUISITION = 1.08


@dataclass(frozen=True)
class Benchmark:
    prix_m2_bas: float
    prix_m2_haut: float
    loyer_m2_annuel: float

    @property
    def prix_m2_median(self) -> float:
        return (self.prix_m2_bas + self.prix_m2_haut) / 2


class Benchmarks:
    """Référentiel statique de prix/m² et loyers (data/benchmarks.json)."""

    def __init__(
        self, departements: dict[str, Benchmark], communes: dict[str, Benchmark]
    ) -> None:
        self.departements = departements
        self.communes = communes

    @classmethod
    def charger(cls, chemin: Path) -> "Benchmarks":
        donnees = json.loads(chemin.read_text(encoding="utf-8"))

        def convertir(bloc: dict) -> dict[str, Benchmark]:
            return {
                cle: Benchmark(v["prix_m2"][0], v["prix_m2"][1], v["loyer_m2_annuel"])
                for cle, v in bloc.items()
            }

        return cls(convertir(donnees["departements"]), convertir(donnees.get("communes", {})))

    def pour(self, code_postal: str, departement: str) -> Benchmark | None:
        """Benchmark le plus précis disponible : code postal, sinon département."""
        return self.communes.get(code_postal) or self.departements.get(departement)


def loyer_mensuel_retenu(annonce: Annonce, benchmarks: Benchmarks) -> tuple[float | None, bool]:
    """Loyer réel si connu ; pour des murs libres, loyer estimé au benchmark (flag estimé)."""
    if annonce.loyer_mensuel:
        return annonce.loyer_mensuel, False
    if annonce.type_murs is TypeMurs.MURS_LIBRES and annonce.surface_m2:
        bench = benchmarks.pour(annonce.code_postal, annonce.departement)
        if bench:
            return annonce.surface_m2 * bench.loyer_m2_annuel / 12, True
    return None, False


def position_vs_benchmark(annonce: Annonce, benchmarks: Benchmarks, seuil_decote_pct: float) -> str:
    bench = benchmarks.pour(annonce.code_postal, annonce.departement)
    if bench is None or annonce.prix_m2 is None:
        return "inconnu"
    decote_pct = (bench.prix_m2_median - annonce.prix_m2) / bench.prix_m2_median * 100
    if decote_pct >= seuil_decote_pct:
        return "decote_forte"
    if annonce.prix_m2 <= bench.prix_m2_haut:
        return "dans_fourchette"
    return "surcote"


def enrichir(annonce: Annonce, benchmarks: Benchmarks, seuil_decote_pct: float) -> Annonce:
    if annonce.prix and annonce.surface_m2:
        annonce.prix_m2 = round(annonce.prix / annonce.surface_m2)

    loyer, estime = loyer_mensuel_retenu(annonce, benchmarks)
    annonce.loyer_estime = estime
    annonce.loyer_mensuel_estime = round(loyer, 2) if (estime and loyer) else None
    if loyer and annonce.prix:
        loyer_annuel = loyer * 12
        annonce.rendement_brut_pct = round(loyer_annuel / annonce.prix * 100, 2)
        cout_acte_en_main = annonce.prix * TAUX_FRAIS_ACQUISITION + (annonce.honoraires or 0)
        annonce.rendement_acte_en_main_pct = round(loyer_annuel / cout_acte_en_main * 100, 2)

    annonce.position_benchmark = position_vs_benchmark(annonce, benchmarks, seuil_decote_pct)

    # Comparaison au marché local, pour l'affichage (« ~12 % sous le marché »).
    bench = benchmarks.pour(annonce.code_postal, annonce.departement)
    if bench is not None:
        annonce.marche_prix_m2_bas = bench.prix_m2_bas
        annonce.marche_prix_m2_haut = bench.prix_m2_haut
        if annonce.prix_m2 is not None:
            annonce.decote_pct = round(
                (bench.prix_m2_median - annonce.prix_m2) / bench.prix_m2_median * 100, 1
            )
    return annonce
