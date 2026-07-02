"""Persistance JSON versionnée dans git : la mémoire du collecteur entre deux runs."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pipeline.modeles import Annonce


class Stockage:
    def __init__(self, chemin: Path) -> None:
        self.chemin = chemin

    def charger(self) -> tuple[dict[str, Annonce], dict[str, Any]]:
        """Retourne (annonces par id, méta du dernier run)."""
        if not self.chemin.exists():
            return {}, {}
        contenu = json.loads(self.chemin.read_text(encoding="utf-8"))
        annonces = {d["id"]: Annonce.from_dict(d) for d in contenu.get("annonces", [])}
        return annonces, contenu.get("meta", {})

    def sauvegarder(self, annonces: dict[str, Annonce], meta: dict[str, Any]) -> None:
        ordonnees = sorted(annonces.values(), key=lambda a: (a.score is None, -(a.score or 0)))
        contenu = {"meta": meta, "annonces": [a.to_dict() for a in ordonnees]}
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        self.chemin.write_text(
            json.dumps(contenu, ensure_ascii=False, indent=1), encoding="utf-8"
        )
