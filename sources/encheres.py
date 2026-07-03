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

            nom = lot.get("nom", "") or "Local commercial aux enchères"
            criteres = lot.get("criteres_resume", "") or ""
            surface = extraire_surface(nom) or extraire_surface(criteres)
            date_vente = ""
            if lot.get("ouverture_date"):
                date_vente = datetime.fromtimestamp(
                    lot["ouverture_date"], tz=timezone.utc
                ).date().isoformat()

            lots.append(
                {
                    "id": identifiant,
                    "titre": nom,
                    "url": self.BASE + chemin if chemin else self.BASE + self.LISTE,
                    "departement": departement,
                    "date_vente": date_vente,
                    "type_vente": lot.get("type", ""),
                    "mise_a_prix": mise_a_prix,
                    "surface_m2": surface,
                    "prix_m2_mise_a_prix": (
                        round(mise_a_prix / surface) if surface else None
                    ),
                    "criteres": criteres,
                }
            )
        lots.sort(key=lambda lot: lot["date_vente"] or "9999")
        return lots
