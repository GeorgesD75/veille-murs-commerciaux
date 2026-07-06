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

from dashboard.generer import generer_dashboard
from pipeline.comparables import LoyersComparables
from pipeline.config import RACINE, Config
from pipeline.critique import generer_critiques
from pipeline.dedoublonnage import fusionner, trouver_similaire
from pipeline.enrichissement import Benchmarks, enrichir
from pipeline.filtres import raison_exclusion
from pipeline.geo import Trajets
from pipeline.modeles import Annonce, AnnonceBrute
from pipeline.normalisation import maintenant_iso, normaliser
from pipeline.notifications import notifier
from pipeline.rue import evaluer_annonces
from pipeline.scoring import scorer
from pipeline.stockage import Stockage
from pipeline.taux_marche import taux_credit_estime
from sources import sources_actives
from sources.encheres import CollecteurEncheres, scorer_lots

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
            if a.prix is not None and existante.prix is not None and a.prix != existante.prix:
                # Premier changement observé : on horodate aussi le prix DE DÉPART
                # (jusque-là implicite), puis le nouveau — un vendeur qui baisse
                # son prix au fil du temps est un signal de négociation précieux.
                if not existante.historique_prix:
                    existante.historique_prix.append(
                        {"date": existante.date_premiere_vue, "prix": existante.prix}
                    )
                existante.historique_prix.append({"date": quand, "prix": a.prix})
            existante.prix = a.prix  # suit les baisses de prix
            existante.loyer_mensuel = a.loyer_mensuel or existante.loyer_mensuel
            # Les infos de présentation se rafraîchissent aussi (photos ajoutées
            # par l'agence, description étoffée…)
            existante.images = a.images or existante.images
            existante.image_url = a.image_url or existante.image_url
            if len(a.description) > len(existante.description):
                existante.description = a.description
        else:
            similaire = trouver_similaire(a, annonces.values(), config)
            if similaire is not None:
                fusionner(similaire, a)
                log.info("doublon cross-sources fusionné : %s -> %s", a.url, similaire.id)
            else:
                annonces[a.id] = a
                nouvelles.append(a.id)
    return nouvelles


def actualiser_taux_marche(config: Config) -> dict[str, Any] | None:
    """Remplace le taux de crédit statique par le taux de marché du jour, si
    disponible ; sinon le taux de config.yaml reste en place, sans erreur."""
    marge = config["analyse"]["financement"].get("marge_credit_pro_pct", 0)
    resultat = taux_credit_estime(marge)
    if resultat is not None:
        config.donnees["analyse"]["financement"]["taux_pct"] = resultat["taux_pct"]
        log.info(
            "taux de marché : %.2f %% (OAT France %s : %.2f %% + marge %.2f pt)",
            resultat["taux_pct"], resultat["mois_reference"], resultat["oat_pct"], resultat["marge_pct"],
        )
    return resultat


def executer() -> dict[str, Any]:
    config = Config.charger()
    taux_marche = actualiser_taux_marche(config)
    trajets = Trajets.charger(RACINE / "data" / "trajets.json")
    benchmarks = Benchmarks.charger(RACINE / "data" / "benchmarks.json")
    stockage = Stockage(RACINE / "data" / "annonces.json")
    annonces, ancienne_meta = stockage.charger()
    quand = maintenant_iso()

    brutes, sante = collecter_toutes_sources(config)
    nouvelles = integrer(brutes, annonces, config, quand)

    # Canal spécial : enchères à venir (hors scoring — une mise à prix n'est
    # pas un prix de marché). Rafraîchi entièrement à chaque run.
    encheres: list = []
    encheres_ecartees = 0
    if (config.sources.get("encheres_publiques") or {}).get("actif"):
        try:
            encheres, encheres_ecartees = scorer_lots(
                CollecteurEncheres(
                    mise_a_prix_max=config.budget["prix_max_filtre"]
                ).collecter(),
                benchmarks,
                trajets,
                config,
            )
            sante["encheres_publiques"] = {"statut": "ok", "annonces": len(encheres)}
            log.info(
                "enchères : %d lots IdF gardés, %d écartés (départ trop haut)",
                len(encheres), encheres_ecartees,
            )
        except Exception as exc:  # noqa: BLE001
            sante["encheres_publiques"] = {"statut": "erreur", "message": str(exc)}
            log.exception("collecte des enchères en échec, on continue")

    # Filtrage + enrichissement + scoring recalculés sur tout le stock à chaque run,
    # pour que les changements de config.yaml ou des benchmarks s'appliquent partout.
    seuil_decote = config.scoring["prix_m2_vs_benchmark"]["seuil_decote_pct"]
    rendement_cible = config["analyse"]["rendement_cible_pct"]
    for a in annonces.values():
        a.raison_exclusion = raison_exclusion(a, config, trajets)
        a.exclue = a.raison_exclusion is not None

    # Emplacement rue par rue (API publiques, volume plafonné par run) : calculé
    # à part, AVANT le scoring, pour que ses points soient déjà là ce run-ci.
    try:
        evaluer_annonces(annonces, config)
    except Exception:  # noqa: BLE001 — enrichissement optionnel, jamais bloquant
        log.exception("évaluation des rues en échec, on continue sans")

    comparables = LoyersComparables.depuis(a for a in annonces.values() if not a.exclue)
    for a in annonces.values():
        if a.exclue:
            a.score = None
            a.detail_score = {}
        else:
            enrichir(a, benchmarks, seuil_decote, rendement_cible, comparables=comparables)
            scorer(a, config)

    # Critique IA (Claude Haiku, optionnelle) : le score final est requis pour
    # choisir qui critiquer — appelée en dernier, jamais bloquante.
    try:
        generer_critiques(annonces, config)
    except Exception:  # noqa: BLE001 — enrichissement optionnel, jamais bloquant
        log.exception("critique IA en échec, on continue sans")

    meta = {
        "derniere_execution": quand,
        "sante_sources": sante,
        "nouvelles_ce_run": nouvelles,
        "taux_marche": taux_marche,
        "encheres": encheres,
        "encheres_ecartees": encheres_ecartees,
        # Mémoire anti-doublon des emails pépite (complétée par notifier)
        "pepites_notifiees": ancienne_meta.get("pepites_notifiees", []),
    }

    meta["notifications"] = notifier(annonces, nouvelles, meta, config)
    stockage.sauvegarder(annonces, meta)

    try:
        cible = generer_dashboard(annonces, meta, config, RACINE / "docs")
        log.info("dashboard généré : %s", cible)
    except Exception:  # noqa: BLE001 — les données sont sauvées, le run reste utile
        log.exception("génération du dashboard en échec")

    afficher_rapport(annonces, nouvelles, sante, meta["notifications"])
    return meta


def afficher_rapport(
    annonces: dict[str, Annonce],
    nouvelles: list[str],
    sante: dict[str, Any],
    notifications: dict[str, Any],
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

    print(f"\n=== Notifications : {notifications.get('statut', '?')} "
          f"(pépites : {notifications.get('pepites', 0)}, "
          f"quotidien : {notifications.get('quotidien', 0)}) ===")

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
