"""Transformation d'une AnnonceBrute (source) en Annonce normalisée (pipeline)."""
from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

from pipeline.modeles import Annonce, AnnonceBrute, identifiant

FUSEAU = ZoneInfo("Europe/Paris")


def maintenant_iso() -> str:
    return datetime.now(FUSEAU).isoformat(timespec="seconds")


def _nettoyer(texte: str) -> str:
    return " ".join((texte or "").split())


def _code_postal(brut: str) -> str:
    m = re.search(r"\b(\d{5})\b", brut or "")
    return m.group(1) if m else ""


def normaliser(brute: AnnonceBrute, quand: str | None = None) -> Annonce:
    quand = quand or maintenant_iso()
    cp = _code_postal(brute.code_postal)
    images: list[str] = []
    for image in [*(brute.images or []), brute.image_url]:
        if image and image not in images:
            images.append(image)
    return Annonce(
        id=identifiant(brute.source, brute.id_source),
        id_source=brute.id_source,
        source=brute.source,
        url=(brute.url or "").strip(),
        titre=_nettoyer(brute.titre),
        ville=_nettoyer(brute.ville),
        code_postal=cp,
        departement=cp[:2],
        type_murs=brute.type_murs,
        prix=brute.prix,
        surface_m2=brute.surface_m2,
        loyer_mensuel=brute.loyer_mensuel,
        honoraires=brute.honoraires,
        image_url=images[0] if images else None,
        images=images,
        description=_nettoyer(brute.description),
        date_premiere_vue=quand,
        date_derniere_vue=quand,
    )
