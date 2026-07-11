"""Géographie : couronnes, temps de trajet approximatifs depuis le domicile
(rue Francoeur, Paris 18e — Lamarck-Caulaincourt L12 à 3 min à pied)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from pipeline.texte import cle_commune, normaliser_texte

PETITE_COURONNE = {"75", "92", "93", "94"}
GRANDE_COURONNE = {"77", "78", "91", "95"}
ILE_DE_FRANCE = PETITE_COURONNE | GRANDE_COURONNE

_MOTS_CENTRE_VILLE = (
    "centre-ville", "centre ville", "hypercentre", "plein centre",
    "coeur de ville", "cœur de ville",
)

_RE_CP_PARIS = re.compile(r"750([0-2]\d)\b")
_RE_ARRONDISSEMENT_SUFFIXE = re.compile(r"\b(\d{1,2})\s*(?:e|eme)\b")
_RE_ARRONDISSEMENT_APRES_PARIS = re.compile(r"\bparis\D{0,3}(\d{1,2})\b")


def arrondissement_paris(ville: str, code_postal: str = "") -> int | None:
    """Numéro d'arrondissement (1-20) déduit du code postal ou, à défaut, du
    texte de la ville — les sources écrivent « Paris 18e », « Paris 1er »,
    « Paris 5 », « Paris 5ème » ou parfois directement le code postal complet
    dans le champ ville. Renvoie None si aucun numéro fiable n'en ressort
    (ex. ville = « Paris » seul) : on retombe alors sur une valeur par défaut."""
    m = _RE_CP_PARIS.search(f"{ville} {code_postal}")
    if m:
        n = int(m.group(1))
        if 1 <= n <= 20:
            return n
    t = normaliser_texte(ville).replace("1er", "1e")
    for motif in (_RE_ARRONDISSEMENT_SUFFIXE, _RE_ARRONDISSEMENT_APRES_PARIS):
        m = motif.search(t)
        if m:
            n = int(m.group(1))
            if 1 <= n <= 20:
                return n
    return None


@dataclass(frozen=True)
class Trajets:
    """Table statique commune -> minutes, avec défaut par département.

    Paris est affiné par arrondissement (métro Château Rouge ligne 4 /
    Lamarck-Caulaincourt ligne 12, les deux stations de départ du 18e
    indiquées par l'utilisateur) plutôt qu'une seule valeur pour tout Paris —
    un local dans le 15e n'est pas à la même distance qu'un local dans le 9e.
    """

    communes: dict[str, int]
    departements_defaut: dict[str, int]
    arrondissements_paris: dict[str, int] = field(default_factory=dict)

    @classmethod
    def charger(cls, chemin: Path) -> "Trajets":
        donnees = json.loads(chemin.read_text(encoding="utf-8"))
        return cls(
            donnees["communes"],
            donnees["departements_defaut"],
            donnees.get("arrondissements_paris", {}),
        )

    def temps_depuis_paris18(
        self, ville: str, departement: str, code_postal: str = ""
    ) -> int | None:
        if departement == "75":
            arr = arrondissement_paris(ville, code_postal)
            if arr is not None and str(arr) in self.arrondissements_paris:
                return self.arrondissements_paris[str(arr)]
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
