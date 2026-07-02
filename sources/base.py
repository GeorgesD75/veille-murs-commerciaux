"""Interfaces communes à toutes les sources d'annonces."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable
from typing import Any

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
                lot = extraire(html, contexte)
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
