"""geolocaux.com — vente de locaux commerciaux, une page par département IdF.

Validation robots.txt (relevé du 2026-07-04) : contrairement à l'hypothèse de
départ (« portail bloqué »), le robots est permissif — seuls /api/, /ax/, le
cache de recherche, les flux et quelques pages outillées sont interdits. Les
listings /vente/local-commercial/<departement>/ sont rendus côté serveur
(cartes div.annonce) et listés dans leur sitemap. 8 requêtes par run
(1 par département IdF), espacées de 3-5 s comme partout.
"""
from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from bs4.element import Tag

from pipeline.modeles import AnnonceBrute
from sources.base import SourceHtml
from sources.extraction import (
    deviner_type_murs,
    extraire_nombre,
    extraire_surface,
    loyer_mensuel_depuis_texte,
)

_SLUGS = {
    "75": "paris-75", "92": "hauts-de-seine-92", "93": "seine-saint-denis-93",
    "94": "val-de-marne-94", "95": "val-d-oise-95", "78": "yvelines-78",
    "91": "essonne-91", "77": "seine-et-marne-77",
}
# les titres du site mélangent « Paris 5 », « Paris 17e », « Paris 1er »…
_PARIS_ARRONDISSEMENT = re.compile(
    r"\bparis\s*(\d{1,2})(?:\s*(?:er|[eè]me|e))?\b", re.IGNORECASE
)
_MOTS_TYPE = re.compile(
    r"^(vente|achat|location)\s+(boutique|local commercial|local|commerce|murs)\s*",
    re.IGNORECASE,
)


def _texte(element: Tag | None) -> str:
    return element.get_text(" ", strip=True) if element else ""


class SourceGeolocaux(SourceHtml):
    nom = "geolocaux"
    BASE = "https://www.geolocaux.com"

    def __init__(self, client=None, departements: list[str] | None = None) -> None:
        super().__init__(client)
        self.departements = departements or list(_SLUGS)

    def collecter(self) -> list[AnnonceBrute]:
        pages = [
            (f"/vente/local-commercial/{_SLUGS[d]}/", d)
            for d in self.departements if d in _SLUGS
        ]
        return self.collecter_pages(pages, self.extraire)

    def _localiser(self, titre: str, departement: str) -> tuple[str, str]:
        """(ville, code postal) — arrondissement parisien si présent, sinon
        la commune du titre avec un CP départemental approximatif."""
        arrondissement = _PARIS_ARRONDISSEMENT.search(titre)
        if arrondissement and departement == "75":
            n = int(arrondissement.group(1))
            if 1 <= n <= 20:
                return f"Paris {n}{'er' if n == 1 else 'e'}", f"750{n:02d}"
        reste = _MOTS_TYPE.sub("", titre)
        ville = reste.split(" - ")[0].split(",")[0].strip()
        return ville[:40], departement.ljust(5, "0")

    def extraire(self, html: str, departement: str) -> list[AnnonceBrute]:
        soup = BeautifulSoup(html, "html.parser")
        annonces: dict[str, AnnonceBrute] = {}
        for carte in soup.select("div.annonce"):
            annonce = self._extraire_carte(carte, departement)
            if annonce is not None:
                annonces.setdefault(annonce.id_source, annonce)
        return list(annonces.values())

    def _extraire_carte(self, carte: Tag, departement: str) -> AnnonceBrute | None:
        lien = carte.select_one("h3.title a")
        if lien is None:
            return None
        href = str(lien.get("href", ""))
        ref = re.search(r"-(\d+)\.html$", href)
        if not ref:
            return None
        titre = _texte(lien)
        description = _texte(carte.select_one(".accroche")).replace("Voir l'annonce", "").strip()
        prix = extraire_nombre(_texte(carte.select_one(".price .price_wrapper")))
        surface = extraire_surface(_texte(carte.select_one(".surface .surf")))

        images: list[str] = []
        for img in carte.select("img[src]"):
            src = str(img["src"]).replace("&amp;", "&")
            if "/photos/" in src and "default" not in src:
                absolue = urljoin(self.BASE, src)
                if absolue not in images:
                    images.append(absolue)

        ville, code_postal = self._localiser(titre, departement)
        return AnnonceBrute(
            id_source=ref.group(1),
            source=self.nom,
            url=urljoin(self.BASE, href),
            titre=titre,
            ville=ville,
            code_postal=code_postal,
            type_murs=deviner_type_murs(f"{titre} {description}"),
            prix=prix,
            surface_m2=surface,
            loyer_mensuel=loyer_mensuel_depuis_texte(description, prix),
            image_url=images[0] if images else None,
            images=images,
            description=description[:600],
        )
