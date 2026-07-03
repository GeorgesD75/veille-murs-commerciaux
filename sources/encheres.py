"""encheres-publiques.com — ventes aux enchères de locaux commerciaux en IdF.

Canal SPÉCIAL, hors pipeline de scoring : une mise à prix n'est PAS un prix de
marché (souvent 25-50 % de la valeur, le prix final se fait aux enchères) —
la scorer serait trompeur, et nos garde-fous anti-pièges l'élimineraient.
Les lots à venir sont donc affichés dans une section dédiée du dashboard,
avec date de vente, mise à prix et lien, sans score.

Validation robots.txt (relevé du 2026-07-03) : `Allow: /`, seules les URLs à
paramètres sont interdites — la page de listing est propre. Le site rend son
état Next.js côté serveur (`__NEXT_DATA__`) : on lit ce JSON, plus stable que
le HTML. Une requête par run.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from pipeline.enrichissement import Benchmarks
from pipeline.geo import ILE_DE_FRANCE
from sources.extraction import extraire_surface
from sources.http import ClientPoli

_NEXT_DATA = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)
_LIEN_LOT = re.compile(
    r'href="(/encheres/immobilier/locaux-commerciaux/[a-z0-9-]+?-(\d{2,3})/[^"]*_(\d+))"'
)


class CollecteurEncheres:
    nom = "encheres_publiques"
    BASE = "https://www.encheres-publiques.com"
    LISTE = "/ventes/immobilier/locaux-commerciaux/ile-de-france"

    def __init__(self, client: ClientPoli | None = None, mise_a_prix_max: int = 420_000) -> None:
        self.client = client or ClientPoli()
        self.mise_a_prix_max = mise_a_prix_max
        self.avertissements: list[str] = []

    def collecter(self) -> list[dict[str, Any]]:
        html = self.client.obtenir(self.BASE + self.LISTE)
        return self.extraire(html)

    def extraire(self, html: str) -> list[dict[str, Any]]:
        brut = _NEXT_DATA.search(html)
        if not brut:
            raise ValueError("__NEXT_DATA__ introuvable : structure du site changée ?")
        data = json.loads(brut.group(1))["props"]["pageProps"]["apolloState"]["data"]

        # id du lot -> (chemin, département), depuis les liens rendus dans la page
        liens = {m.group(3): (m.group(1), m.group(2)) for m in _LIEN_LOT.finditer(html)}

        lots: list[dict[str, Any]] = []
        for cle, lot in data.items():
            if not cle.startswith("Lot:"):
                continue
            identifiant = str(lot.get("id", ""))
            mise_a_prix = lot.get("mise_a_prix")
            if not identifiant or not mise_a_prix:
                continue
            if lot.get("prix_adjuge") is not None:  # vente passée
                continue
            chemin, departement = liens.get(identifiant, ("", ""))
            if departement not in ILE_DE_FRANCE:
                continue
            if mise_a_prix > self.mise_a_prix_max:
                continue

            ref_adresse = (lot.get("adresse_defaut") or {}).get("__ref", "")
            adresse = data.get(ref_adresse, {}) if ref_adresse else {}
            ville = adresse.get("ville") or adresse.get("commune") or ""

            nom = lot.get("nom", "") or "Local commercial aux enchères"
            criteres = lot.get("criteres_resume", "") or ""
            surface = extraire_surface(nom) or extraire_surface(criteres)
            date_vente = ""
            if lot.get("ouverture_date"):
                date_vente = datetime.fromtimestamp(
                    lot["ouverture_date"], tz=timezone.utc
                ).date().isoformat()

            photo = lot.get("photo") or ""
            lots.append(
                {
                    "id": identifiant,
                    "titre": nom,
                    "url": self.BASE + chemin if chemin else self.BASE + self.LISTE,
                    "ville": ville,
                    "departement": departement,
                    "date_vente": date_vente,
                    "type_vente": lot.get("type", ""),
                    "mise_a_prix": mise_a_prix,
                    "estimation_basse": lot.get("estimation_basse"),
                    "estimation_haute": lot.get("estimation_haute"),
                    "surface_m2": surface,
                    "prix_m2_mise_a_prix": (
                        round(mise_a_prix / surface) if surface else None
                    ),
                    "criteres": criteres,
                    "image_url": self.BASE + photo if photo.startswith("/") else (photo or None),
                }
            )
        lots.sort(key=lambda lot: lot["date_vente"] or "9999")
        return lots


def enrichir_lots(lots: list[dict[str, Any]], benchmarks: Benchmarks) -> list[dict[str, Any]]:
    """Ajoute la comparaison au marché et un « prix max conseillé » à chaque lot.

    On ne SCORE pas une enchère (la mise à prix n'est pas un prix), mais on
    peut dire : « au-dessus de X €, ce n'est plus une affaire » — X étant la
    valeur basse du marché local (fourchette basse du benchmark × surface).
    Le niveau d'opportunité compare la mise à prix à cette valeur basse.
    """
    for lot in lots:
        bench = benchmarks.pour("", lot.get("departement", ""))
        surface = lot.get("surface_m2")
        if bench is None or not surface:
            lot["opportunite"] = "inconnue"
            continue
        valeur_basse = bench.prix_m2_bas * surface
        lot["marche_prix_m2_bas"] = bench.prix_m2_bas
        lot["marche_prix_m2_haut"] = bench.prix_m2_haut
        lot["prix_max_conseille"] = round(valeur_basse)
        ratio = lot["mise_a_prix"] / valeur_basse
        lot["opportunite"] = "forte" if ratio <= 0.5 else ("reelle" if ratio <= 1 else "faible")
    return lots
