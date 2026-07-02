"""Dédoublonnage : même (source, id) via l'identifiant, et cross-sources par similarité."""
from __future__ import annotations

from collections.abc import Iterable

from pipeline.config import Config
from pipeline.modeles import Annonce


def sont_similaires(a: Annonce, b: Annonce, config: Config) -> bool:
    """Même bien probable : même code postal, surface ±3 m², prix ±5 % (config)."""
    d = config.deduplication
    if not a.code_postal or a.code_postal != b.code_postal:
        return False
    if a.surface_m2 is None or b.surface_m2 is None:
        return False
    if abs(a.surface_m2 - b.surface_m2) > d["tolerance_surface_m2"]:
        return False
    if a.prix is None or b.prix is None:
        return False
    tolerance = d["tolerance_prix_pct"] / 100 * max(a.prix, b.prix)
    return abs(a.prix - b.prix) <= tolerance


def trouver_similaire(
    annonce: Annonce, existantes: Iterable[Annonce], config: Config
) -> Annonce | None:
    """Cherche un doublon cross-sources parmi les annonces déjà connues."""
    for existante in existantes:
        if existante.id == annonce.id or existante.source == annonce.source:
            continue
        if sont_similaires(annonce, existante, config):
            return existante
    return None


def fusionner(principale: Annonce, doublon: Annonce) -> Annonce:
    """Garde une seule fiche : ajoute le lien du doublon et comble les trous."""
    liens_connus = [principale.url, *principale.urls_multiples]
    if doublon.url and doublon.url not in liens_connus:
        principale.urls_multiples.append(doublon.url)
    if principale.loyer_mensuel is None:
        principale.loyer_mensuel = doublon.loyer_mensuel
    if principale.image_url is None:
        principale.image_url = doublon.image_url
    if len(doublon.description) > len(principale.description):
        principale.description = doublon.description
    principale.date_premiere_vue = min(principale.date_premiere_vue, doublon.date_premiere_vue)
    principale.date_derniere_vue = max(principale.date_derniere_vue, doublon.date_derniere_vue)
    return principale
