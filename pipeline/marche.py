"""Contexte de marché — séries officielles gratuites, actualisées ~1 fois/mois.

Le tableau de bord affiche des annonces ; ce module apporte le PAYSAGE derrière
elles : où en sont les loyers commerciaux, les prix immobiliers, les taux et
les défaillances d'entreprises. Uniquement des séries officielles, gratuites
et SANS CLÉ — chaque graphique cite sa source et son identifiant de série,
vérifiables en un clic :

- INSEE BDM (api SDMX `bdm.insee.fr`, sans clé) :
  ILC — l'indice qui révise les baux commerciaux, LA référence du métier ;
  prix des logements anciens IdF (Notaires-INSEE, CVS) ; défaillances
  d'entreprises IdF en cumul 12 mois (tous secteurs, commerce,
  hébergement-restauration — les locataires typiques de murs de boutique).
- Eurostat (déjà utilisé par taux_marche.py) : rendement OAT 10 ans France.

Cadence : les séries sont mensuelles ou trimestrielles — réinterroger les API
à chaque tournée (3×/jour) serait du gaspillage impoli. Les données ne sont
rafraîchies que si le fichier a plus de JOURS_FRAICHEUR jours ; entre-temps,
le fichier committé fait foi. Une panne d'API ne perd JAMAIS l'historique :
chaque série en échec conserve ses points précédents, avec sa date d'origine.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path

import requests

from pipeline.normalisation import maintenant_iso
from sources.http import USER_AGENT

log = logging.getLogger("collecteur.marche")

JOURS_FRAICHEUR = 27  # < 1 mois : assez frais pour des séries mensuelles/trimestrielles
DEPUIS = "2015"

URL_INSEE = "https://bdm.insee.fr/series/sdmx/data/SERIES_BDM/{idbanks}?startPeriod=" + DEPUIS
URL_EUROSTAT = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/irt_lt_mcby_m"

# idbanks INSEE relevés le 2026-07-10 en sondant les dataflows ILC-ILAT-ICC,
# IPLA-IPLNA-2015 et DEFAILLANCES-ENTREPRISES (voir la mémoire du projet).
SERIES_INSEE: dict[str, dict[str, str]] = {
    "ilc": {
        "idbank": "001532540",
        "libelle": "Loyers commerciaux (ILC)",
        "unite": "indice, base 100 au T1 2008",
        "frequence": "trimestrielle",
        "lecture": "L'indice officiel de révision des baux commerciaux : la pente "
                   "de VOS futurs loyers.",
    },
    "logements_idf": {
        "idbank": "010567079",
        "libelle": "Prix des logements anciens en Île-de-France",
        "unite": "indice, base 100 en 2015 (CVS)",
        "frequence": "trimestrielle",
        "lecture": "Indice Notaires-INSEE : le cycle immobilier francilien — les murs "
                   "commerciaux n'y échappent pas, avec retard et amplitude moindre.",
    },
    "defaillances_idf": {
        "idbank": "001656272",
        "libelle": "Tous secteurs",
        "unite": "défaillances, cumul 12 mois",
        "frequence": "mensuelle",
        "lecture": "Jugements d'ouverture de procédure collective en Île-de-France, "
                   "cumulés sur 12 mois glissants.",
    },
    "defaillances_commerce_idf": {
        "idbank": "001656240",
        "libelle": "Commerce",
        "unite": "défaillances, cumul 12 mois",
        "frequence": "mensuelle",
        "lecture": "Commerce et réparation automobile en Île-de-France : la santé des "
                   "locataires-boutiquiers.",
    },
    "defaillances_resto_idf": {
        "idbank": "001656243",
        "libelle": "Hébergement-restauration",
        "unite": "défaillances, cumul 12 mois",
        "frequence": "mensuelle",
        "lecture": "Hébergement et restauration en Île-de-France : les restaurateurs, "
                   "locataires typiques de murs de boutique.",
    },
    "climat_commerce": {
        "idbank": "001786560",
        "libelle": "Climat des affaires dans le commerce de détail",
        "unite": "indice, moyenne de longue période = 100",
        "frequence": "mensuelle",
        "lecture": "Le moral de vos futurs locataires, interrogés chaque mois par l'INSEE : "
                   "sous 100, les commerçants voient l'avenir sombre — ils négocient leurs "
                   "loyers plus durement et signent moins de baux.",
    },
    "cout_construction": {
        "idbank": "000008630",
        "libelle": "Coût de la construction (ICC)",
        "unite": "indice, base 100 au T4 1953",
        "frequence": "trimestrielle",
        "lecture": "Le prix de faire des travaux : une envolée de l'ICC renchérit toute "
                   "rénovation de local — à garder en tête devant un bien « à rafraîchir ».",
    },
}

_SERIE_RE = re.compile(r"<Series ([^>]+)>(.*?)</Series>", re.DOTALL)
_OBS_RE = re.compile(r'<Obs [^>]*?TIME_PERIOD="([^"]+)"[^>]*?OBS_VALUE="([^"]+)"')


def _cle_periode(periode: str) -> tuple[int, int]:
    """Ordre chronologique : « 2015-Q1 » et « 2015-01 » triables ensemble."""
    annee, reste = periode.split("-", 1)
    if reste.startswith("Q"):
        return int(annee), int(reste[1:]) * 3  # T1 -> mois 3, etc.
    return int(annee), int(reste)


def _series_insee() -> dict[str, list[list]]:
    """points par idbank, une seule requête pour toutes les séries."""
    idbanks = "+".join(v["idbank"] for v in SERIES_INSEE.values())
    reponse = requests.get(
        URL_INSEE.format(idbanks=idbanks),
        headers={"User-Agent": USER_AGENT}, timeout=30,
    )
    reponse.raise_for_status()
    resultat: dict[str, list[list]] = {}
    for attributs, corps in _SERIE_RE.findall(reponse.text):
        idbank = re.search(r'IDBANK="([^"]+)"', attributs)
        if not idbank:
            continue
        points = []
        for periode, valeur in _OBS_RE.findall(corps):
            try:
                points.append([periode, float(valeur)])
            except ValueError:  # valeur manquante (« . »…) : point ignoré
                continue
        points.sort(key=lambda p: _cle_periode(p[0]))
        resultat[idbank.group(1)] = points
    return resultat


def _serie_oat() -> list[list]:
    reponse = requests.get(
        URL_EUROSTAT,
        params={"geo": "FR", "format": "JSON", "sinceTimePeriod": f"{DEPUIS}-01"},
        headers={"User-Agent": USER_AGENT}, timeout=30,
    )
    reponse.raise_for_status()
    donnees = reponse.json()
    index_temps = donnees["dimension"]["time"]["category"]["index"]
    par_position = {str(pos): mois for mois, pos in index_temps.items()}
    points = [
        [par_position[pos], round(float(v), 2)]
        for pos, v in donnees["value"].items()
        if pos in par_position
    ]
    points.sort(key=lambda p: _cle_periode(p[0]))
    return points


def _collecter(existant: dict | None) -> dict:
    """Toutes les séries ; celle qui échoue GARDE ses points précédents."""
    anciennes = (existant or {}).get("series", {})
    series: dict[str, dict] = {}

    try:
        par_idbank = _series_insee()
    except Exception as exc:  # noqa: BLE001 — jamais bloquant
        log.warning("INSEE BDM indisponible (%s) — séries INSEE conservées telles quelles", exc)
        par_idbank = {}
    for cle, meta in SERIES_INSEE.items():
        points = par_idbank.get(meta["idbank"]) or (anciennes.get(cle) or {}).get("points") or []
        series[cle] = {
            "libelle": meta["libelle"],
            "unite": meta["unite"],
            "frequence": meta["frequence"],
            "lecture": meta["lecture"],
            "source": f"INSEE, série {meta['idbank']}",
            "url": f"https://www.insee.fr/fr/statistiques/serie/{meta['idbank']}",
            "points": points,
        }

    try:
        points_oat = _serie_oat()
    except Exception as exc:  # noqa: BLE001
        log.warning("Eurostat indisponible (%s) — série OAT conservée telle quelle", exc)
        points_oat = (anciennes.get("oat") or {}).get("points") or []
    series["oat"] = {
        "libelle": "Taux des obligations d'État françaises à 10 ans (OAT)",
        "unite": "% par an",
        "frequence": "mensuelle",
        "lecture": "La référence sur laquelle les banques indexent leurs crédits : "
                   "quand l'OAT monte, votre futur taux monte.",
        "source": "Eurostat, série irt_lt_mcby_m (critère de Maastricht)",
        "url": "https://ec.europa.eu/eurostat/databrowser/view/irt_lt_mcby_m/",
        "points": points_oat,
    }

    return {"maj": maintenant_iso(), "series": series}


def actualiser_marche(chemin: Path) -> dict | None:
    """Contenu du contexte de marché, réinterrogé au plus 1 fois par mois.

    Retourne le dict (depuis le fichier s'il est frais, sinon fraîchement
    collecté et sauvegardé), ou None si rien n'est disponible du tout.
    """
    existant: dict | None = None
    if chemin.exists():
        try:
            existant = json.loads(chemin.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 — fichier corrompu : on recollecte
            log.exception("data/marche.json illisible, recollecte")

    if existant:
        try:
            age = datetime.fromisoformat(maintenant_iso()) - datetime.fromisoformat(existant["maj"])
            # Un fichier frais dispense de recollecte SAUF si la configuration
            # attend une série qu'il n'a pas encore (série ajoutée au code) :
            # sans ce contrôle, un nouveau graphique attendrait un mois.
            attendues = set(SERIES_INSEE) | {"oat"}
            if age.days < JOURS_FRAICHEUR and attendues <= set(existant.get("series", {})):
                return existant
        except (KeyError, ValueError):
            pass  # champ maj absent/invalide : on recollecte

    contenu = _collecter(existant)
    if not any(s["points"] for s in contenu["series"].values()):
        log.warning("aucune série de marché disponible — on garde l'existant")
        return existant
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(
        json.dumps(contenu, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    log.info("contexte de marché actualisé (%d séries)", len(contenu["series"]))
    return contenu
