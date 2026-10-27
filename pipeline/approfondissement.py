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
import json
import time
from collections import deque
from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from urllib.parse import urlparse, urljoin

from bs4 import BeautifulSoup
import requests

from sources.extraction import extraire_surface, loyer_mensuel_depuis_texte
from sources.http import ClientPoli, SourceBloqueeErreur, SourceTemporaireErreur
from sources.donnees_structurees import appliquer_structure, extraire_structure
from pipeline.fiabilite import noter_preuve
from pipeline.normalisation import maintenant_iso
from pipeline.texte import normaliser_texte
from pipeline.transaction import qualifier_transaction

if TYPE_CHECKING:
    from pipeline.config import Config
    from pipeline.modeles import Annonce

log = logging.getLogger("collecteur.approfondissement")

TAILLE_TEXTE_DETAIL = 12000  # garder aussi les clauses en fin de description
_SCRIPTS = re.compile(r"<(script|style|noscript|svg|nav|footer|header)[^>]*>.*?</\1>",
                      re.DOTALL | re.IGNORECASE)
_BALISES = re.compile(r"<[^>]+>")
_ENTITES = {"&amp;": "&", "&nbsp;": " ", "&#39;": "'", "&apos;": "'",
            "&quot;": '"', "&lt;": "<", "&gt;": ">", "&eacute;": "é", "&egrave;": "è"}


def est_page_de_liste(html: str, url: str | None = None) -> bool:
    """Une ancienne fiche peut rediriger silencieusement vers les résultats."""
    soup = BeautifulSoup(html, "html.parser")
    canonical = soup.select_one('link[rel="canonical"][href]')
    if url and canonical:
        chemin = urlparse(urljoin(url,str(canonical['href']))).path.rstrip('/')
        if chemin != urlparse(url).path.rstrip('/') and re.search(
            r'^/(?:annonces,|commerce/vente-(?:local|locaux)|fr/(?:acheter-murs|murs-de-boutique-)|immobilier-d-entreprise/annonces/)',chemin):
            return True
    contexte = soup.select_one("script#react-context")
    if contexte:
        try:
            d = json.loads(contexte.string or contexte.get_text())
            if len((d.get("global") or {}).get("results", {}).get("items", [])) > 1:
                return True
        except (ValueError, TypeError, AttributeError):
            pass
    h1 = " ".join(e.get_text(" ", strip=True) for e in soup.select("h1"))
    return bool(re.search(r"\d+\s+annonces?", h1, re.I)) and len(soup.select('a[href*="/annonce/"]')) > 3


def texte_de_page(html: str) -> str:
    """Isole le contenu principal et retire les recommandations d'autres biens."""
    soup = BeautifulSoup(html, "html.parser")
    titres = soup.select("h1")
    titre_principal = titres[0].get_text(" ", strip=True) if len(titres) == 1 else ""
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
    texte = " ".join(racine.get_text(" ", strip=True).split())
    if titre_principal and titre_principal not in texte:
        texte = titre_principal + " " + texte
    return texte


def approfondir(annonce: "Annonce", texte: str, quand: str | None = None) -> list[str]:
    """Applique le texte de détail à l'annonce ; retourne ce qui a été appris."""
    appris: list[str] = []
    quand = quand or maintenant_iso()
    annonce.texte_detail = texte[:TAILLE_TEXTE_DETAIL]
    if annonce.loyer_mensuel is None or annonce.loyer_origine == "rendement":
        loyer = loyer_mensuel_depuis_texte(texte, annonce.prix, annonce.surface_m2)
        if loyer:
            annonce.loyer_mensuel = loyer
            annonce.loyer_origine = "fiche_texte"
            noter_preuve(annonce, "loyer_mensuel", loyer, "fiche:texte", quand, texte)
            appris.append(f"loyer {loyer:.0f} €/mois")
    if annonce.surface_m2 is None:
        surface = extraire_surface(texte)
        if surface:
            annonce.surface_m2 = surface
            noter_preuve(annonce, "surface_m2", surface, "fiche:texte", quand, texte)
            appris.append(f"surface {surface:.0f} m²")
    return appris


def approfondir_annonces(annonces: dict[str, "Annonce"], config: "Config") -> dict:
    """Va lire la page de détail des meilleures annonces pas encore lues.

    Deux petites surfaces puis une opportunité hors surface cible, pour ne
    pas laisser les grandes annonces prometteuses sans lecture détaillée.
    Une page en échec réseau
    n'est pas marquée : un prochain run réessaiera. Un site bloqué (robots,
    403) marque l'annonce pour ne pas s'acharner.
    """
    cfg = dict(config["analyse"].get("approfondissement") or {})
    rapport = {"tentees": 0, "lues": 0, "champs_ajoutes": 0, "refusees": 0, "temporaires": 0, "pauvres": 0, "retirees": 0, "listes": 0}
    if not cfg.get("actif", False):
        return rapport
    max_par_run = int(cfg.get("max_par_run", 10))
    budget_s = float(cfg.get("budget_secondes", 90))
    if max_par_run <= 0 or budget_s <= 0:
        return rapport

    quand = maintenant_iso()
    maintenant = datetime.fromisoformat(quand)

    def eligible(a):
        age_max = cfg.get("age_max_jours")
        if age_max and datetime.fromisoformat(a.date_derniere_vue) < maintenant - timedelta(days=int(age_max)):
            return False
        if a.date_detail_tentative:
            delai = 30 if a.etat_detail == "refuse" else 14 if a.etat_detail == "retiree" else 7 if a.etat_detail in {"lu", "redirection_liste"} else 1
            if datetime.fromisoformat(a.date_detail_tentative) > maintenant - timedelta(days=delai):
                return False
        return not a.approfondie or bool(a.texte_detail) or bool(a.date_detail_tentative)

    limite_surface = config.donnees.get("recherche", {}).get("surface_max_m2", 40)
    def petite(a):
        return bool(a.surface_m2 and 0 < a.surface_m2 < limite_surface)

    candidats = sorted(
        (a for a in annonces.values()
         if (not a.exclue or a.raison_exclusion in {"prix non renseigné", "hors Île-de-France (département inconnu)"}
             or (a.raison_exclusion or "").startswith("suspect_fonds"))
         and qualifier_transaction(a)["nature"] not in {"fonds", "bail", "mixte", "location"}
         and eligible(a) and a.url.startswith("http")),
        key=lambda a: (
            petite(a),
            a.etat_detail != "lu",
            a.code_postal == "75018", a.date_derniere_vue, (a.score or 50), a.loyer_mensuel is None),
        reverse=True,
    )
    if not candidats:
        return rapport
    rapport["candidats"] = len(candidats)

    scoring = config.donnees.get("scoring", {})
    seuils = scoring.get("seuils", {})
    def prometteuse(a):
        # Un score précédent OU le revenu déclaré justifie d'aller lire la
        # fiche. Cela ne suffit pas à qualifier une pépite sur le dashboard.
        if (a.score or 0) >= seuils.get("affichage", 65):
            return True
        if not a.prix or not a.loyer_mensuel or a.loyer_estime or a.loyer_origine == "rendement":
            return False
        rendement = a.loyer_mensuel * 1200 / a.prix
        return seuils.get("rendement_minimum_vert", 7) <= rendement <= scoring.get("seuil_alerte_rendement_pct", 10)

    def repartir(lot):
        if not cfg.get("repartir_sources", False):
            return list(lot)
        files = {}
        for a in lot:
            files.setdefault(urlparse(a.url).netloc, deque()).append(a)
        resultat = []
        while files:
            for hote in list(files):
                resultat.append(files[hote].popleft())
                if not files[hote]:
                    del files[hote]
        return resultat

    petites = deque(repartir(a for a in candidats if petite(a)))
    opportunites = deque(repartir(sorted((a for a in candidats if not petite(a) and prometteuse(a)),
                                key=lambda a: (a.score or 50, a.date_derniere_vue), reverse=True)))
    autres = repartir(a for a in candidats if not petite(a) and not prometteuse(a))
    candidats = []
    # Un tiers des créneaux disponibles, tant que les deux files sont pleines.
    # Aucun appel supplémentaire : les mêmes plafonds de temps/requêtes restent appliqués.
    while petites and opportunites:
        for _ in range(2):
            if petites:
                candidats.append(petites.popleft())
        candidats.append(opportunites.popleft())
    candidats.extend(petites)
    candidats.extend(opportunites)
    candidats.extend(autres)

    client = ClientPoli()
    hotes_bloques: set[str] = set()
    debut = time.monotonic()
    tentatives = 0
    par_hote = {}
    plafond_hote = int(cfg.get("max_par_hote", max_par_run))
    for a in candidats:
        hote = urlparse(a.url).netloc
        if hote in hotes_bloques or par_hote.get(hote, 0) >= plafond_hote:
            continue
        if tentatives >= max_par_run:
            break
        if time.monotonic() - debut > budget_s:
            log.info("budget de temps approfondissement (%.0f s) atteint", budget_s)
            break
        tentatives += 1
        par_hote[hote] = par_hote.get(hote, 0) + 1
        rapport["tentees"] += 1
        a.date_detail_tentative = quand
        try:
            html = client.obtenir(a.url)
        except SourceTemporaireErreur as exc:
            a.etat_detail = "temporaire"
            rapport["temporaires"] += 1
            hotes_bloques.add(hote)
            log.info("hôte temporairement indisponible (%s) : %s", hote, exc)
            continue
        except SourceBloqueeErreur as exc:
            a.approfondie = True   # interdit : inutile d'y revenir
            a.etat_detail = "refuse"
            rapport["refusees"] += 1
            hotes_bloques.add(hote)
            log.info("détail refusé (%s) : %s", a.url, exc)
            continue
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code in {404, 410}:
                a.etat_detail, a.approfondie = "retiree", True
                rapport["retirees"] += 1
            else:
                a.etat_detail = "temporaire"
                rapport["temporaires"] += 1
            log.info("détail HTTP indisponible (%s) : %s", a.url, exc)
            continue
        except Exception as exc:  # noqa: BLE001 — jamais bloquant, on retentera
            a.etat_detail = "temporaire"
            rapport["temporaires"] += 1
            log.info("détail indisponible (%s) : %s", a.url, exc)
            continue
        if est_page_de_liste(html, a.url):
            a.etat_detail, a.approfondie = "redirection_liste", True
            rapport["listes"] += 1
            log.info("page de résultats ignorée à la place de la fiche : %s", a.url)
            continue
        donnees = extraire_structure(html, a.url)
        texte = donnees.get("description") or texte_de_page(html)
        if donnees.get("description"):
            titres = BeautifulSoup(html, "html.parser").select("h1")
            if len(titres) == 1:
                texte = titres[0].get_text(" ", strip=True) + " " + texte
        if donnees.get("retiree") or re.search(r"cette annonce n.est plus disponible|cette annonce a ete (?:supprimee|retiree)|ce bien n.est plus disponible", normaliser_texte(texte)):
            a.etat_detail, a.approfondie = "retiree", True
            rapport["retirees"] += 1
            continue
        if len(texte) < 80:
            a.etat_detail = "pauvre"
            rapport["pauvres"] += 1
            log.info("détail trop pauvre (%s), aucune donnée inférée", a.url)
            continue
        appris = appliquer_structure(a, donnees, quand)
        appris += approfondir(a, texte, quand)
        a.approfondie = True
        a.etat_detail = "lu"
        a.date_detail_vue = quand
        rapport["lues"] += 1
        nature = qualifier_transaction(a)["nature"]
        rapport.setdefault("natures_apres_lecture", {})[nature] = rapport.get("natures_apres_lecture", {}).get(nature, 0) + 1
        rapport["champs_ajoutes"] += len(appris)
        if appris:
            log.info("approfondi %s : %s", a.url, ", ".join(appris))
    rapport["par_hote"] = par_hote
    rapport["restantes"] = max(0, len(candidats)-tentatives)
    return rapport
