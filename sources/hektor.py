"""Parser partagé iburoshop.fr / flagship.fr — même plateforme d'agence.

Validation robots.txt (relevé du 2026-07-02, identique sur les deux domaines) :
seules les pages d'impression sont interdites. Les listings sont rendus côté
serveur (`article.blocAnnonce`, schema.org/Offer), triés « Nouveautés »
(id décroissant) : la première page suffit pour une veille quotidienne.

Les cartes de location et de cession de bail sont ignorées (URL sans
« vente »). La référence et le code postal sont dans l'URL du bien :
`/nos-biens/ref-uh1-5603/vente-commerce-paris-75018/`.
"""
from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from bs4.element import Tag

from pipeline.modeles import AnnonceBrute, TypeMurs
from sources.base import SourceHtml
from sources.extraction import (
    deviner_type_murs,
    extraire_nombre,
    extraire_surface,
    loyer_mensuel_depuis_texte,
    rentabilite_depuis_texte,
)

_LIBELLES = {
    TypeMurs.MURS_OCCUPES: "Murs occupés",
    TypeMurs.MURS_LIBRES: "Murs libres",
}


def _premiere_ligne(element: Tag | None) -> str:
    return next(element.stripped_strings, "") if element else ""


def _texte(element: Tag | None) -> str:
    return element.get_text(" ", strip=True) if element else ""


class SourceHektor(SourceHtml):
    """À sous-classer : définir nom, BASE et PAGES [(chemin, type ou None)]."""

    PAGES: list[tuple[str, TypeMurs | None]] = []

    def collecter(self) -> list[AnnonceBrute]:
        return self.collecter_pages(self.PAGES, self.extraire)

    def extraire(self, html: str, type_defaut: TypeMurs | None) -> list[AnnonceBrute]:
        soup = BeautifulSoup(html, "html.parser")
        annonces: list[AnnonceBrute] = []
        for carte in soup.select("article.blocAnnonce"):
            annonce = self._extraire_carte(carte, type_defaut)
            if annonce is not None:
                annonces.append(annonce)
        return annonces

    def _extraire_carte(
        self, carte: Tag, type_defaut: TypeMurs | None
    ) -> AnnonceBrute | None:
        lien = carte.select_one('a[href*="/ref-"]')
        if lien is None:
            return None
        href = str(lien.get("href", ""))
        if "vente" not in href:  # locations et cessions de bail : hors sujet
            return None
        ref = re.search(r"/ref-([a-z0-9-]+)/", href)
        if not ref:
            return None
        cp = re.search(r"-(\d{5})/?$", href)

        prix_texte = _texte(carte.select_one("p.prix"))
        prix_brut = re.search(r"prix[^0-9]*([\d\s  .,]+)", prix_texte, re.IGNORECASE)
        prix = extraire_nombre(prix_brut.group(1)) if prix_brut else None
        if prix is None:
            return None

        description = _texte(carte.select_one(".propertyDescription"))
        type_murs = type_defaut or deviner_type_murs(description)

        # Surface : dans l'attribut alt des photos (« … 75018 43 m² ») ou la description.
        image_el = carte.select_one("img[itemprop=image]")
        surface = None
        if image_el is not None:
            surface = extraire_surface(str(image_el.get("alt", "")))
        if surface is None:
            surface = extraire_surface(description)

        # Loyer : annuel dans la description, sinon déduit de la rentabilité déclarée.
        loyer = loyer_mensuel_depuis_texte(description, prix)
        if loyer is None:
            rentabilite = rentabilite_depuis_texte(description)
            if rentabilite:
                loyer = round(prix * rentabilite / 100 / 12, 2)

        ville = _premiere_ligne(carte.select_one("p.city")).title()
        quartier = _premiere_ligne(carte.select_one("p.quartier"))
        titre = f"{_LIBELLES[type_murs]} – {ville}" + (f" ({quartier})" if quartier else "")

        image = None
        if image_el is not None:
            src = image_el.get("src") or image_el.get("data-src")
            if src:
                image = urljoin(self.BASE, str(src))

        return AnnonceBrute(
            id_source=ref.group(1),
            source=self.nom,
            url=urljoin(self.BASE, href),
            titre=titre,
            ville=ville,
            code_postal=cp.group(1) if cp else "",
            type_murs=type_murs,
            prix=prix,
            surface_m2=surface,
            loyer_mensuel=loyer,
            image_url=image,
            description=description,
        )


class SourceIburoshop(SourceHektor):
    nom = "iburoshop"
    BASE = "https://www.iburoshop.fr"
    PAGES = [
        ("/vente-de-murs-occupes-paris-iburoshop/&new_research=1", TypeMurs.MURS_OCCUPES),
        ("/murs-a-vendre-libre-paris-iburoshop/&new_research=1", TypeMurs.MURS_LIBRES),
    ]


class SourceFlagship(SourceHektor):
    nom = "flagship"
    BASE = "https://www.flagship.fr"
    # Page mixte (ventes, locations, cessions) : le type est déduit du texte.
    PAGES = [("/murs-de-boutiques-paris/&new_research=1", None)]
