"""arthur-loyd.com — réseau national spécialisé immobilier d'entreprise,
rubrique dédiée « locaux commerciaux » (distincte de bureaux/entrepôts).

Validation robots.txt (relevé le 2026-08-23) : seuls des PARAMÈTRES de requête
sont interdits (`?type=`, `?bien=`, `?surface_min=`…) ; le chemin utilisé ici
est 100 % dans le PATH (`/locaux-commerciaux-vente/ile-de-france`), sans aucun
paramètre — non concerné par ces règles.

Limite connue et acceptée : la page liste l'Île-de-France entière en une seule
requête (~28 offres constatées le 2026-08-23), mais n'en affiche que les 18
premières côté serveur — le reste est chargé par un widget carte (Symfony UX
Live Component, protocole signé par checksum, non rejouable simplement en
requête HTTP classique). Tenté : pagination `?page=N`/`/page/N` (ignorée,
renvoie la page 1) et filtrage par département (`/ile-de-france/{dept}`,
comportement incohérent — certains slugs filtrent vraiment, d'autres
retombent silencieusement sur les 28 offres complètes sans erreur, aucun
moyen fiable de les distinguer sans casser l'un ou l'autre cas). Le tri par
défaut de la page est cependant « Nouveautés » (le plus récent en premier) :
pour une veille qui tourne 3×/jour, les nouvelles annonces sont justement
celles qui restent dans ces 18 premières — la limite pénalise surtout les
annonces plus anciennes déjà vues lors d'une tournée précédente.
"""
from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from bs4.element import Tag

from pipeline.modeles import AnnonceBrute
from sources.base import SourceHtml
from sources.extraction import deviner_type_murs, extraire_nombre, extraire_surface

_ADRESSE = re.compile(r"^(?P<ville>.+?)\s+(?P<cp>\d{5})$")


def _texte(element: Tag | None) -> str:
    return element.get_text(" ", strip=True) if element else ""


class SourceArthurLoyd(SourceHtml):
    nom = "arthurloyd"
    BASE = "https://www.arthur-loyd.com"
    LISTE = "/locaux-commerciaux-vente/ile-de-france"

    def collecter(self) -> list[AnnonceBrute]:
        return self.collecter_pages([(self.LISTE, None)], lambda html, _ctx: self.extraire(html))

    def extraire(self, html: str) -> list[AnnonceBrute]:
        soup = BeautifulSoup(html, "html.parser")
        annonces: dict[str, AnnonceBrute] = {}
        for carte in soup.select("a.offer-card"):
            annonce = self._extraire_carte(carte)
            if annonce is not None:
                annonces.setdefault(annonce.id_source, annonce)
        return list(annonces.values())

    def _extraire_carte(self, carte: Tag) -> AnnonceBrute | None:
        id_source = carte.get("data-id")
        href = carte.get("href")
        if not id_source or not href:
            return None

        adresse = _texte(carte.select_one(".offer-card__content-address"))
        ref = _ADRESSE.match(adresse)
        ville = ref.group("ville").title() if ref else adresse.title()
        code_postal = ref.group("cp") if ref else ""

        titre = _texte(carte.select_one(".offer-card__content-title")) or f"Local commercial {ville}"
        surface_texte = _texte(carte.select_one(".offer-card__content-surface"))
        prix_texte = _texte(carte.select_one(".offer-card__content-price"))

        image = None
        img_el = carte.select_one(".offer-bg__img")
        if img_el is not None:
            src = img_el.get("src")
            if src:
                image = urljoin(self.BASE, str(src))

        return AnnonceBrute(
            id_source=str(id_source),
            source=self.nom,
            url=urljoin(self.BASE, str(href)),
            titre=titre,
            ville=ville,
            code_postal=code_postal,
            type_murs=deviner_type_murs(titre),
            prix=extraire_nombre(prix_texte),
            surface_m2=extraire_surface(surface_texte) or extraire_nombre(surface_texte),
            loyer_mensuel=None,
            image_url=image,
            description="",
        )
