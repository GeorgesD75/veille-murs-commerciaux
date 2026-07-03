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
from datetime import date, datetime, timezone
from typing import Any

from pipeline.config import Config
from pipeline.enrichissement import Benchmarks
from pipeline.geo import ILE_DE_FRANCE, Trajets, categorie_emplacement
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


def scorer_lots(
    lots: list[dict[str, Any]],
    benchmarks: Benchmarks,
    trajets: Trajets,
    config: Config,
    maintenant: date | None = None,
) -> list[dict[str, Any]]:
    """Score d'INTÉRÊT /100 adapté aux enchères — sans prédire le prix final.

    Le prix d'adjudication est imprévisible (1× à 6× la mise à prix selon la
    salle) : toute « marge probable » serait une supposition. On note donc ce
    qui est CONNAISSABLE avant la vente :
    - emplacement /30 (même grille que les annonces, ×1,2) ;
    - gabarit vs budget /25 : la valeur de marché MÉDIANE du bien tient-elle
      dans le budget ? Si elle le dépasse largement, la salle vous doublera
      ou vous surpaierez — ce bien n'est pas pour vous ;
    - lisibilité du dossier /20 : surface 8, estimation du commissaire 6,
      ville identifiée 6 — un dossier opaque se rate ;
    - trajet depuis Paris 18e /10 ;
    - temps de préparation /15 : ≥ 10 jours avant la vente (avocat, visite,
      financement) 15, ≥ 5 jours 8, moins 3.

    Règle d'or ajoutée : une mise à prix DÉJÀ au-dessus du plafond de raison
    (valeur basse du marché) ne peut jamais devenir une affaire — le lot est
    écarté d'office (retourné en compteur, pas en liste).

    Seules les `max_haut_panier` meilleures ≥ `seuil_occasion` montent en haut
    de page. Retourne (lots gardés, nb écartés départ trop haut).
    """
    maintenant = maintenant or date.today()
    cfg = config["encheres"]
    budget = config.budget
    communes_dynamiques = config.scoring["communes_dynamiques"]
    bareme_emplacement = config.scoring["emplacement"]

    gardes: list[dict[str, Any]] = []
    nb_ecartes = 0
    for lot in lots:
        departement = lot.get("departement", "")
        surface = lot.get("surface_m2")
        bench = benchmarks.pour("", departement)
        detail: dict[str, float] = {}

        valeur_basse = valeur_mediane = None
        if bench is not None and surface:
            valeur_basse = bench.prix_m2_bas * surface
            valeur_mediane = bench.prix_m2_median * surface
            lot["valeur_marche_basse"] = round(valeur_basse)
            lot["valeur_marche_haute"] = round(bench.prix_m2_haut * surface)
            lot["prix_max_conseille"] = lot["valeur_marche_basse"]
            lot["marche_prix_m2_bas"] = bench.prix_m2_bas
            lot["marche_prix_m2_haut"] = bench.prix_m2_haut
            if lot["mise_a_prix"] > valeur_basse:
                # Départ déjà au-dessus du plafond de raison : jamais une affaire.
                nb_ecartes += 1
                continue

        categorie = categorie_emplacement(
            lot.get("ville", ""), departement,
            f"{lot.get('titre', '')} {lot.get('criteres', '')}", communes_dynamiques,
        )
        detail["emplacement"] = round(float(bareme_emplacement[categorie]) * 1.2, 1)

        if valeur_mediane is None:
            detail["gabarit"] = 0.0
        elif valeur_mediane <= budget["prix_max"]:
            detail["gabarit"] = 20.0
        elif valeur_mediane <= budget["prix_max"] * 1.35:
            detail["gabarit"] = 10.0  # jouable si la salle est calme
        else:
            detail["gabarit"] = 0.0

        if valeur_basse is None:
            detail["depart"] = 0.0
        else:
            # Marge AU DÉPART : plus la mise à prix part loin sous le plafond,
            # plus il reste d'espace pour enchérir en restant une affaire.
            espace = (valeur_basse - lot["mise_a_prix"]) / valeur_basse
            detail["depart"] = round(min(1.0, espace / 0.60) * 15, 1)

        detail["dossier"] = (
            (6.0 if surface else 0.0)
            + (5.0 if lot.get("estimation_basse") else 0.0)
            + (4.0 if lot.get("ville") else 0.0)
        )

        temps = trajets.temps_depuis_paris18(lot.get("ville", ""), departement)
        if temps is None or temps > 60:
            detail["proximite"] = 0.0
        elif temps < 20:
            detail["proximite"] = 10.0
        elif temps <= 40:
            detail["proximite"] = 6.0
        else:
            detail["proximite"] = 3.0

        if not lot.get("date_vente"):
            detail["preparation"] = 4.0
        else:
            jours = (date.fromisoformat(lot["date_vente"]) - maintenant).days
            detail["preparation"] = 10.0 if jours >= 10 else (5.0 if jours >= 5 else 2.0)

        lot["detail_score"] = detail
        lot["score_enchere"] = int(round(min(100.0, sum(detail.values()))))
        score = lot["score_enchere"]
        lot["opportunite"] = (
            "forte" if score >= cfg["seuil_occasion"]
            else ("reelle" if score >= 50 else "faible")
        )
        gardes.append(lot)

    gardes.sort(key=lambda lot: (-(lot.get("score_enchere") or 0), lot.get("date_vente") or "9999"))
    for rang, lot in enumerate(gardes):
        lot["haut_panier"] = (
            rang < cfg["max_haut_panier"]
            and (lot.get("score_enchere") or 0) >= cfg["seuil_occasion"]
        )
    return gardes, nb_ecartes
