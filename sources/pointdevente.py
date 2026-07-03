"""pointdevente.fr — rubrique murs commerciaux (donnée en or : prix + loyer affichés).

Validation robots.txt (relevé du 2026-07-02) : le listing
`/fr/acheter-murs-commerciaux-paris/lf393` est explicitement autorisé
(`Allow: ...lf393$`) ; la pagination `/lf393/50/{page}/1` n'est pas dans les
motifs interdits (seuls les affichages 10/20/30/40 résultats et la vue grille
`.../2` le sont). Tri du site : plus récentes d'abord (`created_on.DESC`),
donc 2 pages de 50 suffisent largement pour une veille quotidienne.

La rubrique mélange plusieurs types (fonds de commerce, locations…) : seuls
MURS OCCUPÉS et MURS LIBRES sont retenus ici.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup
from bs4.element import Tag

from pipeline.modeles import AnnonceBrute, TypeMurs
from pipeline.texte import normaliser_texte
from sources.base import SourceHtml
from sources.extraction import extraire_nombre

_TYPES = {
    "murs occupes": TypeMurs.MURS_OCCUPES,
    "murs libres": TypeMurs.MURS_LIBRES,
}
_LIBELLES = {
    TypeMurs.MURS_OCCUPES: "Murs occupés",
    TypeMurs.MURS_LIBRES: "Murs libres",
}


def _texte(element: Tag | None) -> str:
    return element.get_text(" ", strip=True) if element else ""


class SourcePointDeVente(SourceHtml):
    nom = "pointdevente"
    BASE = "https://www.pointdevente.fr"
    LISTE = "/fr/acheter-murs-commerciaux-paris/lf393"

    def __init__(self, client=None, max_pages: int = 2) -> None:
        super().__init__(client)
        self.max_pages = max_pages

    def collecter(self) -> list[AnnonceBrute]:
        pages = [
            (self.LISTE if n == 0 else f"{self.LISTE}/50/{n}/1", None)
            for n in range(self.max_pages)
        ]
        return self.collecter_pages(pages, lambda html, _ctx: self.extraire(html))

    def extraire(self, html: str) -> list[AnnonceBrute]:
        soup = BeautifulSoup(html, "html.parser")
        annonces: dict[str, AnnonceBrute] = {}
        for carte in soup.select("a.card-default"):
            annonce = self._extraire_carte(carte)
            if annonce is not None:
                # La page duplique chaque carte (rendu mobile + bureau)
                annonces.setdefault(annonce.id_source, annonce)
        return list(annonces.values())

    def _extraire_carte(self, carte: Tag) -> AnnonceBrute | None:
        type_murs = _TYPES.get(normaliser_texte(_texte(carte.select_one(".block-type .type"))))
        if type_murs is None:  # fonds de commerce, cession, location : hors sujet
            return None
        href = str(carte.get("href", ""))
        ref = re.search(r"/p(\d+)/?$", href)
        if not ref:
            return None

        # Localisation : .code contient soit le CP, soit « Paris 18<sup>e</sup> »
        # (le CP est alors récupéré dans les URLs de photos, ..._75018_paris_...).
        # get_text sans séparateur pour recoller l'exposant : « Paris 18e ».
        code_el = carte.select_one(".block-type .code")
        code = code_el.get_text(strip=True) if code_el else ""
        ville = _texte(carte.select_one(".city"))
        if re.fullmatch(r"\d{5}", code):
            code_postal = code
        else:
            ville = ville or code
            cp = re.search(r"_(\d{5})_", str(carte))
            code_postal = cp.group(1) if cp else ""

        loyer: float | None = None
        surface: float | None = None
        for ligne in carte.select(".info-card > div"):
            texte = _texte(ligne)
            if texte.lower().startswith("loyer"):
                loyer = extraire_nombre(texte)  # affiché en €/mois HC
            elif "surface" in texte.lower():
                surface = extraire_nombre(texte)

        image = None
        bloc_image = carte.select_one(".img-card")
        if bloc_image is not None:
            fond = re.search(r"url\((.*?)\)", str(bloc_image.get("style", "")))
            if fond and "/doc/pdv/" in fond.group(1):  # ignore les pictos génériques
                image = fond.group(1)

        titre = f"{_LIBELLES[type_murs]} – {ville}"
        nom_bien = _texte(carte.select_one(".head-card .title"))
        if nom_bien:
            titre += f" – {nom_bien}"

        # Les pictos de la carte (« Restauration sans conduit possible »,
        # « Terrasse »…) disent ce qu'on peut FAIRE dans le local : capturés
        # comme description pour nourrir les étiquettes d'activité.
        etiquettes = [t.get_text(strip=True) for t in carte.select(".list-tag-produit .sr-only")]

        return AnnonceBrute(
            id_source=ref.group(1),
            source=self.nom,
            url=href,
            titre=titre,
            ville=ville,
            code_postal=code_postal,
            type_murs=type_murs,
            prix=extraire_nombre(_texte(carte.select_one(".text-price .pull-left"))),
            surface_m2=surface,
            loyer_mensuel=loyer,
            image_url=image,
            description=" · ".join(etiquettes),
        )
