"""Emplacement RUE PAR RUE — pas seulement Paris/petite couronne/grande couronne.

Constat de départ : la grille de scoring classe l'emplacement par palier
administratif (département, commune « dynamique »). Deux biens dans le même
arrondissement peuvent pourtant être sur une artère commerçante ou dans une
rue morte. Ce module ajoute un signal mesuré, gratuit et sans clé :

1. `extraire_voie` repère un nom de rue explicite dans le titre/la description
   (« rue X », « place Y »…) — SEULEMENT quand un mot-type de voie est écrit ;
   on ne devine jamais une adresse à partir d'un simple point de repère
   (« proche métro Nation ») pour ne pas fabriquer une fausse précision ;
2. `geocoder` retrouve ses coordonnées via la Base Adresse Nationale
   (api-adresse.data.gouv.fr, service public gratuit, sans clé) ;
3. `densite_commerces` interroge Overpass (données OpenStreetMap, gratuites,
   sans clé) pour compter les commerces actifs et les locaux vacants dans un
   rayon de 150 m — la « vitalité » réelle de la rue.

Ni l'API d'adresse ni Overpass ne sont fiables à 100 % (Overpass en
particulier est un service public parfois saturé) : toute panne ou absence
de résultat renvoie None, honnêtement — la grille administrative reste alors
seule à trancher, sans jamais faire échouer le run ni inventer une valeur.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import requests

from sources.http import USER_AGENT

if TYPE_CHECKING:
    from pipeline.config import Config
    from pipeline.modeles import Annonce

log = logging.getLogger("collecteur.rue")

BAN_URL = "https://api-adresse.data.gouv.fr/search/"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
RAYON_M = 150
SCORE_BAN_MIN = 0.5      # confiance minimale du géocodeur pour retenir un résultat
DELAI_ENTRE_APPELS_S = 1.2  # politesse : ces API publiques tolèrent un usage raisonnable

_MOTS_VOIE = (
    "rue", "avenue", "av", "boulevard", "bd", "place", "allee", "allée",
    "impasse", "quai", "cours", "passage", "square", "villa", "sentier", "chemin",
)
_VOIE_RE = re.compile(
    r"\b(" + "|".join(_MOTS_VOIE) + r")\.?\s+"
    r"([A-ZÀ-Ý0-9][\w'’À-ÿ\-]*(?:\s+[\w'’À-ÿ\-]+){0,5})",
    re.IGNORECASE,
)


def extraire_voie(texte: str) -> str | None:
    """Nom de voie explicite dans le texte, ou None si aucun mot-type trouvé.

    Volontairement conservateur : « proche métro Nation » ne matche pas (pas
    de mot-type de voie) — mieux vaut ne rien évaluer que fabriquer une
    adresse à partir d'un simple repère.
    """
    m = _VOIE_RE.search(texte)
    if not m:
        return None
    voie = f"{m.group(1)} {m.group(2)}"
    voie = re.split(r"\s+-\s+|,", voie)[0].strip()
    return voie if len(voie) >= 6 else None


@dataclass(frozen=True)
class Coordonnees:
    lat: float
    lon: float


class ClientGeo:
    """Petit client dédié aux API publiques de géodonnées (pas du scraping :
    pas de robots.txt à vérifier, mais la même politesse d'espacement)."""

    def __init__(self, delai_s: float = DELAI_ENTRE_APPELS_S) -> None:
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.delai_s = delai_s
        self._derniere_requete = 0.0

    def _attendre(self) -> None:
        ecoule = time.monotonic() - self._derniere_requete
        if ecoule < self.delai_s:
            time.sleep(self.delai_s - ecoule)

    def geocoder(self, voie: str, ville: str, departement: str) -> Coordonnees | None:
        """Coordonnées de la voie via la Base Adresse Nationale, ou None."""
        self._attendre()
        try:
            reponse = self.session.get(
                BAN_URL, params={"q": f"{voie} {ville}", "type": "street", "limit": 1},
                timeout=10,
            )
            self._derniere_requete = time.monotonic()
            reponse.raise_for_status()
            features = reponse.json().get("features", [])
        except Exception as exc:  # noqa: BLE001 — jamais bloquant
            log.info("géocodage BAN indisponible pour %r : %s", voie, exc)
            return None
        if not features:
            return None
        proprietes = features[0]["properties"]
        # Le code postal des sources est parfois approximatif (CP départemental
        # par défaut) : on vérifie le DÉPARTEMENT (code INSEE), plus robuste.
        if proprietes.get("score", 0) < SCORE_BAN_MIN:
            return None
        if str(proprietes.get("citycode", ""))[:2] != departement:
            return None
        lon, lat = features[0]["geometry"]["coordinates"]
        return Coordonnees(lat=lat, lon=lon)

    def densite_commerces(self, coord: Coordonnees) -> "DensiteRue | None":
        """Commerces actifs et locaux vacants dans un rayon de 150 m (OSM)."""
        self._attendre()
        requete = (
            "[out:json][timeout:20];"
            f'(node["shop"](around:{RAYON_M},{coord.lat},{coord.lon});'
            f'way["shop"](around:{RAYON_M},{coord.lat},{coord.lon});'
            f'node["disused:shop"](around:{RAYON_M},{coord.lat},{coord.lon});'
            f'way["disused:shop"](around:{RAYON_M},{coord.lat},{coord.lon}););'
            "out tags;"
        )
        try:
            reponse = self.session.post(
                OVERPASS_URL, data={"data": requete}, timeout=25,
            )
            self._derniere_requete = time.monotonic()
            reponse.raise_for_status()
            elements = reponse.json().get("elements", [])
        except Exception as exc:  # noqa: BLE001 — service public, parfois saturé
            log.info("Overpass indisponible : %s", exc)
            return None
        actifs = 0
        vacants = 0
        for e in elements:
            tags = e.get("tags", {})
            if tags.get("shop") == "vacant" or "disused:shop" in tags:
                vacants += 1
            elif tags.get("shop"):
                actifs += 1
        return DensiteRue(nb_commerces=actifs, nb_vacants=vacants)


@dataclass(frozen=True)
class DensiteRue:
    nb_commerces: int
    nb_vacants: int

    @property
    def categorie(self) -> str:
        if self.nb_commerces >= 15:
            return "tres_commercante"
        if self.nb_commerces >= 8:
            return "commercante"
        if self.nb_commerces >= 3:
            return "calme"
        return "peu_commercante"


def evaluer_rue(voie: str, ville: str, departement: str, client: ClientGeo) -> DensiteRue | None:
    """Pipeline complet géocodage -> densité ; None si une étape échoue."""
    coord = client.geocoder(voie, ville, departement)
    if coord is None:
        return None
    return client.densite_commerces(coord)


def evaluer_annonces(annonces: dict[str, "Annonce"], config: "Config") -> None:
    """Évalue la rue des meilleures annonces non encore renseignées.

    Deux API publiques mais gratuites, sans garantie de disponibilité : le
    volume de requêtes par run est plafonné (politesse + Overpass est parfois
    saturé), en priorisant les annonces au score déjà le plus élevé — celles
    qui comptent vraiment. Une évaluation ratée (pas de voie détectée, pas de
    résultat de géocodage, Overpass en panne) n'est PAS marquée comme faite
    quand la cause est une panne réseau : un prochain run réessaiera.

    Garde-fou de TEMPS (pas seulement de volume) : Overpass est un service
    public parfois lent à échouer (timeouts de plusieurs secondes) ; sans
    budget de temps, une série de pannes pourrait allonger la tournée bien
    au-delà de ce que le nombre de candidats laisse penser. On s'arrête net
    au budget, même en plein milieu de la liste — le reste attendra le
    prochain run.
    """
    cfg = config.scoring.get("rue", {})
    max_par_run = int(cfg.get("max_par_run", 25))
    budget_s = float(cfg.get("budget_secondes", 120))
    if max_par_run <= 0 or budget_s <= 0:
        return
    candidats = sorted(
        (a for a in annonces.values() if not a.exclue and not a.rue_evaluee),
        key=lambda a: a.score or 0, reverse=True,
    )[:max_par_run]
    if not candidats:
        return
    client = ClientGeo()
    debut = time.monotonic()
    for a in candidats:
        if time.monotonic() - debut > budget_s:
            log.info("budget de temps rue (%.0f s) atteint, arrêt pour ce run", budget_s)
            break
        voie = extraire_voie(a.texte_complet())
        if voie is None:
            a.rue_evaluee = True   # rien à extraire dans le texte : inutile de retenter
            continue
        try:
            densite = evaluer_rue(voie, a.ville, a.departement, client)
        except Exception:  # noqa: BLE001 — jamais bloquant pour le run
            log.exception("évaluation de rue en échec pour %s", a.url)
            continue
        if densite is None:
            continue  # géocodage/Overpass indisponible : on retentera plus tard
        a.rue_voie = voie
        a.rue_nb_commerces = densite.nb_commerces
        a.rue_nb_vacants = densite.nb_vacants
        a.rue_categorie = densite.categorie
        a.rue_evaluee = True
