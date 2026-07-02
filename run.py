"""Point d'entrée du collecteur : collecte -> pipeline -> stockage.

Phases suivantes : génération du dashboard (3) et notifications email (4) se
brancheront ici, après la sauvegarde.

Le run ne doit JAMAIS échouer à cause d'une source : chaque source est isolée
dans un try/except et notée dans le rapport de santé.
"""
from __future__ import annotations

import logging
import sys
from typing import Any

from pipeline.config import RACINE, Config
from pipeline.dedoublonnage import fusionner, trouver_similaire
from pipeline.enrichissement import Benchmarks, enrichir
from pipeline.filtres import raison_exclusion
from pipeline.geo import Trajets
from pipeline.modeles import Annonce, AnnonceBrute
from pipeline.normalisation import maintenant_iso, normaliser
from pipeline.scoring import scorer
from pipeline.stockage import Stockage
from sources import sources_actives

log = logging.getLogger("collecteur")


def collecter_toutes_sources(config: Config) -> tuple[list[AnnonceBrute], dict[str, Any]]:
    """Interroge chaque source active ; une panne est loguée, jamais fatale."""
    brutes: list[AnnonceBrute] = []
    sante: dict[str, Any] = {}
    for nom, fabrique in sources_actives(config):
        try:
            source = fabrique()
            lot = source.collecter()
            brutes.extend(lot)
            sante[nom] = {"statut": "ok", "annonces": len(lot)}
            if source.avertissements:
                sante[nom]["avertissements"] = list(source.avertissements)
                log.warning("source %s : %s", nom, "; ".join(source.avertissements))
            log.info("source %s : %d annonces", nom, len(lot))
        except Exception as exc:  # noqa: BLE001 — tolérance aux pannes voulue
            sante[nom] = {"statut": "erreur", "message": str(exc)}
            log.exception("source %s en échec, on continue", nom)
    return brutes, sante


def integrer(
    brutes: list[AnnonceBrute], annonces: dict[str, Annonce], config: Config, quand: str
) -> list[str]:
    """Normalise et intègre les annonces collectées ; retourne les ids nouveaux."""
    nouvelles: list[str] = []
    for brute in brutes:
        try:
            a = normaliser(brute, quand)
        except Exception:  # noqa: BLE001 — une annonce illisible ne bloque pas le run
            log.exception("annonce illisible, ignorée (%s)", brute.url)
            continue
        if a.id in annonces:
            existante = annonces[a.id]
            existante.date_derniere_vue = quand
            existante.prix = a.prix  # suit les baisses de prix
            existante.loyer_mensuel = a.loyer_mensuel or existante.loyer_mensuel
        else:
            similaire = trouver_similaire(a, annonces.values(), config)
            if similaire is not None:
                fusionner(similaire, a)
                log.info("doublon cross-sources fusionné : %s -> %s", a.url, similaire.id)
            else:
                annonces[a.id] = a
                nouvelles.append(a.id)
    return nouvelles


def executer() -> dict[str, Any]:
    config = Config.charger()
    trajets = Trajets.charger(RACINE / "data" / "trajets.json")
    benchmarks = Benchmarks.charger(RACINE / "data" / "benchmarks.json")
    stockage = Stockage(RACINE / "data" / "annonces.json")
    annonces, _ = stockage.charger()
    quand = maintenant_iso()

    brutes, sante = collecter_toutes_sources(config)
    nouvelles = integrer(brutes, annonces, config, quand)

    # Filtrage + enrichissement + scoring recalculés sur tout le stock à chaque run,
    # pour que les changements de config.yaml ou des benchmarks s'appliquent partout.
    seuil_decote = config.scoring["prix_m2_vs_benchmark"]["seuil_decote_pct"]
    for a in annonces.values():
        a.raison_exclusion = raison_exclusion(a, config, trajets)
        a.exclue = a.raison_exclusion is not None
        if a.exclue:
            a.score = None
            a.detail_score = {}
        else:
            enrichir(a, benchmarks, seuil_decote)
            scorer(a, config)

    meta = {
        "derniere_execution": quand,
        "sante_sources": sante,
        "nouvelles_ce_run": nouvelles,
    }
    stockage.sauvegarder(annonces, meta)
    afficher_rapport(annonces, nouvelles, sante)
    return meta


def afficher_rapport(
    annonces: dict[str, Annonce], nouvelles: list[str], sante: dict[str, Any]
) -> None:
    retenues = sorted(
        (a for a in annonces.values() if not a.exclue), key=lambda a: a.score or 0, reverse=True
    )
    exclues = [a for a in annonces.values() if a.exclue]

    print("\n=== Santé des sources ===")
    for nom, s in sante.items():
        if s["statut"] == "ok":
            print(f"  {nom} : ok ({s['annonces']} annonces)")
            for avertissement in s.get("avertissements", []):
                print(f"      avertissement : {avertissement}")
        else:
            print(f"  {nom} : ERREUR — {s.get('message', '?')}")

    print(f"\n=== {len(retenues)} annonces retenues ({len(nouvelles)} nouvelles ce run) ===")
    for a in retenues:
        surface = f"{a.surface_m2:.0f} m²" if a.surface_m2 else "surface ?"
        rendement = (
            f"{a.rendement_brut_pct:.1f} %" + (" (estimé)" if a.loyer_estime else "")
            if a.rendement_brut_pct is not None
            else "n/a"
        )
        alerte = " ⚠️" if "rendement_anormalement_eleve" in a.flags else ""
        prix = f"{a.prix:,.0f} €".replace(",", " ")
        print(
            f"  [{a.score:>3}] {a.titre} — {a.ville} ({a.code_postal}) — {prix} — "
            f"{surface} — rendement brut {rendement}{alerte}"
        )

    print(f"\n=== {len(exclues)} annonces exclues (transparence du filtre) ===")
    for a in exclues:
        print(f"  - {a.titre} ({a.ville}) : {a.raison_exclusion}")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout.reconfigure(encoding="utf-8")  # console Windows
    executer()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
