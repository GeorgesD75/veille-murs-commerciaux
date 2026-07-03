"""papcommerces.fr — annonces de particuliers et pros (le site commerces de PAP).

Validation robots.txt (relevé du 2026-07-03) : les listings de base
`/commerce/vente-local-commercial-…` sont autorisés ; seuls les tris
(`tri-…`), fourchettes de prix (`a-partir-de`, `jusqu-a`), rayons
(`a-XX-km-autour-de`) et query strings sont interdits — nous n'en utilisons
aucun. Le tri par défaut est « plus récentes d'abord ».

Particularités : prix au format « 515.000 € » (milliers à point), type de murs
et loyer déduits de la description (« Vendu loué : 2 087 € »), code postal
parfois absent de l'URL (déduit de l'arrondissement : « Paris 5e » -> 75005).
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


def _texte(element: Tag | None) -> str:
    return element.get_text(" ", strip=True) if element else ""


class SourcePapCommerces(SourceHtml):
    nom = "papcommerces"
    BASE = "https://www.papcommerces.fr"
    PAGES = [("/commerce/vente-local-commercial-ile-de-france-g439", None)]

    def collecter(self) -> list[AnnonceBrute]:
        return self.collecter_pages(self.PAGES, lambda html, _ctx: self.extraire(html))

    def extraire(self, html: str) -> list[AnnonceBrute]:
        soup = BeautifulSoup(html, "html.parser")
        annonces: list[AnnonceBrute] = []
        for carte in soup.select("div.search-list-item"):
            annonce = self._extraire_carte(carte)
            if annonce is not None:
                annonces.append(annonce)
        return annonces

    def _code_postal(self, href: str, textes: str, ville: str) -> str:
        cp = re.search(r"-(\d{5})-r\d+$", href)
        if cp:
            return cp.group(1)
        cp = re.search(r"\((\d{5})\)", textes)
        if cp:
            return cp.group(1)
        arrondissement = _ARRONDISSEMENT.search(normaliser_texte(ville))
        if arrondissement:
            return f"750{int(arrondissement.group(1)):02d}"
        return ""

    def _extraire_carte(self, carte: Tag) -> AnnonceBrute | None:
        lien = carte.select_one("a.item-title")
        if lien is None:
            return None
        href = str(lien.get("href", ""))
        ref = re.search(r"-r(\d+)$", href)
        if not ref:
            return None

        entete = _texte(carte.select_one(".item-title .h1"))  # « Local commercial Paris 5E »
        ville = re.sub(r"^local\s+commercial\s+", "", entete, flags=re.IGNORECASE).strip()
        prix = extraire_nombre(_texte(carte.select_one(".item-price")))
        surface = extraire_surface(_texte(carte.select_one(".item-tags")))
        description = _texte(carte.select_one(".item-description"))
        type_murs = deviner_type_murs(f"{entete} {description}")

        image = None
        img_el = carte.select_one(".item-thumb img")
        if img_el is not None:
            src = str(img_el.get("src", ""))
            if src and "visuel-nophoto" not in src:
                image = urljoin(self.BASE, src)

        return AnnonceBrute(
            id_source=ref.group(1),
            source=self.nom,
            url=urljoin(self.BASE, href),
            # Titre de la SOURCE, sans préfixe ajouté : le contrôle « suspect_fonds »
            # exige une mention des murs par l'annonceur lui-même.
            titre=entete,
            ville=ville,
            code_postal=self._code_postal(href, str(carte), ville),
            type_murs=type_murs,
            prix=prix,
            surface_m2=surface,
            loyer_mensuel=loyer_mensuel_depuis_texte(description, prix),
            image_url=image,
            description=description,
        )
