"""Recalcule le stock et le site hors ligne, sans collecte ni notifications."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from dashboard.generer import generer_html, preparer_payload
from pipeline.comparables import LoyersComparables
from pipeline.config import Config
from pipeline.dvf import VentesDvf
from pipeline.enrichissement import Benchmarks, enrichir
from pipeline.filtres import raison_exclusion
from pipeline.geo import Trajets
from pipeline.scoring import scorer
from pipeline.stockage import Stockage


def main() -> None:
    config = Config.charger()
    stockage = Stockage(RACINE / "data/annonces.json")
    annonces, meta = stockage.charger()
    # Ne pas changer la date de dernière collecte : aucun réseau n'a été consulté.
    if meta.get("taux_marche"):
        config.donnees["analyse"]["financement"]["taux_pct"] = meta["taux_marche"]["taux_pct"]
    trajets = Trajets.charger(RACINE / "data/trajets.json")
    benchmarks = Benchmarks.charger(RACINE / "data/benchmarks.json")
    dvf_path = RACINE / "data/dvf.json"
    dvf = VentesDvf(json.loads(dvf_path.read_text(encoding="utf-8")),
                    int(config["analyse"].get("dvf", {}).get("ventes_minimum", 5))) if dvf_path.exists() else None
    for a in annonces.values():
        a.raison_exclusion = raison_exclusion(a, config, trajets)
        a.exclue = a.raison_exclusion is not None
    maintenant = datetime.now(ZoneInfo("Europe/Paris"))
    comparables = LoyersComparables.depuis(annonces.values(), maintenant=maintenant)
    for a in annonces.values():
        if a.exclue:
            a.score, a.detail_score = None, {}
            continue
        enrichir(a, benchmarks, config.scoring["prix_m2_vs_benchmark"]["seuil_decote_pct"],
                 config["analyse"]["rendement_cible_pct"], comparables=comparables, dvf=dvf)
        scorer(a, config)
    marche_path = RACINE / "data/marche.json"
    marche = json.loads(marche_path.read_text(encoding="utf-8")) if marche_path.exists() else None
    # Réutilise les dossiers existants : éviter de réécrire des centaines de classeurs.
    fichiers = {p.stem.rsplit("-", 1)[-1]: p.name for p in (RACINE / "docs/dossiers").glob("*.xlsx")}
    dossiers = {a.id: fichiers[a.id[:8]] for a in annonces.values() if a.id[:8] in fichiers}
    payload = preparer_payload(annonces, meta, config, maintenant, dossiers, marche=marche)
    cible = RACINE / "docs/index.html"
    cible.write_text(generer_html(payload), encoding="utf-8")
    print(cible)


if __name__ == "__main__":
    main()
