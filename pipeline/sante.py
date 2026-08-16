"""Historique de santé des sources — détecte les pannes silencieuses.

Le rapport de santé d'une tournée (pipeline/stockage.py) n'est jamais gardé
que pour le DERNIER run : une source en erreur (identifiants expirés) ou qui
retombe à 0 annonce (site qui a changé de structure) est invisible ailleurs
que dans le pied de page du dashboard — constaté en pratique : IMAP resté en
échec d'authentification 4 jours de suite, cessionpme à 0 annonce pendant
5+ jours, sans qu'aucune alerte ne parte.

Un petit fichier JSON (une entrée par source et par jour ; la dernière
tournée du jour l'emporte) suffit pour compter des jours consécutifs en
panne, sans avoir à rejouer l'historique git à chaque tournée.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger("collecteur.sante")


def _en_panne(entree: dict[str, Any], volume_sporadique: bool) -> bool:
    """0 annonce ne compte comme panne que pour une source à volume normalement
    régulier — pour une source par nature sporadique (enchères sans lot cette
    semaine, notaires à faible volume IdF…), 0 est un résultat plausible, pas
    un signe de casse. Constaté en pratique le 2026-08-16 : encheres_publiques
    a déclenché une alerte pour une simple semaine calme."""
    if entree.get("statut") != "ok":
        return True
    return not volume_sporadique and entree.get("annonces", 0) == 0


def charger(chemin: Path) -> dict[str, list[dict[str, Any]]]:
    if not chemin.exists():
        return {}
    return json.loads(chemin.read_text(encoding="utf-8"))


def mettre_a_jour(
    chemin: Path,
    sante_sources: dict[str, Any],
    quand: str,
    jours_retenus: int = 30,
) -> dict[str, list[dict[str, Any]]]:
    """Ajoute (ou remplace) l'entrée du jour pour chaque source et sauvegarde.

    Une seule entrée par jour : plusieurs tournées le même jour ne comptent
    que pour un jour de panne, pas plusieurs.
    """
    jour = quand[:10]
    historique = charger(chemin)
    for nom, s in sante_sources.items():
        entrees = historique.setdefault(nom, [])
        entree = {
            "jour": jour,
            "statut": s.get("statut", "?"),
            "annonces": s.get("annonces", 0),
            "message": s.get("message") or "; ".join(s.get("avertissements", [])) or None,
        }
        if entrees and entrees[-1]["jour"] == jour:
            entrees[-1] = entree
        else:
            entrees.append(entree)
        del entrees[:-jours_retenus]
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(historique, ensure_ascii=False, indent=1), encoding="utf-8")
    return historique


def sources_en_panne(
    historique: dict[str, list[dict[str, Any]]],
    jours_consecutifs: int,
    sources_volume_sporadique: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Sources dont les N derniers jours connus sont TOUS en panne (erreur ou
    0 annonce). Une source jamais vue ou trop récente n'est jamais retenue."""
    sporadiques = sources_volume_sporadique or set()
    resultat = []
    for nom, entrees in historique.items():
        recentes = entrees[-jours_consecutifs:]
        if len(recentes) < jours_consecutifs or not all(
            _en_panne(e, nom in sporadiques) for e in recentes
        ):
            continue
        resultat.append({
            "source": nom,
            "jours": len(recentes),
            "depuis": recentes[0]["jour"],
            "dernier_statut": recentes[-1]["statut"],
            "dernier_message": recentes[-1]["message"],
        })
    return sorted(resultat, key=lambda p: p["source"])
