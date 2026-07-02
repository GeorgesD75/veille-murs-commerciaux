"""Interface commune à toutes les sources d'annonces."""
from __future__ import annotations

from abc import ABC, abstractmethod

from pipeline.modeles import AnnonceBrute


class Source(ABC):
    """Une source = un module qui rend des AnnonceBrute ; le pipeline fait le reste.

    Une source a le droit de lever une exception : le run la logue, la note en
    erreur dans le rapport de santé et continue avec les autres sources.
    """

    nom: str = "source"

    @abstractmethod
    def collecter(self) -> list[AnnonceBrute]:
        """Récupère les annonces courantes de la source."""
