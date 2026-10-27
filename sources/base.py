"""Interfaces communes à toutes les sources d'annonces."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable
from typing import Any
from urllib.parse import urljoin, urlsplit
import logging

from bs4 import BeautifulSoup

from pipeline.modeles import AnnonceBrute
from sources.http import ClientPoli, SourceBloqueeErreur


class Source(ABC):
    """Une source = un module qui rend des AnnonceBrute ; le pipeline fait le reste.

    Une source a le droit de lever une exception : le run la logue, la note en
    erreur dans le rapport de santé et continue avec les autres sources.
    Les problèmes non fatals (une page sur deux en échec…) vont dans
    `avertissements`, repris dans le rapport de santé.
    """

    nom: str = "source"

    def __init__(self) -> None:
        self.avertissements: list[str] = []
        self.rapport_collecte: dict[str, Any] = {}

    @abstractmethod
    def collecter(self) -> list[AnnonceBrute]:
        """Récupère les annonces courantes de la source."""


class SourceHtml(Source):
    """Base des sources Niveau 1 : scraping léger via le client poli."""

    BASE: str = ""

    def __init__(self, client: ClientPoli | None = None) -> None:
        super().__init__()
        self.client = client or ClientPoli()

    def collecter_pages(
        self,
        pages: Iterable[tuple[str, Any]],
        extraire: Callable[[str, Any], Iterable[AnnonceBrute]],
    ) -> list[AnnonceBrute]:
        """Boucle polie sur des pages (chemin, contexte) avec tolérance aux pannes.

        - blocage (robots, 403, 429) : on arrête TOUTES les pages restantes ;
        - autre erreur : on note un avertissement et on passe à la page suivante ;
        - si rien n'a pu être collecté, la première erreur est propagée.
        """
        annonces: dict[str, AnnonceBrute] = {}
        erreurs: list[Exception] = []
        for chemin, contexte in pages:
            try:
                html = self.client.obtenir(self.BASE + chemin)
                lot = list(extraire(html, contexte))
            except SourceBloqueeErreur as exc:
                erreurs.append(exc)
                self.avertissements.append(f"{chemin} : {exc}")
                break
            except Exception as exc:  # noqa: BLE001 — une page en échec ne bloque pas
                erreurs.append(exc)
                self.avertissements.append(f"{chemin} : {exc}")
                continue
            for annonce in lot:
                annonces.setdefault(annonce.id_source, annonce)
        if not annonces and erreurs:
            raise erreurs[0]
        return list(annonces.values())

    def collecter_pagination(self, premier: str, extraire, max_pages: int) -> list[AnnonceBrute]:
        """Suit les liens Suivant du site, avec dédoublonnage et arrêt sur boucle.

        Aucun lien externe ni changement d'origine n'est suivi. Les pages sans
        bien pertinent n'interrompent pas une pagination encore active.
        """
        annonces: dict[str, AnnonceBrute] = {}
        visites, signatures = set(), set()
        origine = urlsplit(self.BASE)
        url = urljoin(self.BASE, premier)
        limite = max(1, min(60, int(max_pages)))
        rapport = self.rapport_collecte = {"pages_lues": 0, "annonces_uniques": 0, "fin": "fin_listing"}
        while url and rapport["pages_lues"] < limite:
            cible = urlsplit(url)
            if (cible.scheme, cible.netloc) != (origine.scheme, origine.netloc) or url in visites:
                rapport["fin"] = "lien_invalide_ou_boucle"
                break
            visites.add(url)
            try:
                html = self.client.obtenir(url)
                lot = list(extraire(html))
            except Exception as exc:
                rapport["fin"] = "interrompue"
                self.avertissements.append(f"{url} : {exc}")
                if not annonces:
                    raise
                break
            rapport["pages_lues"] += 1
            logging.getLogger("collecteur.sources").info("%s : page %s, %s annonces reconnues",self.nom,rapport["pages_lues"],len(lot))
            signature = tuple(sorted(a.id_source for a in lot))
            if signature and signature in signatures:
                rapport["fin"] = "page_repetee"
                self.avertissements.append("Pagination répétée : arrêt avant de recompter les mêmes annonces.")
                break
            signatures.add(signature)
            for a in lot:
                annonces.setdefault(a.id_source, a)
            url = page_suivante(html, url)
        rapport["annonces_uniques"] = len(annonces)
        if url and rapport["pages_lues"] >= limite and rapport["fin"] == "fin_listing":
            rapport["fin"] = "limite_pages"
            self.avertissements.append(f"Limite de {limite} pages atteinte : d’autres résultats restent disponibles.")
        return list(annonces.values())


def page_suivante(html: str, url: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    liens = soup.select('a[rel~="next"], a.pagination-next, .pagination a, a.next, a.pagination__btn')
    for a in soup.select("a[href]"):
        if a.get_text(" ", strip=True).casefold() in {"suivante", "suivant"}:
            liens.append(a)
    for lien in liens:
        texte = lien.get_text(" ", strip=True).casefold()
        if "next" in lien.get("rel", []) or "pagination-next" in lien.get("class", []) or texte in {"suivante", "suivant", ">", "›"}:
            href = lien.get("href")
            if href and not str(href).startswith(("#", "javascript:")):
                return urljoin(url, str(href))
    return None
