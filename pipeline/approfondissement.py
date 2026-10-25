"""Approfondissement : lire la PAGE DE DÉTAIL des meilleures annonces.

Le point faible n°1 de l'outil : les pages de LISTE des sites ne donnent
qu'un extrait — le loyer réel, la classe énergie, les dettes de copropriété,
l'article 606 ou le nom de la rue se cachent souvent dans la page de détail
que personne ne lisait. Ce module va la chercher, poliment, pour les
meilleures annonces seulement (budget par tournée).

Aucun parseur par site : on extrait le TEXTE brut de la page (balises
retirées) et on le stocke dans `texte_detail`, qui est inclus dans
`texte_complet()` — TOUS les détecteurs existants en profitent d'un coup :
filtre anti-fonds-de-commerce, loyer, DPE, dettes de copro, article 606,
caractéristiques, extraction du nom de rue (signal OpenStreetMap), baux
comparables (un loyer réel trouvé nourrit les estimations des voisins).

Limites assumées, documentées :
- une page de détail contient parfois des « annonces similaires » : les
  extracteurs par mots-clés sont conservateurs, mais un signal peut venir
  d'un encart voisin — c'est un filet de plus, jamais une preuve ;
- les sites entièrement JavaScript (bienici…) rendent peu de texte : on
  marque la tentative faite et on passe, sans erreur ;
- politesse identique au reste : ClientPoli (robots.txt, 3-5 s entre
  requêtes), plafond d'annonces ET budget de temps par tournée.
"""
from __future__ import annotations

import logging
import re
import time
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from sources.extraction import extraire_surface, loyer_mensuel_depuis_texte
from sources.http import ClientPoli, SourceBloqueeErreur, SourceTemporaireErreur

if TYPE_CHECKING:
    from pipeline.config import Config
    from pipeline.modeles import Annonce

log = logging.getLogger("collecteur.approfondissement")

TAILLE_TEXTE_DETAIL = 3000   # assez pour les détecteurs, sans gonfler le stockage
_SCRIPTS = re.compile(r"<(script|style|noscript|svg|nav|footer|header)[^>]*>.*?</\1>",
                      re.DOTALL | re.IGNORECASE)
_BALISES = re.compile(r"<[^>]+>")
_ENTITES = {"&amp;": "&", "&nbsp;": " ", "&#39;": "'", "&apos;": "'",
            "&quot;": '"', "&lt;": "<", "&gt;": ">", "&eacute;": "é", "&egrave;": "è"}


def texte_de_page(html: str) -> str:
    """Isole le contenu principal et retire les recommandations d'autres biens."""
    soup = BeautifulSoup(html, "html.parser")
    for noeud in soup.select("script, style, noscript, svg, nav, footer, header, aside, form"):
        noeud.decompose()
    for noeud in list(soup.find_all(["section", "div", "ul"])):
        if noeud.attrs is None:
            continue
        identite = " ".join(noeud.get("class", [])) + " " + str(noeud.get("id", ""))
        if re.search(r"similar|related|recommend|suggest|autres-annonces", identite, re.I):
            noeud.decompose()
    racine = soup.select_one("main, [role='main']") or soup.body or soup
    for titre in racine.find_all(["h2", "h3", "h4"]):
        if re.search(r"annonces? similaires?|biens? similaires?|vous aimerez|autres (?:annonces|biens)",
                     titre.get_text(" ", strip=True), re.I):
            for suivant in list(titre.find_all_next()):
                suivant.decompose()
            titre.decompose()
            break
    return " ".join(racine.get_text(" ", strip=True).split())


def approfondir(annonce: "Annonce", texte: str) -> list[str]:
    """Applique le texte de détail à l'annonce ; retourne ce qui a été appris."""
    appris: list[str] = []
    annonce.texte_detail = texte[:TAILLE_TEXTE_DETAIL]
    if annonce.loyer_mensuel is None:
        loyer = loyer_mensuel_depuis_texte(texte, annonce.prix)
        if loyer:
            annonce.loyer_mensuel = loyer
            appris.append(f"loyer {loyer:.0f} €/mois")
    if annonce.surface_m2 is None:
        surface = extraire_surface(texte)
        if surface:
            annonce.surface_m2 = surface
            appris.append(f"surface {surface:.0f} m²")
    return appris


def approfondir_annonces(annonces: dict[str, "Annonce"], config: "Config") -> None:
    """Va lire la page de détail des meilleures annonces pas encore lues.

    Priorité aux scores élevés (ceux qui comptent), et parmi eux à ceux dont
    le loyer manque (la donnée la plus précieuse). Une page en échec réseau
    n'est pas marquée : un prochain run réessaiera. Un site bloqué (robots,
    403) marque l'annonce pour ne pas s'acharner.
    """
    cfg = dict(config["analyse"].get("approfondissement") or {})
    if not cfg.get("actif", False):
        return
    max_par_run = int(cfg.get("max_par_run", 10))
    budget_s = float(cfg.get("budget_secondes", 90))
    if max_par_run <= 0 or budget_s <= 0:
        return

    candidats = sorted(
        (a for a in annonces.values()
         if not a.exclue and not a.approfondie and a.url.startswith("http")),
        key=lambda a: (
            bool(a.surface_m2 and 0 < a.surface_m2 < config.donnees.get("recherche", {}).get("surface_max_m2", 40)),
            a.code_postal == "75018", a.date_derniere_vue, (a.score or 50), a.loyer_mensuel is None),
        reverse=True,
    )
    if not candidats:
        return

    client = ClientPoli()
    hotes_bloques: set[str] = set()
    debut = time.monotonic()
    tentatives = 0
    for a in candidats:
        hote = urlparse(a.url).netloc
        if hote in hotes_bloques:
            continue
        if tentatives >= max_par_run:
            break
        if time.monotonic() - debut > budget_s:
            log.info("budget de temps approfondissement (%.0f s) atteint", budget_s)
            break
        tentatives += 1
        try:
            html = client.obtenir(a.url)
        except SourceTemporaireErreur as exc:
            hotes_bloques.add(hote)
            log.info("hôte temporairement indisponible (%s) : %s", hote, exc)
            continue
        except SourceBloqueeErreur as exc:
            a.approfondie = True   # interdit : inutile d'y revenir
            hotes_bloques.add(hote)
            log.info("détail refusé (%s) : %s", a.url, exc)
            continue
        except Exception as exc:  # noqa: BLE001 — jamais bloquant, on retentera
            log.info("détail indisponible (%s) : %s", a.url, exc)
            continue
        texte = texte_de_page(html)
        if len(texte) < 80:
            log.info("détail trop pauvre (%s), aucune donnée inférée", a.url)
            continue
        appris = approfondir(a, texte)
        a.approfondie = True
        if appris:
            log.info("approfondi %s : %s", a.url, ", ".join(appris))
