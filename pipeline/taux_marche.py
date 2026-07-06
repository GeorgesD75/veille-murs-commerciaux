"""Taux de crédit de référence, actualisé à CHAQUE tournée — jamais figé.

Source : le rendement des obligations d'État françaises à long terme
(« OAT »), série officielle Eurostat utilisée pour le critère de convergence
de Maastricht — API publique, gratuite, sans clé, mise à jour mensuellement.
C'est la référence sur laquelle les banques indexent leurs marges de crédit :
on y ajoute une marge professionnelle typique (configurable) pour approcher
un taux de crédit murs commerciaux réaliste.

Ce n'est PAS une offre bancaire réelle — juste une estimation de marché,
transparente sur sa source et sa date, bien plus honnête qu'un chiffre figé
dans un fichier de configuration qu'on oublie de mettre à jour. Une panne
(service indisponible, format changé) ne bloque jamais le run : le taux
statique de config.yaml reprend la main, silencieusement.
"""
from __future__ import annotations

import logging

import requests

from sources.http import USER_AGENT

log = logging.getLogger("collecteur.taux")

URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/irt_lt_mcby_m"


def taux_obligataire_france() -> tuple[float, str] | None:
    """(taux OAT France en %, mois "AAAA-MM" de la dernière valeur publiée)."""
    try:
        reponse = requests.get(
            URL, params={"geo": "FR", "format": "JSON", "lastTimePeriod": 1},
            headers={"User-Agent": USER_AGENT}, timeout=15,
        )
        reponse.raise_for_status()
        donnees = reponse.json()
        valeur = next(iter(donnees["value"].values()))
        mois = next(iter(donnees["dimension"]["time"]["category"]["index"]))
        return round(float(valeur), 2), str(mois)
    except Exception as exc:  # noqa: BLE001 — jamais bloquant : le taux de config reste valable
        log.info("taux de marché indisponible (%s) — on garde le taux de config.yaml", exc)
        return None


def taux_credit_estime(marge_pct: float) -> dict | None:
    """Taux de crédit pro estimé (OAT + marge) et sa provenance, ou None."""
    resultat = taux_obligataire_france()
    if resultat is None:
        return None
    oat, mois = resultat
    return {
        "taux_pct": round(oat + marge_pct, 2),
        "oat_pct": oat,
        "marge_pct": marge_pct,
        "mois_reference": mois,
    }
