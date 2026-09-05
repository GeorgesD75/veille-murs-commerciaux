"""cessionpme.com — listing « vente de locaux commerciaux / boutiques » déjà
filtré Île-de-France (1 000+ annonces, cartes rendues côté serveur).

Validation robots.txt (relevé du 2026-07-03, revérifié le 2026-08-15 après la
refonte ci-dessous) : `Allow: /` ; seuls quelques paramètres de requête sont
interdits (`bounds=`, `tribarre=`, `moteur=OUI`…), nous n'en utilisons aucun.
Une requête par run sur le listing de base.

Refonte du site constatée le 2026-08-15 (source tombée à 0 annonce plusieurs
jours de suite, cf. alerte de santé) : les cartes `a.offer-card` sont devenues
des `article.annonce-card` contenant un lien `a.annonce-card__link` distinct,
et l'URL de ce lien encode DIRECTEMENT ville + code postal en fin de slug
(« …-boutique-paris-11e-75011,9900001,A,offre.html ») — bien plus fiable que
l'ancien attribut `title="… à VILLE"`, qui a disparu du nouveau balisage.

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
from sources.base import SourceHtml
from sources.extraction import (
    LIMITE_DESCRIPTION,
    deviner_type_murs,
    extraire_nombre,
    extraire_surface,
    loyer_mensuel_depuis_texte,
)

# « …boutique-{ville-slug}-{cp},{id},{lettre},offre.html » — le verbe (achat,
# vente, acheter…) varie selon l'annonce, jamais le reste du gabarit.
_HREF = re.compile(
    r"^/annonce,immo-entreprise-[a-z]+-local-commercial-boutique-"
    r"(?P<ville>[a-z0-9-]+?)-(?P<cp>\d{5}),(?P<id>\d+),[A-Z],offre\.html$"
)
_PETITS_MOTS = {"de", "du", "des", "le", "la", "les", "sur", "sous", "en", "aux", "et"}


def _ville_depuis_slug(slug: str) -> str:
    """'le-pre-saint-gervais' -> 'Le Pre Saint Gervais' ; 'paris-11e' -> 'Paris 11e'."""
    mots: list[str] = []
    for mot in slug.split("-"):
        if re.fullmatch(r"\d{1,2}e", mot):
            mots.append(mot)  # arrondissement : "11e", jamais "11E"
        elif mot in _PETITS_MOTS and mots:
            mots.append(mot)
        else:
            mots.append(mot.capitalize())
    return " ".join(mots)


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
        for carte in soup.select("article.annonce-card"):
            annonce = self._extraire_carte(carte)
            if annonce is not None:
                # la carte « à la une » peut réapparaître dans la liste
                annonces.setdefault(annonce.id_source, annonce)
        return list(annonces.values())

    def _extraire_carte(self, carte: Tag) -> AnnonceBrute | None:
        lien = carte.select_one("a.annonce-card__link")
        href = str(lien.get("href", "")) if lien is not None else ""
        ref = _HREF.match(href)
        if not ref:
            return None

        titre_source = _texte(carte.select_one(".annonce-card__title"))
        description = _texte(carte.select_one(".annonce-card__description"))

        prix = extraire_nombre(_texte(carte.select_one(".annonce-card__price__value")))
        surface = None
        for item in carte.select(".annonce-card__highlights__item"):
            libelle = _texte(item.select_one(".annonce-card__highlights__label")).lower()
            if libelle == "surface":
                surface = extraire_nombre(_texte(item.select_one(".annonce-card__highlights__value")))
        if surface is None:
            surface = extraire_surface(description)

        ville = _ville_depuis_slug(ref.group("ville"))
        type_murs = deviner_type_murs(f"{titre_source} {description}")

        image = None
        img_el = carte.select_one("header img")
        if img_el is not None:
            src = img_el.get("src") or img_el.get("data-src")
            if src and str(src).startswith(("http", "/")):
                image = urljoin(self.BASE, str(src))

        return AnnonceBrute(
            id_source=ref.group("id"),
            source=self.nom,
            url=urljoin(self.BASE, href),
            # Titre de la SOURCE, sans préfixe ajouté : le contrôle « suspect_fonds »
            # exige une mention des murs par l'annonceur lui-même.
            titre=titre_source or ville,
            ville=ville,
            code_postal=ref.group("cp"),
            type_murs=type_murs,
            prix=prix,
            surface_m2=surface,
            loyer_mensuel=loyer_mensuel_depuis_texte(description, prix),
            image_url=image,
            description=description[:LIMITE_DESCRIPTION],
        )
