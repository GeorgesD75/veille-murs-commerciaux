"""Ventes réelles de locaux commerciaux — DVF (data.gouv.fr), par commune.

« Demandes de valeurs foncières » : chaque vente immobilière enregistrée chez
le notaire, en open data. C'est la réponse à « le prix affiché est-il réel ? » :
au lieu de comparer une annonce à un référentiel interne rédigé à la main, on
la compare aux prix effectivement PAYÉS pour des locaux commerciaux de la même
commune (fichiers géo-DVF par commune, gratuits, sans clé).

Précautions qui font la fiabilité du chiffre :
- une mutation DVF peut couvrir plusieurs lots : la valeur foncière est celle
  de la mutation ENTIÈRE, répétée sur chaque ligne. On regroupe par mutation et
  on ne garde que celles composées uniquement de locaux commerciaux (les
  dépendances sont tolérées, une mutation mêlant appartements et boutique est
  écartée : impossible d'isoler le prix du local) ;
- filtres de vraisemblance (surface ≥ 8 m², prix ≥ 10 000 €, 200 à
  30 000 €/m²) : DVF contient des ventes symboliques et des erreurs de saisie ;
- un secteur n'est utilisé que s'il compte assez de ventes (config
  ventes_minimum) — une « médiane » sur 3 ventes n'en est pas une ;
- la fourchette affichée est P25-P75 (la moitié centrale des ventes), la
  comparaison se fait à la médiane.

Limites assumées, dites à l'utilisateur : DVF paraît avec ~6 mois de retard ;
les prix des années passées ne sont pas actualisés du marché courant ; un
local d'angle neuf et une arrière-boutique sombre sont dans le même panier.
C'est un garde-fou factuel, pas une expertise.

Cadence : fichiers mis à jour ~2 fois par an côté data.gouv — chaque commune
est rafraîchie au plus une fois par mois, quelques communes par tournée
(budget), le résultat vit dans data/dvf.json committé comme les autres caches.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import requests

from pipeline.normalisation import maintenant_iso
from sources.http import USER_AGENT

log = logging.getLogger("collecteur.dvf")

URL_COMMUNE = "https://files.data.gouv.fr/geo-dvf/latest/csv/{annee}/communes/{dep}/{insee}.csv"
URL_GEO_COMMUNES = "https://geo.api.gouv.fr/communes"
TYPE_LOCAL_COMMERCIAL = "Local industriel. commercial ou assimilé"

JOURS_FRAICHEUR_COMMUNE = 30   # géo-DVF n'est publié que ~2 fois par an
SURFACE_MIN_M2 = 8
PRIX_MIN = 10_000
PRIX_M2_MIN, PRIX_M2_MAX = 200, 30_000
DELAI_ENTRE_APPELS_S = 1.0


def _quantile(valeurs: list[float], q: float) -> float:
    """Quantile par interpolation linéaire (assez bon pour une fourchette)."""
    tri = sorted(valeurs)
    pos = (len(tri) - 1) * q
    bas = int(pos)
    if bas == len(tri) - 1:
        return tri[bas]
    return tri[bas] + (tri[bas + 1] - tri[bas]) * (pos - bas)


def extraire_prix_m2(texte_csv: str) -> list[float]:
    """Prix/m² des ventes de locaux commerciaux d'un fichier commune géo-DVF.

    Regroupe les lignes par mutation (la valeur foncière est celle de la
    mutation entière) et écarte toute mutation mélangeant le local avec de
    l'habitation — le prix de la boutique n'y est pas isolable.
    """
    mutations: dict[str, dict] = {}
    for ligne in csv.DictReader(io.StringIO(texte_csv)):
        if ligne.get("nature_mutation") != "Vente":
            continue
        m = mutations.setdefault(ligne["id_mutation"], {
            "valeur": None, "surface_commerciale": 0.0, "autre_habitable": False,
        })
        try:
            m["valeur"] = float(ligne["valeur_fonciere"])
        except (TypeError, ValueError):
            pass
        type_local = ligne.get("type_local") or ""
        if type_local == TYPE_LOCAL_COMMERCIAL:
            try:
                m["surface_commerciale"] += float(ligne["surface_reelle_bati"] or 0)
            except ValueError:
                pass
        elif type_local in ("Appartement", "Maison"):
            m["autre_habitable"] = True

    prix_m2 = []
    for m in mutations.values():
        if m["autre_habitable"] or not m["valeur"] or m["surface_commerciale"] < SURFACE_MIN_M2:
            continue
        if m["valeur"] < PRIX_MIN:
            continue
        p = m["valeur"] / m["surface_commerciale"]
        if PRIX_M2_MIN <= p <= PRIX_M2_MAX:
            prix_m2.append(round(p))
    return prix_m2


@dataclass(frozen=True)
class VentesSecteur:
    nb: int
    prix_m2_p25: float
    prix_m2_median: float
    prix_m2_p75: float
    periode: str


class VentesDvf:
    """Accès aux médianes de ventes réelles par commune (cache data/dvf.json)."""

    def __init__(self, donnees: dict, ventes_minimum: int) -> None:
        self.donnees = donnees
        self.ventes_minimum = ventes_minimum

    def pour(self, code_postal: str) -> VentesSecteur | None:
        insee = self.donnees.get("insee_par_cp", {}).get(code_postal)
        commune = self.donnees.get("communes", {}).get(insee or "")
        if not commune or commune.get("nb", 0) < self.ventes_minimum:
            return None
        return VentesSecteur(
            nb=commune["nb"],
            prix_m2_p25=commune["p25"],
            prix_m2_median=commune["p50"],
            prix_m2_p75=commune["p75"],
            periode=commune["periode"],
        )


def _resoudre_insee(session: requests.Session, code_postal: str) -> str | None:
    """Code INSEE d'un code postal. Paris : 750xx -> 751xx sans appel réseau."""
    if code_postal.startswith("750") and len(code_postal) == 5:
        return "751" + code_postal[3:]
    try:
        reponse = session.get(
            URL_GEO_COMMUNES, params={"codePostal": code_postal, "fields": "code"},
            timeout=15,
        )
        reponse.raise_for_status()
        communes = reponse.json()
    except Exception as exc:  # noqa: BLE001 — jamais bloquant
        log.info("geo.api.gouv.fr indisponible pour %s : %s", code_postal, exc)
        return None
    # Un code postal peut couvrir plusieurs communes : on prend la première —
    # approximation assumée (les annonces portent rarement mieux que le CP).
    return communes[0]["code"] if communes else None


def actualiser_dvf(
    chemin: Path,
    codes_postaux: list[str],
    config_dvf: dict,
) -> VentesDvf | None:
    """Rafraîchit quelques communes par tournée ; retourne l'accès au cache.

    `codes_postaux` : ceux des annonces actuellement retenues — on ne collecte
    que les secteurs où l'on chasse vraiment.
    """
    if not config_dvf.get("actif", False):
        return None
    ventes_minimum = int(config_dvf.get("ventes_minimum", 6))
    annees = [int(a) for a in config_dvf.get("annees", [2023, 2024, 2025])]
    max_par_run = int(config_dvf.get("max_communes_par_run", 12))

    donnees: dict = {"maj": None, "insee_par_cp": {}, "communes": {}}
    if chemin.exists():
        try:
            donnees = json.loads(chemin.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            log.exception("data/dvf.json illisible, cache reconstruit")

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    maintenant = datetime.fromisoformat(maintenant_iso())
    traitees = 0
    modifie = False

    for code_postal in dict.fromkeys(codes_postaux):  # dédoublonné, ordre stable
        if traitees >= max_par_run:
            break
        if not code_postal or len(code_postal) != 5:
            continue
        insee = donnees["insee_par_cp"].get(code_postal)
        if insee is None:
            insee = _resoudre_insee(session, code_postal)
            time.sleep(DELAI_ENTRE_APPELS_S)
            if insee is None:
                continue
            donnees["insee_par_cp"][code_postal] = insee
            modifie = True

        commune = donnees["communes"].get(insee)
        if commune:
            try:
                age = maintenant - datetime.fromisoformat(commune["maj"])
                if age.days < JOURS_FRAICHEUR_COMMUNE and commune.get("annees") == annees:
                    continue  # déjà frais, mêmes années : rien à faire
            except (KeyError, ValueError):
                pass

        prix_m2: list[float] = []
        echec = False
        for annee in annees:
            try:
                reponse = session.get(
                    URL_COMMUNE.format(annee=annee, dep=insee[:2], insee=insee), timeout=30
                )
                time.sleep(DELAI_ENTRE_APPELS_S)
                if reponse.status_code == 404:
                    continue  # pas de fichier pour cette commune/année : pas une panne
                reponse.raise_for_status()
                reponse.encoding = "utf-8"  # le serveur ne déclare pas le charset
                prix_m2.extend(extraire_prix_m2(reponse.text))
            except Exception as exc:  # noqa: BLE001 — on garde l'ancien état de la commune
                log.info("DVF %s %s indisponible : %s", insee, annee, exc)
                echec = True
                break
        if echec:
            continue

        donnees["communes"][insee] = {
            "maj": maintenant_iso(),
            "annees": annees,
            "nb": len(prix_m2),
            "p25": round(_quantile(prix_m2, 0.25)) if prix_m2 else None,
            "p50": round(_quantile(prix_m2, 0.50)) if prix_m2 else None,
            "p75": round(_quantile(prix_m2, 0.75)) if prix_m2 else None,
            "periode": f"{min(annees)}-{max(annees)}",
        }
        modifie = True
        traitees += 1

    if modifie:
        donnees["maj"] = maintenant_iso()
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(json.dumps(donnees, ensure_ascii=False, indent=1), encoding="utf-8")
        log.info("DVF : %d commune(s) rafraîchie(s), %d au total en cache",
                 traitees, len(donnees["communes"]))
    return VentesDvf(donnees, ventes_minimum)
