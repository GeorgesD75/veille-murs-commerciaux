"""iccinvest.com — cabinet indépendant spécialisé « murs de commerce »
(hôtels, commerces, restaurants), listing national ; on ne garde que l'IDF.

Validation robots.txt (relevé le 2026-08-16) : `Allow: /` sans restriction —
site WordPress (Yoast). Page listing `/annonces/` (custom post type
« annonce »), paginée `/annonces/page/{n}/`.

Le champ « département » affiché sur le site s'est montré occasionnellement
faux (une annonce à Mérignac (33) taguée « 32 », une autre en région Rhône-
Alpes taguée par son nom plutôt qu'un code) — on préfère donc un vrai code
postal trouvé dans le titre/la description quand il y est (fréquent pour les
annonces parisiennes : « … sis 75008 PARIS »), et on ne retombe sur le
département affiché qu'à défaut, comme repère grossier (le pipeline
recoupera de toute façon avec ses propres filtres IDF).

Le site affiche une « rentabilité » (%) plutôt qu'un loyer — le loyer mensuel
est donc déduit de prix × rentabilité, comme n'importe quel loyer ANNONCÉ
ailleurs : une donnée du vendeur, jamais vérifiée, mais du même niveau de
confiance que ce que les autres sources publient déjà.
"""
from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from bs4.element import Tag

from pipeline.modeles import AnnonceBrute
from sources.base import SourceHtml
from sources.extraction import LIMITE_DESCRIPTION, deviner_type_murs, extraire_nombre, extraire_surface

_CP = re.compile(r"\b(\d{5})\b")
_ID_POST = re.compile(r"post-(\d+)")


def _texte(element: Tag | None) -> str:
    return element.get_text(" ", strip=True) if element else ""


class SourceIccInvest(SourceHtml):
    nom = "iccinvest"
    BASE = "https://www.iccinvest.com"
    LISTE = "/annonces/"

    def __init__(self, client=None, max_pages: int = 5) -> None:
        super().__init__(client)
        self.max_pages = max_pages

    def collecter(self) -> list[AnnonceBrute]:
        pages = [
            (self.LISTE if n == 0 else f"{self.LISTE}page/{n + 1}/", None)
            for n in range(self.max_pages)
        ]
        return self.collecter_pages(pages, lambda html, _ctx: self.extraire(html))

    def extraire(self, html: str) -> list[AnnonceBrute]:
        soup = BeautifulSoup(html, "html.parser")
        annonces: dict[str, AnnonceBrute] = {}
        conteneur = soup.select_one(".liste_annonces") or soup
        for article in conteneur.find_all("article", recursive=False):
            annonce = self._extraire_carte(article)
            if annonce is not None:
                annonces.setdefault(annonce.id_source, annonce)
        return list(annonces.values())

    def _code_postal(self, titre: str, description: str, departement_brut: str) -> str:
        trouve = _CP.search(f"{titre} {description}")
        if trouve:
            return trouve.group(1)
        dept = departement_brut.strip()
        if re.fullmatch(r"\d{2}", dept):
            return f"{dept}000"  # repère de département, pas un vrai CP
        return ""

    def _extraire_carte(self, article: Tag) -> AnnonceBrute | None:
        id_trouve = _ID_POST.search(str(article.get("id", "")))
        if not id_trouve:
            return None

        lien = article.select_one("h2 a")
        if lien is None or not lien.get("href"):
            return None
        href = str(lien["href"])
        titre = _texte(lien)

        ville = _texte(article.select_one(".ville"))
        departement_brut = _texte(article.select_one(".departement"))
        description = _texte(article.select_one("p"))

        prix = extraire_nombre(_texte(article.select_one('li[title="Prix de vente"]')))

        loyer_mensuel = None
        rentabilite_txt = _texte(article.select_one('li[title="Rentabilité"]'))
        if rentabilite_txt and prix:
            pct = extraire_nombre(rentabilite_txt)
            if pct and 2.0 <= pct <= 15.0:
                loyer_mensuel = round(prix * pct / 100 / 12, 2)

        image = None
        img_el = article.select_one(".img img")
        if img_el is not None:
            src = img_el.get("src")
            if src and str(src).startswith(("http", "/")) and "default.jpg" not in str(src):
                image = urljoin(self.BASE, str(src))

        return AnnonceBrute(
            id_source=id_trouve.group(1),
            source=self.nom,
            url=urljoin(self.BASE, href),
            titre=titre or ville,
            ville=ville,
            code_postal=self._code_postal(titre, description, departement_brut),
            type_murs=deviner_type_murs(f"{titre} {description}"),
            prix=prix,
            surface_m2=extraire_surface(f"{titre} {description}"),
            loyer_mensuel=loyer_mensuel,
            image_url=image,
            description=description[:LIMITE_DESCRIPTION],
        )
