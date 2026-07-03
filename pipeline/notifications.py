"""Notifications email via Resend (free tier).

Deux emails, envoyés UNIQUEMENT quand il y a matière :
- « 🔥 Pépite » immédiat pour toute NOUVELLE annonce à score ≥ seuil pépite,
  avec anti-doublon persistant (une pépite n'est notifiée qu'une fois) ;
- récapitulatif quotidien : top des nouvelles annonces retenues du run.

Secrets attendus en variables d'environnement (GitHub Actions) :
    RESEND_API_KEY  clé API Resend
    EMAIL_TO        destinataire (l'adresse du compte Resend en free tier)

Sans ces variables, on n'envoie rien et on le dit (statut « non configurées »).
Les emails sont autosuffisants : décision possible sans ouvrir le dashboard.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import requests

from pipeline.config import Config
from pipeline.modeles import Annonce

log = logging.getLogger("collecteur.notifications")

_API = "https://api.resend.com/emails"
_EXPEDITEUR = "Les Murs. <onboarding@resend.dev>"

_STYLE_CARTE = (
    "border:1px solid #e3e3da;border-radius:10px;padding:14px 16px;"
    "margin:0 0 12px;font-family:Georgia,serif;"
)
_STYLE_CHIP = (
    "display:inline-block;padding:2px 10px;border-radius:999px;"
    "font-weight:bold;font-family:Arial,sans-serif;font-size:13px;"
)


def _fmt_euros(valeur: float | None) -> str:
    return "—" if valeur is None else f"{valeur:,.0f} €".replace(",", " ")


def _fmt_pct(valeur: float | None) -> str:
    return "—" if valeur is None else f"{valeur:.1f} %".replace(".", ",")


def _carte_html(a: Annonce) -> str:
    score = a.score or 0
    couleur = "#1c5e2a" if score >= 75 else ("#8a5a00" if score >= 60 else "#4e544e")
    fond = "#e3efe4" if score >= 75 else ("#f9edd2" if score >= 60 else "#ecede7")
    loyer = a.loyer_mensuel if a.loyer_mensuel is not None else a.loyer_mensuel_estime
    mention = " (est.)" if (a.loyer_mensuel is None and loyer is not None) or a.loyer_estime else ""
    lignes = [
        f"<b>{_fmt_euros(a.prix)}</b> · {a.surface_m2 or '?'} m² · "
        f"{_fmt_euros(a.prix_m2)}/m²",
        f"Loyer : {_fmt_euros(loyer)}/mois{mention} — rendement brut "
        f"<b>{_fmt_pct(a.rendement_brut_pct)}{mention}</b>, "
        f"acte en main {_fmt_pct(a.rendement_acte_en_main_pct)}",
    ]
    if a.lecture_prix:
        lignes.append(f"<i>{a.lecture_prix}</i>")
    contenu = "<br>".join(lignes)
    type_murs = "Murs occupés" if a.type_murs.value == "murs_occupes" else "Murs libres"
    return f"""<div style="{_STYLE_CARTE}">
  <div style="margin-bottom:6px">
    <span style="{_STYLE_CHIP}background:{fond};color:{couleur}">{score} /100</span>
    <span style="{_STYLE_CHIP}background:#ecede7;color:#4e544e">{type_murs}</span>
  </div>
  <div style="font-size:16px;font-weight:bold;margin-bottom:2px">
    <a href="{a.url}" style="color:#1d5240">{a.titre}</a>
  </div>
  <div style="color:#4e544e;font-size:13px;margin-bottom:8px">{a.ville} ({a.code_postal})</div>
  <div style="font-size:14px;line-height:1.5">{contenu}</div>
  <div style="margin-top:10px"><a href="{a.url}"
    style="background:#1d5240;color:#f2efe4;padding:7px 14px;border-radius:8px;
    text-decoration:none;font-family:Arial,sans-serif;font-size:13px">Voir l'annonce →</a></div>
</div>"""


def _enveloppe(titre: str, corps: str, url_dashboard: str) -> str:
    pied = (
        f'<p style="margin-top:18px"><a href="{url_dashboard}" '
        f'style="color:#1d5240;font-weight:bold">Ouvrir le tableau de chasse complet →</a></p>'
        if url_dashboard else ""
    )
    return f"""<div style="max-width:640px;margin:0 auto;background:#f6f6f1;padding:18px">
  <div style="background:#1d5240;color:#f2efe4;padding:16px 20px;border-radius:12px 12px 0 0;
    border-top:3px solid #a87c1f">
    <span style="font-family:Georgia,serif;font-size:26px;font-weight:bold">Les Murs<span style="color:#d6a532">.</span></span>
    <span style="font-size:13px;opacity:.85"> — {titre}</span>
  </div>
  <div style="background:#fdfdfa;padding:18px 20px;border-radius:0 0 12px 12px">
    {corps}
    {pied}
    <p style="color:#82887e;font-size:12px;margin-top:14px">Veille automatique quotidienne.
    Rappel : ⚠️ tout rendement élevé se vérifie (bail, locataire, quartier) avant d'appeler.</p>
  </div>
</div>"""


def _envoyer(cle_api: str, destinataire: str, sujet: str, html: str) -> None:
    reponse = requests.post(
        _API,
        headers={"Authorization": f"Bearer {cle_api}"},
        json={"from": _EXPEDITEUR, "to": [destinataire], "subject": sujet, "html": html},
        timeout=30,
    )
    reponse.raise_for_status()


def notifier(
    annonces: dict[str, Annonce],
    nouvelles_ids: list[str],
    meta: dict[str, Any],
    config: Config,
) -> dict[str, Any]:
    """Envoie ce qui doit l'être ; retourne un petit rapport pour la santé/les logs.

    Effet de bord voulu : meta["pepites_notifiees"] mémorise les pépites déjà
    signalées (persisté dans le stockage) pour ne jamais notifier deux fois.
    """
    parametres = config["notifications"]
    cle_api = os.environ.get("RESEND_API_KEY")
    destinataire = os.environ.get("EMAIL_TO")
    seuil_pepite = config.scoring["seuils"]["pepite"]
    url_dashboard = parametres.get("url_dashboard", "") or ""

    deja_notifiees = set(meta.get("pepites_notifiees", []))
    pepites = [
        a for a in annonces.values()
        if not a.exclue and (a.score or 0) >= seuil_pepite and a.id not in deja_notifiees
    ]
    nouvelles = sorted(
        (
            annonces[i] for i in nouvelles_ids
            if i in annonces and not annonces[i].exclue
        ),
        key=lambda a: a.score or 0,
        reverse=True,
    )[: int(parametres.get("max_annonces_email", 5))]

    rapport: dict[str, Any] = {"pepites": len(pepites), "quotidien": len(nouvelles)}
    if not cle_api or not destinataire:
        rapport["statut"] = "non configurées (RESEND_API_KEY / EMAIL_TO absents)"
        if pepites or nouvelles:
            log.warning("notifications non configurées : %s", rapport)
        return rapport

    try:
        if pepites:
            corps = "".join(_carte_html(a) for a in pepites)
            sujet = f"🔥 Pépite détectée : {pepites[0].titre[:60]} ({pepites[0].score}/100)"
            _envoyer(cle_api, destinataire, sujet,
                     _enveloppe("alerte pépite", corps, url_dashboard))
            meta["pepites_notifiees"] = sorted(deja_notifiees | {a.id for a in pepites})
            log.info("email pépite envoyé (%d annonce(s))", len(pepites))

        if nouvelles and parametres.get("email_quotidien", True):
            corps = (
                f"<p style='font-size:14px'>{len(nouvelles_ids)} nouvelle(s) annonce(s) "
                f"détectée(s) aujourd'hui — voici les mieux notées :</p>"
                + "".join(_carte_html(a) for a in nouvelles)
            )
            sujet = f"Les Murs. — {len(nouvelles_ids)} nouveauté(s), top : {nouvelles[0].score}/100"
            _envoyer(cle_api, destinataire, sujet,
                     _enveloppe("le point du jour", corps, url_dashboard))
            log.info("email quotidien envoyé (%d annonce(s))", len(nouvelles))
        rapport["statut"] = "ok"
    except Exception as exc:  # noqa: BLE001 — un échec d'envoi ne casse pas le run
        rapport["statut"] = f"erreur : {exc}"
        log.exception("envoi des notifications en échec")
    return rapport
