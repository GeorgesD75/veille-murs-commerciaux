"""bienici.com — via son point d'accès JSON public (celui du site lui-même).

Validation robots.txt (relevé du 2026-07-03) : les interdictions visent des
motifs de pages de recherche (`?mode=`, `tri=`, virgules…) ; `/realEstateAds.json`
n'est pas interdit. Une seule requête par run, triée « publication récente »,
côté serveur : type boutique (« shop »), achat, prix plafonné au budget.

Le champ `adType` distingue la vente des murs (« buy ») de la cession de fonds
de commerce (« businessTakeOver ») : ces dernières sont écartées à la source.
"""
from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote

from bs4 import BeautifulSoup

from pipeline.modeles import AnnonceBrute
from sources.base import SourceHtml
from sources.extraction import deviner_type_murs, loyer_mensuel_depuis_texte


def _texte_description(description_html: str) -> str:
    return BeautifulSoup(description_html or "", "html.parser").get_text(" ", strip=True)


def _premiere_photo(annonce: dict[str, Any]) -> str | None:
    photos = annonce.get("photos") or []
    if not photos:
        return None
    premiere = photos[0]
    if isinstance(premiere, str):
        return premiere
    return premiere.get("url_photo") or premiere.get("url")


class SourceBienici(SourceHtml):
    nom = "bienici"
    BASE = "https://www.bienici.com"

    def __init__(self, client=None, max_annonces: int = 100, prix_max: int = 420_000) -> None:
        super().__init__(client)
        self.max_annonces = max_annonces
        self.prix_max = prix_max

    def _url(self) -> str:
        filtres = {
            "size": self.max_annonces,
            "from": 0,
            "filterType": "buy",
            "propertyType": ["shop"],
            "maxPrice": self.prix_max,
            "page": 1,
            "sortBy": "publicationDate",
            "sortOrder": "desc",
            "onTheMarket": [True],
        }
        return "/realEstateAds.json?filters=" + quote(
            json.dumps(filtres, separators=(",", ":"))
        )

    def collecter(self) -> list[AnnonceBrute]:
        return self.collecter_pages(
            [(self._url(), None)],
            lambda contenu, _ctx: self.convertir(json.loads(contenu)),
        )

    def convertir(self, donnees: dict[str, Any]) -> list[AnnonceBrute]:
        annonces: list[AnnonceBrute] = []
        for a in donnees.get("realEstateAds", []):
            if a.get("adType") != "buy":  # cessions de fonds : hors sujet
                continue
            identifiant = str(a.get("id", "")).strip()
            if not identifiant:
                continue
            description = _texte_description(a.get("description", ""))
            titre_source = a.get("title") or "Local commercial"
            type_murs = deviner_type_murs(f"{titre_source} {description}")
            prix = a.get("price")
            annonces.append(
                AnnonceBrute(
                    id_source=identifiant,
                    source=self.nom,
                    url=f"{self.BASE}/annonce/{identifiant}",
                    # Titre de la SOURCE, sans préfixe : le contrôle « suspect_fonds »
                    # exige une mention des murs par l'annonceur lui-même.
                    titre=titre_source,
                    ville=a.get("city", "") or "",
                    code_postal=str(a.get("postalCode", "") or ""),
                    type_murs=type_murs,
                    prix=float(prix) if prix is not None else None,
                    surface_m2=a.get("surfaceArea"),
                    loyer_mensuel=loyer_mensuel_depuis_texte(description, prix),
                    image_url=_premiere_photo(a),
                    description=description[:600],
                )
            )
        return annonces
