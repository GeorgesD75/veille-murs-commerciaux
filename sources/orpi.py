"""orpi.com — réseau national d'agences indépendantes, section « commerces et
entreprises », vente de locaux commerciaux.

Validation robots.txt (relevé le 2026-08-23) : le chemin /commerces-entreprises/
n'apparaît dans AUCUNE règle Disallow (elles visent /estate/*, /recherche/*,
/annonces-immobilieres-*/*-pieces/ — préfixe résidentiel différent, /login*…) ;
seul le paramètre ?contact=* est interdit — jamais utilisé ici, on ne suit que
le lien canonique de chaque carte (celui qui n'a pas ce paramètre).

Un seul filtre géographique « Île-de-France » couvre toute la zone du projet
(pas besoin d'itérer département par département comme bureauxlocaux.py) ;
pagination ?page=2, 3… — 9 pages constatées le 2026-08-23, la 10e renvoie
proprement un 404 (pas de contenu dupliqué à filtrer, comme bureauxlocaux).

Chaque carte porte un attribut `data-eulerian-action` (tracking analytics)
au format JSON : prix (prdamount) et surface (surfaceBien) en sont extraits
directement, plus fiable que de reparser « 163 000 € » (espaces insécables,
encodage). codePostal y est systématiquement vide — récupéré depuis le slug
de l'URL de la fiche à la place (même logique que cessionpme.py). Une carte
« à la une » réapparaît en tête de page (même piège que cessionpme.com) :
dédoublonnée par id_source, lui aussi tiré de l'URL.
"""
from __future__ import annotations

import json
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from bs4.element import Tag

from pipeline.modeles import AnnonceBrute
from sources.base import SourceHtml
from sources.extraction import LIMITE_DESCRIPTION, deviner_type_murs

_HREF = re.compile(r"annonce-vente-local-commercial-(?P<ville>.+)-(?P<cp>\d{5})-(?P<id>[\w-]+)/?$")
_PETITS_MOTS = {"de", "du", "des", "le", "la", "les", "sur", "sous", "en", "aux", "et"}


def _ville_depuis_slug(slug: str) -> str:
    """'sainte-genevieve-des-bois' -> 'Sainte Genevieve Des Bois' (accents perdus
    par le slug côté source, comme pour cessionpme.py — jamais devinés)."""
    mots = []
    for mot in slug.split("-"):
        mots.append(mot if mot in _PETITS_MOTS and mots else mot.capitalize())
    return " ".join(mots)


def _texte(element: Tag | None) -> str:
    return element.get_text(" ", strip=True) if element else ""


def _nombre_positif(valeur: object) -> float | None:
    try:
        f = float(valeur)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return f if f > 0 else None


class SourceOrpi(SourceHtml):
    nom = "orpi"
    BASE = "https://www.orpi.com"
    LISTE = "/commerces-entreprises/annonces-immobilieres-ile-de-france/vente-local-commercial/"

    def __init__(self, client=None, max_pages: int = 9) -> None:
        super().__init__(client)
        self.max_pages = max_pages

    def collecter(self) -> list[AnnonceBrute]:
        pages = [(self.LISTE, None)] + [
            (f"{self.LISTE}?page={p}", None) for p in range(2, self.max_pages + 1)
        ]
        return self.collecter_pages(pages, lambda html, _ctx: self.extraire(html))

    def extraire(self, html: str) -> list[AnnonceBrute]:
        soup = BeautifulSoup(html, "html.parser")
        annonces: dict[str, AnnonceBrute] = {}
        for carte in soup.find_all("article", class_="c-estate-thumb"):
            annonce = self._extraire_carte(carte)
            if annonce is not None:
                annonces.setdefault(annonce.id_source, annonce)
        return list(annonces.values())

    def _extraire_carte(self, carte: Tag) -> AnnonceBrute | None:
        lien = carte.select_one("a.link-unstyled")
        href = str(lien.get("href", "")).split("?")[0] if lien is not None else ""
        ref = _HREF.search(href)
        if not ref:
            return None

        ville = _ville_depuis_slug(ref.group("ville"))
        prix = surface = None
        bouton = carte.select_one("[data-eulerian-action]")
        if bouton is not None:
            try:
                data = json.loads(bouton["data-eulerian-action"])
            except (ValueError, KeyError, TypeError):
                data = {}
            prix = _nombre_positif(data.get("prdamount"))
            surface = _nombre_positif(data.get("surfaceBien"))

        description = _texte(carte.select_one(".text-sm.mt-sm"))
        type_libelle = _texte(carte.select_one("[data-oncrawl=estate-type]")) or "Local commercial"

        image = None
        img_el = carte.select_one("img")
        if img_el is not None:
            src = img_el.get("data-src") or img_el.get("src")
            if src and str(src).startswith("http"):
                image = str(src)

        return AnnonceBrute(
            id_source=ref.group("id"),
            source=self.nom,
            url=urljoin(self.BASE, href),
            titre=f"{type_libelle} {ville}".strip(),
            ville=ville,
            code_postal=ref.group("cp"),
            type_murs=deviner_type_murs(f"{type_libelle} {description}"),
            prix=prix,
            surface_m2=surface,
            loyer_mensuel=None,
            image_url=image,
            description=description[:LIMITE_DESCRIPTION],
        )
