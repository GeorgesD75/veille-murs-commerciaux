"""Point de Vente : deux rubriques publiques, murs libres et murs occupés.

Vérifiées le 27/10/2026 : lf9/lf10 listent les murs, contrairement à lf393
qui mélange les transactions. Pagination par les liens Suivant réels, 50
résultats par page ; libellé de CHAQUE carte vérifié. /produit.list, vues
grille et tailles 10/20/30/40 sont interdites par robots et jamais utilisées.
"""
from __future__ import annotations

import re
from urllib.parse import urljoin

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
    LISTES = [
        ("/fr/murs-de-boutique-libres/murs-de-boutique/lf9", "libres"),
        ("/fr/murs-de-boutique-occupes/murs-de-boutique/lf10", "occupes"),
    ]

    def __init__(self, client=None, max_pages: int = 12) -> None:
        super().__init__(client)
        self.max_pages = max_pages

    def collecter(self) -> list[AnnonceBrute]:
        # Rubriques publiques liées dans la navigation du site. Le moteur
        # /produit.list est interdit par robots.txt et n'est jamais interrogé.
        annonces = {}
        rapport = {"pages_lues":0,"annonces_uniques":0,"categories":{}}
        for chemin, categorie in self.LISTES:
            try:
                lot = self.collecter_pagination(chemin,self.extraire,self.max_pages)
            except Exception:
                if not annonces:
                    raise
                break
            rapport["categories"][categorie] = dict(self.rapport_collecte)
            rapport["pages_lues"] += self.rapport_collecte["pages_lues"]
            for a in lot:
                annonces.setdefault(a.id_source,a)
        rapport["annonces_uniques"] = len(annonces)
        self.rapport_collecte = rapport
        return list(annonces.values())

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
            url=urljoin(self.BASE, href),
            titre=titre,
            ville=ville,
            code_postal=code_postal,
            type_murs=type_murs,
            nature_transaction_source="murs",  # libellé MURS LIBRES/OCCUPÉS de cette carte
            prix=extraire_nombre(_texte(carte.select_one(".text-price .pull-left"))),
            surface_m2=surface,
            loyer_mensuel=loyer,
            image_url=image,
            description=" · ".join(etiquettes),
        )
