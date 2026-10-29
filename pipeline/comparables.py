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
from urllib.parse import urlsplit, urlunsplit

from pipeline.modeles import Annonce, TypeMurs
from pipeline.transaction import qualifier_transaction

MIN_COMPARABLES = 2  # en dessous, pas assez solide pour remplacer le référentiel de zone


@dataclass(frozen=True)
class LoyersComparables:
    """Loyers/m²/an déclaratifs regroupés par code postal et surface."""

    par_code_postal: dict[str, list[float]]
    par_surface: dict[str, list[tuple[float, float]]] = field(default_factory=dict)
    observations: list[dict] = field(default_factory=list)

    @classmethod
    def depuis(cls, annonces: Iterable[Annonce], maintenant: datetime | None = None) -> "LoyersComparables":
        groupes: dict[str, list[float]] = defaultdict(list)
        surfaces: dict[str, list[tuple[float, float]]] = defaultdict(list)
        observations = []
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
                and qualifier_transaction(a)["nature"] == "murs"
                and a.loyer_mensuel
                and a.surface_m2
                and a.code_postal
                and a.loyer_mensuel > 0 and a.surface_m2 > 0
            ):
                taux = a.loyer_mensuel * 12 / a.surface_m2
                groupes[a.code_postal].append(taux)
                surfaces[a.code_postal].append((a.surface_m2, taux))
                observations.append({"id":a.id,"url":a.url,"code_postal":a.code_postal,
                                     "surface":a.surface_m2,"taux":taux,"vu_le":a.date_derniere_vue})
        return cls(dict(groupes), dict(surfaces), observations)

    def diagnostic(self, annonce: Annonce) -> dict:
        """Compare au stock récent sans compter le bien lui-même ou son URL."""
        def canonique(url):
            u = urlsplit(url)
            return urlunsplit((u.scheme,u.netloc,u.path.rstrip('/'),'', ''))
        exclues = {canonique(u) for u in [annonce.url,*annonce.urls_multiples]}
        deja, lot = set(), []
        for o in self.observations:
            url = canonique(o["url"])
            if o["id"] == annonce.id or url in exclues or url in deja or o["code_postal"] != annonce.code_postal:
                continue
            if not annonce.surface_m2 or not annonce.surface_m2/2 <= o["surface"] <= annonce.surface_m2*2:
                continue
            deja.add(url)
            lot.append(o)
        if len(lot) < MIN_COMPARABLES:
            return {"nombre":len(lot),"exploitable":False}
        taux = [o["taux"] for o in lot]
        mediane = statistics.median(taux)
        reel = annonce.loyer_mensuel and not annonce.loyer_estime and annonce.loyer_origine != "rendement"
        ecart = (annonce.loyer_mensuel*12/annonce.surface_m2/mediane-1)*100 if reel else None
        return {"nombre":len(lot),"exploitable":True,"mediane_m2_an":round(mediane,1),
                "bas_m2_an":round(min(taux),1),"haut_m2_an":round(max(taux),1),
                "ecart_pct":round(ecart,1) if ecart is not None else None,
                "references":lot[:5]}

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
