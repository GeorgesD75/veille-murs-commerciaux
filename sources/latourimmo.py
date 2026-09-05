"""latourimmo.com — cabinet indépendant, vente de locaux commerciaux (Paris/IDF).

Validation robots.txt (relevé le 2026-08-16) : autorisé pour `User-agent: *`
(seuls quelques chemins techniques `/passe/`, `/inc/`, `/lib/`… sont interdits,
sans rapport avec le listing) ; une longue liste de robots connus est bloquée
nommément, notre user-agent honnête n'y figure pas.

La page listing mélange VENTE et LOCATION (le titre de chaque carte commence
par l'un des deux) — seules les « Vente » sont retenues, les « Location »
n'entrent pas dans le sujet de cet outil. Une douzaine de biens au total,
non paginé (le bloc de pagination de la page est vide).
"""
from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from bs4.element import Tag

from pipeline.modeles import AnnonceBrute
from sources.base import SourceHtml
from sources.extraction import LIMITE_DESCRIPTION, deviner_type_murs, extraire_nombre, extraire_surface

_ID_LIEN = re.compile(r"-(\d+)$")
_CP_VILLE = re.compile(r"\b(\d{5})\s+([A-ZÀ-Ý][\wÀ-ÿ'’ -]*)$")
_PREFIXE_VENTE = re.compile(r"^vente\s*-\s*", re.IGNORECASE)


def _texte(element: Tag | None) -> str:
    return element.get_text(" ", strip=True) if element else ""


class SourceLaTourImmo(SourceHtml):
    nom = "latourimmo"
    BASE = "https://www.latourimmo.com"
    LISTE = "/nos-biens-a-la-vente-locaux-commerciaux-w1"

    def collecter(self) -> list[AnnonceBrute]:
        return self.collecter_pages([(self.LISTE, None)], lambda html, _ctx: self.extraire(html))

    def extraire(self, html: str) -> list[AnnonceBrute]:
        soup = BeautifulSoup(html, "html.parser")
        annonces: dict[str, AnnonceBrute] = {}
        grille = soup.select_one(".grid-listing")
        if grille is None:
            return []
        for carte in grille.find_all("div", class_="ann", recursive=False):
            annonce = self._extraire_carte(carte)
            if annonce is not None:
                annonces.setdefault(annonce.id_source, annonce)
        return list(annonces.values())

    def _extraire_carte(self, carte: Tag) -> AnnonceBrute | None:
        lien = carte.select_one("h2 a")
        if lien is None or not lien.get("href"):
            return None
        titre_complet = _texte(lien)
        if not titre_complet.lower().startswith("vente"):
            return None  # « Location » : hors sujet, ce projet ne traite que l'achat

        href = str(lien["href"])
        id_trouve = _ID_LIEN.search(href)
        if not id_trouve:
            return None

        titre = _PREFIXE_VENTE.sub("", titre_complet).strip() or titre_complet
        cp_ville = _CP_VILLE.search(titre_complet)
        code_postal = cp_ville.group(1) if cp_ville else ""
        ville = cp_ville.group(2).strip().title() if cp_ville else ""

        prix = None
        for champ in carte.select(".primaire-immo"):
            libelle = _texte(champ.select_one(".primaire-immo__label")).lower()
            if libelle == "prix":
                prix = extraire_nombre(_texte(champ.select_one(".primaire-immo__valeur")))

        description = _texte(carte.select_one(".ann-desc"))

        image = None
        img_el = carte.select_one("picture img, img")
        if img_el is not None:
            src = img_el.get("src")
            if src and str(src).startswith("http"):
                image = str(src)

        return AnnonceBrute(
            id_source=id_trouve.group(1),
            source=self.nom,
            url=urljoin(self.BASE + "/", href),
            titre=titre,
            ville=ville,
            code_postal=code_postal,
            type_murs=deviner_type_murs(f"{titre_complet} {description}"),
            prix=prix,
            surface_m2=extraire_surface(titre_complet) or extraire_surface(description),
            loyer_mensuel=None,
            image_url=image,
            description=description[:LIMITE_DESCRIPTION],
        )
