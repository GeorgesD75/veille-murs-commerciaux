"""Client HTTP poli, partagé par toutes les sources Niveau 1 (scraping léger).

Règles appliquées systématiquement :
- User-Agent honnête identifiant le projet et un contact ;
- 3 à 5 secondes entre deux requêtes, aucune parallélisation ;
- vérification de robots.txt (en plus de la validation manuelle documentée
  dans chaque parser — le parseur robots de la stdlib ne gère pas les jokers) ;
- arrêt propre sur HTTP 403/429 : le site refuse, on n'insiste pas ;
- IPv4 forcé (voir plus bas) : les runners GitHub Actions ont un IPv6 cassé
  ou absent, et une source dont le DNS répond aussi en IPv6 (ex. pointdevente.fr)
  échoue alors en « Network is unreachable » — constaté le 2026-08-17, alors
  que le site répondait normalement en IPv4 depuis un autre réseau.
"""
from __future__ import annotations

import logging
import random
import re
import socket
import time
import urllib.robotparser
from urllib.parse import urlparse, unquote

import requests
import urllib3.util.connection as _urllib3_connexion

log = logging.getLogger("collecteur.http")

# Force IPv4 : sans ça, un hôte publiant AUSSI une adresse IPv6 (courant, sans
# rapport avec un site cassé) est tenté en premier par urllib3 — et échoue net
# sur un runner sans connectivité IPv6 sortante, avant même d'essayer l'IPv4
# qui, lui, aurait fonctionné. Patch global : ce projet n'a aucun besoin d'IPv6.
_urllib3_connexion.allowed_gai_family = lambda: socket.AF_INET

USER_AGENT = (
    "VeilleMursCommerciaux/0.1 "
    "(veille personnelle d'annonces, 1 requete/3-5s, 3 runs/jour; "
    "contact: georgesdurand75@gmail.com)"
)


class SourceBloqueeErreur(RuntimeError):
    """HTTP 403/429 ou interdiction robots.txt : arrêt propre de la source."""


class SourceTemporaireErreur(RuntimeError):
    """Serveur/robots indisponible : réessayer à la prochaine tournée."""


def robots_autorise(parseur, agent: str, url: str) -> bool:
    """Règle la plus spécifique, jokers et ancre finale (RFC 9309).

    La stdlib applique le premier préfixe : « Allow: / » masquait ainsi des
    interdictions plus précises. Elle ne reconnaît pas non plus * et $.
    """
    if parseur.disallow_all:
        return False
    if parseur.allow_all:
        return True
    produit = agent.split('/')[0].lower()
    groupes = []
    for entree in parseur.entries:
        tailles = [len(a) for a in entree.useragents if a != '*' and a.lower() in produit]
        if tailles:
            groupes.append((max(tailles),entree))
    retenues = [e for taille,e in groupes if taille == max(t for t,_ in groupes)] if groupes else ([parseur.default_entry] if parseur.default_entry else [])
    decoupe = urlparse(url)
    chemin = unquote(decoupe.path or '/') + ('?' + unquote(decoupe.query) if decoupe.query else '')
    correspondances = []
    for entree in retenues:
        for regle in entree.rulelines:
            motif = unquote(regle.path)
            ancre = motif.endswith('$')
            corps = motif[:-1] if ancre else motif
            expression = '^' + re.escape(corps).replace(r'\*','.*') + ('$' if ancre else '')
            if re.search(expression,chemin):
                correspondances.append((len(corps.replace('*','').encode('utf-8')),regle.allowance))
    return max(correspondances)[1] if correspondances else True


class ClientPoli:
    def __init__(self, delai_min_s: float = 3.0, delai_max_s: float = 5.0) -> None:
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.delai_min_s = delai_min_s
        self.delai_max_s = delai_max_s
        self._derniere_requete = 0.0
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._indisponibles: dict[str, str] = {}

    def _attendre_son_tour(self) -> None:
        ecoule = time.monotonic() - self._derniere_requete
        attente = random.uniform(self.delai_min_s, self.delai_max_s) - ecoule
        if attente > 0:
            time.sleep(attente)

    def _robots_pour(self, url: str) -> urllib.robotparser.RobotFileParser | None:
        """Charge robots.txt avec NOTRE session (UA honnête).

        RobotFileParser.read() utilise urllib et son UA par défaut, que certains
        sites (ex. papcommerces) refusent en 403 — le parseur conclurait alors,
        à tort, « tout interdit ». RFC 9309 : un robots en 5xx ou inaccessible
        suspend la collecte jusqu'à la prochaine tournée.
        """
        decoupe = urlparse(url)
        hote = f"{decoupe.scheme}://{decoupe.netloc}"
        if hote in self._indisponibles:
            raise SourceTemporaireErreur(self._indisponibles[hote])
        if hote not in self._robots:
            parseur: urllib.robotparser.RobotFileParser | None = None
            try:
                self._attendre_son_tour()
                reponse = self.session.get(f"{hote}/robots.txt", timeout=15)
                self._derniere_requete = time.monotonic()
                if reponse.status_code == 429 or reponse.status_code >= 500:
                    self._indisponibles[hote] = f"robots.txt indisponible : HTTP {reponse.status_code} sur {hote}"
                    raise SourceTemporaireErreur(self._indisponibles[hote])
                if reponse.status_code == 200:
                    parseur = urllib.robotparser.RobotFileParser()
                    parseur.parse(reponse.text.splitlines())
                else:
                    log.warning(
                        "robots.txt de %s en HTTP %s — consignes réputées absentes",
                        hote, reponse.status_code,
                    )
            except requests.RequestException as exc:
                self._derniere_requete = time.monotonic()
                self._indisponibles[hote] = f"robots.txt inaccessible pour {hote}"
                raise SourceTemporaireErreur(f"robots.txt inaccessible pour {hote}") from exc
            self._robots[hote] = parseur
        return self._robots[hote]

    def obtenir(self, url: str) -> str:
        """GET poli. Lève SourceBloqueeErreur sur refus (robots, 403, 429)."""
        parseur = self._robots_pour(url)
        if parseur is not None and not robots_autorise(parseur, USER_AGENT, url):
            raise SourceBloqueeErreur(f"robots.txt interdit {url}")
        if parseur is not None:
            delai = parseur.crawl_delay(USER_AGENT) or parseur.crawl_delay("*")
            if delai:
                self.delai_min_s = max(self.delai_min_s, float(delai))
                self.delai_max_s = max(self.delai_max_s, self.delai_min_s)
        self._attendre_son_tour()
        try:
            reponse = self.session.get(url, timeout=30)
        finally:
            self._derniere_requete = time.monotonic()
        if reponse.status_code == 429 or reponse.status_code >= 500:
            decoupe = urlparse(url)
            hote = f"{decoupe.scheme}://{decoupe.netloc}"
            self._indisponibles[hote] = f"HTTP {reponse.status_code} sur {url} — réessai à la prochaine tournée"
            raise SourceTemporaireErreur(self._indisponibles[hote])
        if reponse.status_code == 403:
            raise SourceBloqueeErreur(f"HTTP {reponse.status_code} sur {url} — arrêt propre")
        reponse.raise_for_status()
        return reponse.text
