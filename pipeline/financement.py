"""Hypothèses d'exploitation communes au score, à la décision et aux offres."""
from __future__ import annotations

import math

from pipeline.config import Config
from pipeline.modeles import Annonce


def mensualite_credit(capital: float, taux_pct: float, duree_ans: int) -> float:
    if capital <= 0:
        return 0.0
    n = duree_ans * 12
    t = taux_pct / 1200
    return capital * t / (1 - (1 + t) ** -n) if t else capital / n


def hypotheses_exploitation(a: Annonce, config: Config) -> dict:
    """Une provision est une hypothèse affichée, jamais une donnée vendeur.

    Zéro déclaré est conservé ; une taxe absente ou invalide est provisionnée.
    Les charges incluent entretien/gestion ; la taxe est déduite séparément,
    même si sa refacturation au locataire est annoncée mais non vérifiée.
    """
    loyer = a.loyer_mensuel or a.loyer_mensuel_estime
    recherche = config.donnees.get("recherche", {})
    vacance = float(recherche.get("vacance_prudente_pct", 8))
    charges = float(recherche.get("provision_charges_pct", 10))
    taxe = a.taxe_fonciere_annuelle
    connue = (isinstance(taxe, (int, float)) and not isinstance(taxe, bool)
              and math.isfinite(taxe) and taxe >= 0)
    mois = float(config["analyse"].get("dossier_banque", {}).get("taxe_fonciere_mois_loyer", 1))
    taxe = taxe if connue else (loyer * mois if loyer else None)
    return {
        "taxe_estimee": not connue, "taxe_annuelle_retenue": taxe,
        "vacance_pct": vacance, "charges_pct": charges,
        "revenu_prudent": loyer * (1 - (vacance + charges) / 100) - taxe / 12 if loyer else None,
        # Le scénario dégradé ne peut pas être plus favorable que le prudent.
        "revenu_stress": loyer * .9 * (1 - max(2/12, vacance/100) - charges/100) - taxe / 12 if loyer else None,
    }
