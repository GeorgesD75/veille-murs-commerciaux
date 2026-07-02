"""murscommerciaux.com (Coysevox) — rubriques dédiées murs occupés / murs libres.

Validation robots.txt (relevé du 2026-07-02) : `Allow: /` avec Crawl-delay 1
(notre client applique 3-5 s). La pagination `?p=` est interdite
(`Disallow: /?*p=*`) : on ne lit donc que la première page de chaque rubrique,
qui affiche les annonces les plus récentes (id décroissant) — suffisant pour
une veille quotidienne.

Bonus de cette source : la rentabilité est affichée sur la carte, et le loyer
annuel figure souvent dans la description.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup
from bs4.element import Tag

from pipeline.modeles import AnnonceBrute, TypeMurs
from pipeline.texte import normaliser_texte
from sources.base import SourceHtml
from sources.extraction import (
    extraire_nombre,
    loyer_mensuel_depuis_texte,
    rentabilite_depuis_texte,
)

_LOCALISATION = re.compile(r"^\s*([A-ZÉÈÊÀÂÎÏÔÛÜÇŒ'’ .-]+?)\s*\((\d{2,3})\)")


def _texte(element: Tag | None) -> str:
    return element.get_text(" ", strip=True) if element else ""


class SourceMursCommerciaux(SourceHtml):
    nom = "murscommerciaux"
    BASE = "https://www.murscommerciaux.com"
    PAGES = [
        ("/recherche-murs-commerciaux-occupes", TypeMurs.MURS_OCCUPES),
        ("/recherche-murs-commerciaux-libres", TypeMurs.MURS_LIBRES),
    ]

    def collecter(self) -> list[AnnonceBrute]:
        return self.collecter_pages(self.PAGES, self.extraire)

    def extraire(self, html: str, type_murs: TypeMurs) -> list[AnnonceBrute]:
        soup = BeautifulSoup(html, "html.parser")
        annonces: list[AnnonceBrute] = []
        for carte in soup.select("a.cvs-annonce-item"):
            annonce = self._extraire_carte(carte, type_murs)
            if annonce is not None:
                annonces.append(annonce)
        return annonces

    def _extraire_carte(self, carte: Tag, type_murs: TypeMurs) -> AnnonceBrute | None:
        href = str(carte.get("href", ""))
        ref = re.search(r"/annonce/(\d+)/", href)
        if not ref:
            return None
        titre = _texte(carte.select_one(".cvs-annonce-titre"))
        description = _texte(carte.select_one(".cvs-annonce-description"))
        prix = extraire_nombre(_texte(carte.select_one(".cvs-annonce-price")))

        surface: float | None = None
        rentabilite: float | None = None
        for item in carte.select(".cvs-info-item"):
            libelle = normaliser_texte(_texte(item.select_one(".cvs-info-label")))
            valeur = _texte(item.select_one(".cvs-info-value"))
            if libelle == "surface":
                surface = extraire_nombre(valeur)
            elif libelle == "rentabilite":
                rentabilite = extraire_nombre(valeur)

        # Le loyer annuel de la description prime ; sinon on le déduit de la
        # rentabilité affichée par l'agence (donnée déclarée, pas une estimation).
        loyer = loyer_mensuel_depuis_texte(description, prix)
        if loyer is None and prix and rentabilite and 2.0 <= rentabilite <= 15.0:
            loyer = round(prix * rentabilite / 100 / 12, 2)

        # Localisation en tête de titre : « LEVALLOIS-PERRET (92) … » ou « PARIS (75) … ».
        # Sans CP précis, on synthétise « départerment + 000 » (suffisant pour le
        # filtre géographique ; le benchmark retombe sur le département).
        ville, code_postal = "", ""
        localisation = _LOCALISATION.match(titre)
        if localisation:
            ville = localisation.group(1).strip().title()
            code_postal = localisation.group(2)[:2].ljust(5, "0")

        image = carte.select_one(".cvs-annonce-image-container img")
        return AnnonceBrute(
            id_source=ref.group(1),
            source=self.nom,
            url=href,
            titre=titre,
            ville=ville,
            code_postal=code_postal,
            type_murs=type_murs,
            prix=prix,
            surface_m2=surface,
            loyer_mensuel=loyer,
            image_url=str(image.get("src")) if image and image.get("src") else None,
            description=description,
        )
