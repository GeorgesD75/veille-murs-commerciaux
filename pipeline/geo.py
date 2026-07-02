"""Géographie : couronnes, temps de trajet approximatifs depuis Paris 18e."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pipeline.texte import cle_commune, normaliser_texte

PETITE_COURONNE = {"75", "92", "93", "94"}
GRANDE_COURONNE = {"77", "78", "91", "95"}
ILE_DE_FRANCE = PETITE_COURONNE | GRANDE_COURONNE

_MOTS_CENTRE_VILLE = (
    "centre-ville", "centre ville", "hypercentre", "plein centre",
    "coeur de ville", "cœur de ville",
)


@dataclass(frozen=True)
class Trajets:
    """Table statique commune -> minutes, avec défaut par département."""

    communes: dict[str, int]
    departements_defaut: dict[str, int]

    @classmethod
    def charger(cls, chemin: Path) -> "Trajets":
        donnees = json.loads(chemin.read_text(encoding="utf-8"))
        return cls(donnees["communes"], donnees["departements_defaut"])

    def temps_depuis_paris18(self, ville: str, departement: str) -> int | None:
        cle = cle_commune(ville)
        if cle in self.communes:
            return self.communes[cle]
        return self.departements_defaut.get(departement)


def categorie_emplacement(
    ville: str, departement: str, texte: str, communes_dynamiques: list[str]
) -> str:
    """Catégorie servant au scoring emplacement (clés de config.yaml)."""
    if departement == "75":
        return "paris"
    if departement in PETITE_COURONNE:
        dynamiques = {cle_commune(c) for c in communes_dynamiques}
        if cle_commune(ville) in dynamiques:
            return "petite_couronne_dynamique"
        return "petite_couronne"
    if departement in GRANDE_COURONNE:
        t = normaliser_texte(texte)
        if any(mot in t for mot in _MOTS_CENTRE_VILLE):
            return "grande_couronne_centre_ville"
    return "autre"
