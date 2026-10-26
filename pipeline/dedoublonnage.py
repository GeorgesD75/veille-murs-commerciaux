"""Dédoublonnage : même (source, id) via l'identifiant, et cross-sources par similarité."""
from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import urlsplit
from pipeline.texte import normaliser_texte

from pipeline.config import Config
from pipeline.modeles import Annonce
from pipeline.transaction import qualifier_transaction


def sont_similaires(a: Annonce, b: Annonce, config: Config) -> bool:
    """Même bien probable : même code postal, surface ±3 m², prix ±5 % (config)."""
    d = config.deduplication
    natures = {qualifier_transaction(a)["nature"], qualifier_transaction(b)["nature"]}
    if "murs" in natures and natures.intersection({"fonds", "bail", "mixte", "location"}):
        return False
    if "murs" in natures and "a_confirmer" in natures:
        liens_a = {a.url, *a.urls_multiples}
        liens_b = {b.url, *b.urls_multiples}
        if not (liens_a & liens_b):
            return False  # même photo/local ne prouve pas qu'on vende le même droit
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
        if sont_similaires(annonce, existante, config) and identite_corroboree(annonce, existante):
            return existante
    return None


def identite_corroboree(a: Annonce, b: Annonce) -> bool:
    """Même prix/surface/CP ne suffit pas à fusionner deux boutiques distinctes."""
    def cle(url):
        u = urlsplit(url)
        return u.netloc.lower().removeprefix("www."), u.path.rstrip("/")
    liens_a = {cle(u) for u in [a.url, *a.urls_multiples] if u}
    liens_b = {cle(u) for u in [b.url, *b.urls_multiples] if u}
    if liens_a & liens_b:
        return True
    images_a = {cle(u) for u in [a.image_url, *a.images] if u and not any(m in u.lower() for m in ["logo", "placeholder", "default"])}
    images_b = {cle(u) for u in [b.image_url, *b.images] if u and not any(m in u.lower() for m in ["logo", "placeholder", "default"])}
    if images_a & images_b:
        return True
    mots_a = set(normaliser_texte(a.description).split())
    mots_b = set(normaliser_texte(b.description).split())
    return len(mots_a) >= 30 and len(mots_b) >= 30 and len(mots_a & mots_b) / len(mots_a | mots_b) >= .85


def fusionner(principale: Annonce, doublon: Annonce) -> Annonce:
    """Garde une seule fiche : ajoute le lien du doublon et comble les trous."""
    liens_connus = [principale.url, *principale.urls_multiples]
    if doublon.url and doublon.url not in liens_connus:
        principale.urls_multiples.append(doublon.url)
    if principale.loyer_mensuel is None:
        principale.loyer_mensuel = doublon.loyer_mensuel
        principale.loyer_origine = doublon.loyer_origine
        principale.loyer_estime = doublon.loyer_estime
    if principale.image_url is None:
        principale.image_url = doublon.image_url
    for image in doublon.images:
        if image not in principale.images:
            principale.images.append(image)
    if len(doublon.description) > len(principale.description):
        principale.description = doublon.description
    principale.date_premiere_vue = min(principale.date_premiere_vue, doublon.date_premiere_vue)
    principale.date_derniere_vue = max(principale.date_derniere_vue, doublon.date_derniere_vue)
    for champ, preuves in doublon.preuves.items():
        entrees = principale.preuves.setdefault(champ, [])
        for preuve in preuves:
            if preuve not in entrees:
                entrees.append(preuve)
        del entrees[:-4]
    return principale
