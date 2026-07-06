"""Critique IA de l'annonce — Claude Haiku 4.5, un avis sceptique et concret.

Génère, pour les annonces retenues à bon score, une critique en langage
naturel qui complète le score plutôt que de le répéter : un « avocat du
diable » cherchant activement les défauts qu'un score chiffré peut manquer
(dépendance à un seul locataire, petite surface pour l'activité visée, loyer
non prouvé, etc.). Jamais une flatterie — le prompt l'exige explicitement.

Optionnel et gratuit par défaut : sans ANTHROPIC_API_KEY, la fonctionnalité
s'affiche simplement comme indisponible (même philosophie que
RESEND_API_KEY/IMAP_PASSWORD ailleurs dans ce projet) — jamais bloquant pour
la tournée. Modèle Haiku 4.5 : le moins cher, largement suffisant pour un
texte de quelques phrases par annonce ; ni le paramètre d'effort ni le
« thinking » adaptatif ne sont disponibles sur ce modèle, on ne les utilise
donc pas.

Générée UNE SEULE FOIS par annonce (mémorisée sur l'objet, persistée dans
data/annonces.json) : pas de re-génération à chaque tournée, pour maîtriser
le coût — voir `generer_critiques` pour le plafond de volume par run.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from pipeline.config import Config
from pipeline.modeles import Annonce, TypeMurs

log = logging.getLogger("collecteur.critique")

MODELE = "claude-haiku-4-5"
MAX_TOKENS = 500

_SYSTEME = (
    "Tu es un investisseur immobilier commercial expérimenté et sceptique, qui "
    "conseille un particulier débutant en Île-de-France. On te donne les données "
    "d'une annonce de murs commerciaux, déjà enrichies par un outil (score, "
    "rendement, position vs marché, signaux de rue, alertes). Ta mission : une "
    "critique honnête en 3 à 5 phrases, en français, qui COMPLÈTE le score "
    "plutôt que de le répéter. Cherche activement ce qui pourrait clocher et "
    "que le score ne capture pas : loyer non prouvé par un bail, décote suspecte "
    "et inexpliquée, surface trop petite ou trop grande pour l'activité visée, "
    "dépendance à un seul locataire, quartier ou rue à vérifier sur place, "
    "document manquant. Si tu ne vois vraiment rien à redire, dis-le, mais "
    "explique pourquoi tu es rassuré. Ne fais jamais l'éloge sans nuance. "
    "Réponds uniquement avec la critique elle-même, sans préambule ni formule "
    "de politesse, sans markdown."
)


def _resume_annonce(annonce: Annonce) -> str:
    lignes = [
        f"Titre : {annonce.titre}",
        f"Ville : {annonce.ville} ({annonce.code_postal})",
        "Type : " + (
            "murs occupés (un locataire paie déjà un loyer)"
            if annonce.type_murs is TypeMurs.MURS_OCCUPES
            else "murs libres (local vide, pas de loyer garanti)"
        ),
    ]
    if annonce.prix:
        lignes.append(f"Prix : {annonce.prix:,.0f} €".replace(",", " "))
    if annonce.surface_m2:
        lignes.append(f"Surface : {annonce.surface_m2:.0f} m²")
    loyer = annonce.loyer_mensuel or annonce.loyer_mensuel_estime
    if loyer:
        if annonce.loyer_mensuel and not annonce.loyer_estime:
            confiance = "réel, bail en cours"
        elif annonce.loyer_confiance == "comparables":
            confiance = f"ESTIMÉ, mais sur {annonce.loyer_nb_comparables} baux réels voisins"
        else:
            confiance = "ESTIMÉ, aucune preuve solide"
        lignes.append(f"Loyer mensuel : {loyer:,.0f} € ({confiance})".replace(",", " "))
    if annonce.rendement_brut_pct is not None:
        lignes.append(f"Rendement brut : {annonce.rendement_brut_pct} %")
    if annonce.decote_pct is not None:
        sens = "sous" if annonce.decote_pct >= 0 else "au-dessus de"
        lignes.append(f"Prix au m² : {abs(annonce.decote_pct):.0f} % {sens} la médiane locale")
    if annonce.rue_categorie:
        lignes.append(
            f"Rue mesurée : {annonce.rue_categorie} ({annonce.rue_nb_commerces} commerces à 150 m"
            + (f", {annonce.rue_nb_vacants} vacants" if annonce.rue_nb_vacants else "") + ")"
        )
    if annonce.caracteristiques:
        lignes.append("Caractéristiques annoncées : " + ", ".join(annonce.caracteristiques))
    if annonce.flags:
        lignes.append("Alertes déjà détectées par l'outil : " + ", ".join(annonce.flags))
    if annonce.score is not None:
        lignes.append(f"Score déjà calculé par l'outil : {annonce.score}/100")
    if annonce.description:
        lignes.append(f"Description de l'annonce : {annonce.description[:500]}")
    return "\n".join(lignes)


def generer_critique(annonce: Annonce, client: Any = None) -> str | None:
    """Critique IA d'une annonce, ou None si indisponible — jamais bloquant."""
    try:
        import anthropic
    except ImportError:
        return None
    if client is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return None
        client = anthropic.Anthropic()
    try:
        reponse = client.messages.create(
            model=MODELE,
            max_tokens=MAX_TOKENS,
            system=_SYSTEME,
            messages=[{"role": "user", "content": _resume_annonce(annonce)}],
        )
    except anthropic.APIStatusError as exc:
        log.warning("critique IA en échec (%s) pour %s", exc, annonce.url)
        return None
    except anthropic.APIConnectionError as exc:
        log.warning("critique IA : connexion impossible (%s)", exc)
        return None
    if getattr(reponse, "stop_reason", None) == "refusal":
        log.info("critique IA refusée par les classificateurs pour %s", annonce.url)
        return None
    texte = next((b.text for b in reponse.content if b.type == "text"), "")
    return texte.strip() or None


def generer_critiques(annonces: dict[str, Annonce], config: "Config") -> None:
    """Critique les meilleures annonces pas encore critiquées, dans une limite
    de volume par run (maîtrise du coût — Haiku reste peu cher mais pas gratuit).

    Générée UNE FOIS par annonce : pas de re-génération, même si le prix ou le
    score changent ensuite (le texte peut légèrement dater, comme une note
    humaine qu'on ne réécrit pas à chaque nouvelle information mineure).
    """
    cfg = dict(config["analyse"].get("critique_ia") or {})
    seuil = cfg.get("seuil_score", 60)
    max_par_run = int(cfg.get("max_par_run", 15))
    if max_par_run <= 0:
        return
    candidats = sorted(
        (
            a for a in annonces.values()
            if not a.exclue and a.critique_ia is None and (a.score or 0) >= seuil
        ),
        key=lambda a: a.score or 0, reverse=True,
    )[:max_par_run]
    if not candidats:
        return
    client = None
    try:
        import anthropic
        if os.environ.get("ANTHROPIC_API_KEY"):
            client = anthropic.Anthropic()
    except ImportError:
        return
    if client is None:
        return
    for a in candidats:
        a.critique_ia = generer_critique(a, client=client)
