"""Client HTTP poli, partagé par toutes les sources Niveau 1 (scraping léger).

Règles appliquées systématiquement :
- User-Agent honnête identifiant le projet et un contact ;
- 3 à 5 secondes entre deux requêtes, aucune parallélisation ;
- vérification de robots.txt (en plus de la validation manuelle documentée
  dans chaque parser — le parseur robots de la stdlib ne gère pas les jokers) ;
- arrêt propre sur HTTP 403/429 : le site refuse, on n'insiste pas.
"""
from __future__ import annotations

import logging
import random
import time
import urllib.robotparser
from urllib.parse import urlparse

import requests

log = logging.getLogger("collecteur.http")

USER_AGENT = (
    "VeilleMursCommerciaux/0.1 "
    "(veille personnelle d'annonces, 1 requete/3-5s, 1 run/jour; "
    "contact: georgesdurand75@gmail.com)"
)


class SourceBloqueeErreur(RuntimeError):
    """HTTP 403/429 ou interdiction robots.txt : arrêt propre de la source."""


class ClientPoli:
    def __init__(self, delai_min_s: float = 3.0, delai_max_s: float = 5.0) -> None:
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.delai_min_s = delai_min_s
        self.delai_max_s = delai_max_s
        self._derniere_requete = 0.0
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def _attendre_son_tour(self) -> None:
        ecoule = time.monotonic() - self._derniere_requete
        attente = random.uniform(self.delai_min_s, self.delai_max_s) - ecoule
        if attente > 0:
            time.sleep(attente)

    def _robots_pour(self, url: str) -> urllib.robotparser.RobotFileParser | None:
        decoupe = urlparse(url)
        hote = f"{decoupe.scheme}://{decoupe.netloc}"
        if hote not in self._robots:
            parseur = urllib.robotparser.RobotFileParser(f"{hote}/robots.txt")
            try:
                parseur.read()
            except Exception as exc:  # noqa: BLE001 — robots inaccessible : on continue,
                # les chemins de chaque source ont été validés manuellement.
                log.warning("robots.txt illisible pour %s (%s)", hote, exc)
                parseur = None
            self._robots[hote] = parseur
        return self._robots[hote]

    def obtenir(self, url: str) -> str:
        """GET poli. Lève SourceBloqueeErreur sur refus (robots, 403, 429)."""
        parseur = self._robots_pour(url)
        if parseur is not None and not parseur.can_fetch(USER_AGENT, url):
            raise SourceBloqueeErreur(f"robots.txt interdit {url}")
        self._attendre_son_tour()
        try:
            reponse = self.session.get(url, timeout=30)
        finally:
            self._derniere_requete = time.monotonic()
        if reponse.status_code in (403, 429):
            raise SourceBloqueeErreur(f"HTTP {reponse.status_code} sur {url} — arrêt propre")
        reponse.raise_for_status()
        return reponse.text
