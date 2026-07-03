"""Enrichissement : prix/m², rendements, position vs benchmark local."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pipeline.geo import GRANDE_COURONNE
from pipeline.modeles import Annonce, TypeMurs
from pipeline.texte import normaliser_texte

# Frais d'acquisition (notaire, enregistrement…) retenus pour le rendement « acte en main ».
TAUX_FRAIS_ACQUISITION = 1.08

# Ce qu'on peut FAIRE dans le local : plus l'éventail d'activités possibles est
# large, plus le bien se reloue facilement (moins de vacance). Détection par
# mots-clés dans le titre/la description, affichée en étiquettes sur le dashboard.
_CARACTERISTIQUES: list[tuple[str, tuple[str, ...]]] = [
    ("Extraction / vraie restauration possible",
     ("extraction", "conduit de cheminee", "conduit existant", "cheminee existant")),
    ("Restauration légère possible (sans conduit)",
     ("sans conduit", "restauration sans extraction")),
    ("Toutes activités", ("toutes activites", "tout commerce", "tous commerces")),
    ("Activités restreintes", ("sauf restauration", "sauf bouche", "hors nuisances",
                               "sans nuisance", "activites limitees")),
    ("Terrasse", ("terrasse",)),
    ("Emplacement d'angle", ("d'angle", "d angle", "angle de rue", "en angle")),
]


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


def caracteristiques_depuis_texte(texte: str) -> list[str]:
    """Étiquettes d'usage du local (extraction, terrasse…) détectées dans le texte."""
    t = normaliser_texte(texte)
    return [libelle for libelle, mots in _CARACTERISTIQUES if any(m in t for m in mots)]


def lecture_prix(annonce: Annonce) -> str:
    """Phrase honnête : pourquoi ce prix est là où il est, d'après l'annonce.

    On ne s'appuie que sur des éléments constatables (mots de l'annonce,
    surface, secteur, bail) — jamais d'invention. Une décote inexpliquée est
    dite telle quelle : bonne affaire possible… ou défaut caché.
    """
    if annonce.prix_m2 is None or annonce.decote_pct is None:
        return ""
    d = annonce.decote_pct
    texte = normaliser_texte(annonce.texte_complet())
    caracts = " ".join(annonce.caracteristiques).lower()

    if d >= 10:  # nettement sous la médiane
        raisons = []
        if any(m in texte for m in ("travaux", "a renover", "a rafraichir", "rafraichissement")):
            raisons.append("des travaux sont signalés dans l'annonce")
        if annonce.surface_m2 and annonce.surface_m2 >= 120:
            raisons.append("les grandes surfaces se négocient mécaniquement moins cher au m²")
        if annonce.departement in GRANDE_COURONNE:
            raisons.append("secteur de grande couronne, moins tendu")
        if (
            annonce.type_murs is TypeMurs.MURS_OCCUPES
            and annonce.rendement_brut_pct is not None
            and annonce.rendement_brut_pct < 5
        ):
            raisons.append("le loyer en place est faible et tire le prix vers le bas")
        if raisons:
            return f"Décote lisible : {' ; '.join(raisons)}."
        return (
            "Décote sans explication visible dans l'annonce : possible bonne affaire "
            "— ou défaut caché (état, copropriété, bail) à vérifier sur place."
        )

    if d <= -10:  # nettement au-dessus de la médiane
        raisons = []
        if annonce.surface_m2 and annonce.surface_m2 <= 25:
            raisons.append("les petites surfaces se paient plus cher au m²")
        if annonce.departement == "75":
            raisons.append("emplacement parisien recherché")
        if "extraction" in caracts or "restauration" in caracts:
            raisons.append("la possibilité de restauration est un atout rare")
        if "terrasse" in caracts or "angle" in caracts:
            raisons.append("atouts d'emplacement (terrasse, angle)")
        if (
            annonce.type_murs is TypeMurs.MURS_OCCUPES
            and annonce.rendement_brut_pct is not None
            and annonce.rendement_brut_pct >= 7
        ):
            raisons.append("le bail en place à bon rendement justifie une prime")
        if raisons:
            return f"Prime explicable : {' ; '.join(raisons)}."
        return "Prime non justifiée par les éléments de l'annonce : marge de négociation probable."

    return "Prix cohérent avec le marché local."


def loyer_mensuel_retenu(annonce: Annonce, benchmarks: Benchmarks) -> tuple[float | None, bool]:
    """Loyer retenu pour le rendement, et s'il est hypothétique.

    Murs occupés : loyer réel du bail. Murs libres : tout loyer est hypothétique
    — qu'il soit annoncé par le vendeur (« loyer potentiel ») ou estimé au
    benchmark — donc marqué estimé (pénalité d'incertitude au scoring).
    """
    if annonce.type_murs is TypeMurs.MURS_OCCUPES:
        return annonce.loyer_mensuel, False
    if annonce.loyer_mensuel:
        return annonce.loyer_mensuel, True
    if annonce.surface_m2:
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
    annonce.caracteristiques = caracteristiques_depuis_texte(annonce.texte_complet())

    # Comparaison au marché local, pour l'affichage (« ~12 % sous le marché »).
    bench = benchmarks.pour(annonce.code_postal, annonce.departement)
    if bench is not None:
        annonce.marche_prix_m2_bas = bench.prix_m2_bas
        annonce.marche_prix_m2_haut = bench.prix_m2_haut
        if annonce.prix_m2 is not None:
            annonce.decote_pct = round(
                (bench.prix_m2_median - annonce.prix_m2) / bench.prix_m2_median * 100, 1
            )
    annonce.lecture_prix = lecture_prix(annonce)
    return annonce
