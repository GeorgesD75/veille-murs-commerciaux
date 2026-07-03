"""cessionpme.com — listing « vente de locaux commerciaux / boutiques » déjà
filtré Île-de-France (1 000+ annonces, cartes rendues côté serveur).

Validation robots.txt (relevé du 2026-07-03) : `Allow: /` ; seuls quelques
paramètres de requête sont interdits (`bounds=`, `tribarre=`, `moteur=OUI`…),
nous n'en utilisons aucun. Une requête par run sur le listing de base.

Attention connue : cette place de marché mélange parfois de vrais murs et des
affaires proches du fonds de commerce mal rangées ; les filtres du pipeline
(mots-clés + cohérence prix/m²) font le tri en aval.
"""
from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from bs4.element import Tag

from pipeline.modeles import AnnonceBrute
from pipeline.texte import normaliser_texte
from sources.base import SourceHtml
from sources.extraction import (
    deviner_type_murs,
    extraire_nombre,
    extraire_surface,
    loyer_mensuel_depuis_texte,
)

_ARRONDISSEMENT = re.compile(r"paris\s*(\d{1,2})\s*e", re.IGNORECASE)
_CP = re.compile(r"\b(\d{5})\b")
_DEPT_PARENTHESES = re.compile(r"\((\d{2})\)")


def _texte(element: Tag | None) -> str:
    return element.get_text(" ", strip=True) if element else ""


class SourceCessionPme(SourceHtml):
    nom = "cessionpme"
    BASE = "https://www.cessionpme.com"
    PAGES = [
        (
            "/annonces,vente-immobilier-entreprise-locaux-commerciaux-boutiques-"
            "ile-de-france,54,8,V,10,offres.html",
            None,
        )
    ]

    def collecter(self) -> list[AnnonceBrute]:
        return self.collecter_pages(self.PAGES, lambda html, _ctx: self.extraire(html))

    def extraire(self, html: str) -> list[AnnonceBrute]:
        soup = BeautifulSoup(html, "html.parser")
        annonces: dict[str, AnnonceBrute] = {}
        for carte in soup.select("a.offer-card"):
            annonce = self._extraire_carte(carte)
            if annonce is not None:
                # la carte « à la une » peut réapparaître dans la liste
                annonces.setdefault(annonce.id_source, annonce)
        return list(annonces.values())

    def _code_postal(self, ville: str, texte: str) -> str:
        arrondissement = _ARRONDISSEMENT.search(normaliser_texte(ville))
        if arrondissement:
            return f"750{int(arrondissement.group(1)):02d}"
        cp = _CP.search(texte)
        if cp:
            return cp.group(1)
        dept = _DEPT_PARENTHESES.search(texte)
        if dept:
            return dept.group(1).ljust(5, "0")
        return ""

    def _extraire_carte(self, carte: Tag) -> AnnonceBrute | None:
        href = str(carte.get("href", ""))
        ref = re.search(r",(\d{5,}),[A-Z],offre\.html$", href)
        if not ref:
            return None

        titre_source = _texte(
            carte.select_one(".offer-card__header-title")
            or carte.select_one(".offer-card__a-la-une-title")
        )
        description = _texte(carte.select_one(".offer-card__description"))

        prix = surface = None
        for badge in carte.select(".badge"):
            libelle = normaliser_texte(_texte(badge.select_one(".badge__label")))
            valeur = _texte(badge.select_one(".badge__content__inner"))
            if libelle.startswith("prix"):
                prix = extraire_nombre(valeur)
            elif libelle == "surface":
                surface = extraire_nombre(valeur)
        if surface is None:
            surface = extraire_surface(description)

        # « Vente Locaux commerciaux - Boutiques à Paris 11e » -> ville
        titre_attr = str(carte.get("title", ""))
        ville = ""
        m_ville = re.search(r"\bà\s+(.+)$", titre_attr)
        if m_ville:
            ville = m_ville.group(1).strip()

        type_murs = deviner_type_murs(f"{titre_source} {description}")

        image = None
        img_el = carte.select_one(".offer-card__picture img")
        if img_el is not None:
            src = img_el.get("src") or img_el.get("data-src")
            if src and str(src).startswith(("http", "/")):
                image = urljoin(self.BASE, str(src))

        return AnnonceBrute(
            id_source=ref.group(1),
            source=self.nom,
            url=urljoin(self.BASE, href),
            # Titre de la SOURCE, sans préfixe ajouté : le contrôle « suspect_fonds »
            # exige une mention des murs par l'annonceur lui-même.
            titre=titre_source or ville,
            ville=ville,
            code_postal=self._code_postal(ville, f"{titre_source} {description}"),
            type_murs=type_murs,
            prix=prix,
            surface_m2=surface,
            loyer_mensuel=loyer_mensuel_depuis_texte(description, prix),
            image_url=image,
            description=description[:600],
        )
