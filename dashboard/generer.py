"""Génération du dashboard statique (docs/index.html), publié par GitHub Pages.

Un seul fichier HTML autonome (CSS/JS inclus, données embarquées en JSON) :
rien à builder, consultable aussi en local en ouvrant le fichier. Le site est
non référencé (meta noindex + docs/robots.txt).

La préparation des données (tri, badge 🆕 < 48 h, exclues < 7 jours) est faite
ici en Python pour être testable ; le JavaScript ne fait que filtrer/afficher.

Identité visuelle : « Les Murs. » — vert bouteille de devanture parisienne,
titrage Fraunces (chargé depuis Google Fonts sur le site publié ; repli serif
système hors ligne), gris teintés de vert, chiffres tabulaires.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from pipeline.config import Config
from pipeline.modeles import Annonce

HEURES_NOUVEAUTE = 48
JOURS_EXCLUES = 7


def _iso(date: str) -> datetime:
    return datetime.fromisoformat(date)


def preparer_payload(
    annonces: dict[str, Annonce],
    meta: dict[str, Any],
    config: Config,
    maintenant: datetime,
) -> dict[str, Any]:
    """Données embarquées dans la page, prêtes à afficher."""
    seuil_nouveaute = maintenant - timedelta(hours=HEURES_NOUVEAUTE)
    seuil_exclues = maintenant - timedelta(days=JOURS_EXCLUES)

    retenues = []
    for a in sorted(
        (a for a in annonces.values() if not a.exclue),
        key=lambda a: (a.score or 0),
        reverse=True,
    ):
        retenues.append(
            {
                "id": a.id,
                "titre": a.titre,
                "url": a.url,
                "urls_multiples": a.urls_multiples,
                "ville": a.ville,
                "code_postal": a.code_postal,
                "departement": a.departement,
                "type_murs": a.type_murs.value,
                "prix": a.prix,
                "surface_m2": a.surface_m2,
                "prix_m2": a.prix_m2,
                "loyer_mensuel": a.loyer_mensuel,
                "loyer_mensuel_estime": a.loyer_mensuel_estime,
                "loyer_estime": a.loyer_estime,
                "rendement_brut_pct": a.rendement_brut_pct,
                "rendement_acte_en_main_pct": a.rendement_acte_en_main_pct,
                "score": a.score,
                "detail_score": a.detail_score,
                "flags": a.flags,
                "decote_pct": a.decote_pct,
                "marche_prix_m2_bas": a.marche_prix_m2_bas,
                "marche_prix_m2_haut": a.marche_prix_m2_haut,
                "image_url": a.image_url,
                "date_premiere_vue": a.date_premiere_vue,
                "est_nouvelle": _iso(a.date_premiere_vue) >= seuil_nouveaute,
            }
        )

    exclues = [
        {
            "titre": a.titre,
            "url": a.url,
            "ville": a.ville,
            "raison": a.raison_exclusion,
            "date_derniere_vue": a.date_derniere_vue,
        }
        for a in sorted(
            (a for a in annonces.values() if a.exclue),
            key=lambda a: a.date_derniere_vue,
            reverse=True,
        )
        if _iso(a.date_derniere_vue) >= seuil_exclues
    ]

    scoring = config.scoring
    seuils = scoring["seuils"]
    return {
        "genere_le": maintenant.isoformat(timespec="seconds"),
        "derniere_execution": meta.get("derniere_execution", ""),
        "seuils": {
            "vert": seuils["vert"],
            "orange": seuils["orange"],
            "pepite": seuils["pepite"],
            "affichage": seuils.get("affichage", seuils["orange"]),
        },
        # Barème maximal de chaque poste, pour les jauges « pourquoi ce score »
        "maxima": {
            "rendement": scoring["rendement"]["points"],
            "emplacement": scoring["emplacement"]["paris"],
            "prix_m2_vs_benchmark": scoring["prix_m2_vs_benchmark"]["decote_forte"],
            "proximite": scoring["proximite"]["moins_de_20_min"],
        },
        "stats": {
            "retenues": len(retenues),
            "nouvelles": sum(1 for a in retenues if a["est_nouvelle"]),
            "pepites": sum(
                1 for a in retenues if (a["score"] or 0) >= seuils["pepite"]
            ),
            "exclues_recentes": len(exclues),
        },
        "retenues": retenues,
        "exclues_recentes": exclues,
        "sante": meta.get("sante_sources", {}),
    }


def generer_html(payload: dict[str, Any]) -> str:
    donnees = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    return _GABARIT.replace("__DONNEES__", donnees)


def generer_dashboard(
    annonces: dict[str, Annonce],
    meta: dict[str, Any],
    config: Config,
    dossier: Path,
    maintenant: datetime | None = None,
) -> Path:
    maintenant = maintenant or datetime.now().astimezone()
    payload = preparer_payload(annonces, meta, config, maintenant)
    dossier.mkdir(parents=True, exist_ok=True)
    cible = dossier / "index.html"
    cible.write_text(generer_html(payload), encoding="utf-8")
    # Site volontairement non référencé.
    (dossier / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    # Empêche GitHub Pages de passer le dossier dans Jekyll.
    (dossier / ".nojekyll").write_text("", encoding="utf-8")
    return cible


_GABARIT = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Les Murs — veille locaux commerciaux</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,560;9..144,680&display=swap" rel="stylesheet">
<style>
:root {
  --plan: #f6f6f2; --surface: #fdfdfb;
  --marque: #1d5240; --marque-sombre: #163f31; --marque-encre: #f3f1e9;
  --encre-1: #141713; --encre-2: #4e544e; --encre-3: #82887e;
  --filet: #e2e2da; --bord: rgba(20, 30, 20, .11);
  --vert-fond: #e3efe4; --vert-texte: #1c5e2a;
  --orange-fond: #f9edd2; --orange-texte: #8a5a00;
  --gris-fond: #ecede7; --gris-texte: #4e544e;
  --alerte-fond: #f9e6dc; --alerte-texte: #98351b;
  --bande: #edf3ee;
}
@media (prefers-color-scheme: dark) {
  :root {
    --plan: #101210; --surface: #191c19;
    --marque: #163f31; --marque-sombre: #113126; --marque-encre: #eceade;
    --encre-1: #f4f4ef; --encre-2: #bcc2ba; --encre-3: #848a80;
    --filet: #2a2d29; --bord: rgba(255,255,255,.10);
    --vert-fond: #14301a; --vert-texte: #7fce8c;
    --orange-fond: #362a0d; --orange-texte: #eebe5e;
    --gris-fond: #242723; --gris-texte: #bcc2ba;
    --alerte-fond: #3a1e12; --alerte-texte: #f0a184;
    --bande: #17211a;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--plan); color: var(--encre-1);
  font: 15px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }
a { color: var(--marque); text-decoration: none; }
@media (prefers-color-scheme: dark) { a { color: #8fbfa9; } }
a:hover { text-decoration: underline; }
.serif { font-family: Fraunces, Georgia, "Times New Roman", serif; }

/* ---- Bandeau de marque ---- */
.masthead { background: var(--marque); color: var(--marque-encre); }
.masthead-inner { max-width: 1360px; margin: 0 auto; padding: 20px 24px 18px;
  display: flex; align-items: baseline; gap: 20px; flex-wrap: wrap; }
.wordmark { font-family: Fraunces, Georgia, serif; font-weight: 680; font-size: 30px;
  letter-spacing: .01em; margin: 0; }
.wordmark small { font-size: 13px; font-family: system-ui, sans-serif; font-weight: 400;
  opacity: .82; letter-spacing: .02em; margin-left: 12px; }
.masthead-stats { margin-left: auto; font-size: 13.5px; opacity: .95;
  font-variant-numeric: tabular-nums; }
.masthead-stats b { font-size: 16px; }
.masthead-stats .sep { opacity: .45; margin: 0 7px; }

.page { max-width: 1360px; margin: 0 auto; padding: 10px 24px 60px; }

/* ---- Filtres ---- */
.filtres { position: sticky; top: 0; z-index: 5; background: var(--plan);
  display: flex; align-items: end; gap: 14px; flex-wrap: wrap;
  padding: 12px 0; border-bottom: 1px solid var(--filet); margin-bottom: 6px; }
.filtre { display: flex; flex-direction: column; gap: 3px; }
.filtre label { font-size: 11.5px; color: var(--encre-3); text-transform: uppercase; letter-spacing: .05em; }
.filtre select, .filtre input { background: var(--surface); color: var(--encre-1);
  border: 1px solid var(--bord); border-radius: 7px; padding: 6px 8px; font: inherit; font-size: 14px; }
.filtre input[type=number] { width: 88px; }
.filtres .compteur { margin-left: auto; color: var(--encre-2); font-size: 13px; }
.filtres button { background: none; border: none; color: var(--marque); cursor: pointer;
  font: inherit; font-size: 13px; padding: 6px 0; text-decoration: underline; }
@media (prefers-color-scheme: dark) { .filtres button { color: #8fbfa9; } }

/* ---- Sections ---- */
h2.section { font-family: Fraunces, Georgia, serif; font-weight: 560; font-size: 19px;
  margin: 26px 0 12px; display: flex; align-items: baseline; gap: 10px; }
h2.section .nb { font: 600 12.5px system-ui, sans-serif; color: var(--encre-3); }
.note-vide { color: var(--encre-2); font-size: 14px; margin: 4px 0 8px; }

/* ---- Cartes ---- */
.carte { display: grid; grid-template-columns: 176px minmax(0,1fr) 250px 92px;
  gap: 16px; background: var(--surface); border: 1px solid var(--bord);
  border-radius: 12px; padding: 14px; margin-bottom: 12px; align-items: start; }
.carte.prio { background: var(--bande); border-color: var(--marque);
  box-shadow: 0 1px 0 var(--marque); }
.carte-img { height: 122px; border-radius: 8px; overflow: hidden;
  background: var(--gris-fond); display: flex; align-items: center; justify-content: center;
  font-size: 32px; color: var(--encre-3); }
.carte-img img { width: 100%; height: 100%; object-fit: cover; display: block; }
.carte-titre { font-size: 16px; font-weight: 600; margin: 0 0 2px; }
.carte-titre a { color: var(--encre-1); }
.carte-lieu { color: var(--encre-2); font-size: 13px; margin-bottom: 9px; }
.badges { display: inline-flex; gap: 6px; margin-left: 8px; vertical-align: 2px; flex-wrap: wrap; }
.badge { font-size: 11.5px; font-weight: 600; padding: 2px 8px; border-radius: 999px; white-space: nowrap; }
.badge-type { background: var(--gris-fond); color: var(--gris-texte); }
.badge-nouveau { background: var(--vert-fond); color: var(--vert-texte); }
.badge-alerte { background: var(--alerte-fond); color: var(--alerte-texte); }

.metriques { display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 10px; }
.metrique .libelle { font-size: 10.5px; text-transform: uppercase; letter-spacing: .05em; color: var(--encre-3); }
.metrique .valeur { font-size: 15px; font-weight: 600; font-variant-numeric: tabular-nums; }
.metrique .valeur small { font-weight: 400; color: var(--encre-2); }

/* Jauge marché : bande = fourchette locale, point = ce bien */
.marche { font-size: 12.5px; color: var(--encre-2); max-width: 460px; }
.marche-piste { position: relative; height: 14px; margin: 4px 0 2px; }
.marche-piste .ligne { position: absolute; top: 6px; left: 0; right: 0; height: 2px;
  background: var(--filet); border-radius: 2px; }
.marche-piste .bande-marche { position: absolute; top: 4px; height: 6px;
  background: color-mix(in srgb, var(--marque) 28%, transparent); border-radius: 3px; }
.marche-piste .mediane { position: absolute; top: 2px; width: 2px; height: 10px;
  background: var(--encre-3); }
.marche-piste .bien { position: absolute; top: 3px; width: 9px; height: 9px;
  border-radius: 50%; background: var(--marque); border: 2px solid var(--surface); }
.marche .decote-plus { color: var(--vert-texte); font-weight: 600; }
.marche .decote-moins { color: var(--alerte-texte); font-weight: 600; }

/* Pourquoi ce score */
.pourquoi { font-size: 12px; color: var(--encre-2); }
.pourquoi .titre-bloc { font-size: 10.5px; text-transform: uppercase; letter-spacing: .05em;
  color: var(--encre-3); margin-bottom: 5px; }
.jauge { display: grid; grid-template-columns: 92px 1fr 44px; gap: 7px; align-items: center;
  margin-bottom: 4px; }
.jauge .piste { height: 5px; background: var(--gris-fond); border-radius: 3px; overflow: hidden; }
.jauge .piste div { height: 100%; background: var(--marque); border-radius: 3px; }
.jauge .val { text-align: right; font-variant-numeric: tabular-nums; }
.bonus-ligne { margin-top: 3px; }

.carte-score { display: flex; flex-direction: column; align-items: center; gap: 5px; justify-content: center; }
.score { width: 62px; height: 62px; border-radius: 13px; display: flex; align-items: center;
  justify-content: center; font-family: Fraunces, Georgia, serif;
  font-size: 26px; font-weight: 680; font-variant-numeric: tabular-nums; }
.score.vert { background: var(--vert-fond); color: var(--vert-texte); }
.score.orange { background: var(--orange-fond); color: var(--orange-texte); }
.score.gris { background: var(--gris-fond); color: var(--gris-texte); }
.score-libelle { font-size: 10.5px; color: var(--encre-3); text-transform: uppercase; letter-spacing: .05em; }

/* Reste du marché : lignes compactes */
details.repli { margin-top: 22px; border-top: 1px solid var(--filet); padding-top: 12px; }
details.repli summary { cursor: pointer; color: var(--encre-2); font-weight: 600; font-size: 14px; }
.ligne-compacte { display: flex; gap: 12px; align-items: center; padding: 7px 2px;
  border-bottom: 1px solid var(--filet); font-size: 13.5px; }
.ligne-compacte .mini-score { flex: 0 0 34px; text-align: center; border-radius: 7px;
  font-weight: 700; font-variant-numeric: tabular-nums; padding: 2px 0; }
.ligne-compacte .t { flex: 1 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ligne-compacte .d { color: var(--encre-2); white-space: nowrap; font-variant-numeric: tabular-nums; }

.exclues table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13.5px; }
.exclues td { padding: 6px 10px 6px 0; border-bottom: 1px solid var(--filet); vertical-align: top; }
.exclues .raison { color: var(--encre-2); }

footer { margin-top: 32px; border-top: 1px solid var(--filet); padding-top: 14px;
  color: var(--encre-2); font-size: 13px; }
.sante { display: flex; gap: 18px; flex-wrap: wrap; margin: 6px 0; }
.sante .ok::before { content: "●"; color: #0ca30c; margin-right: 5px; }
.sante .erreur::before { content: "●"; color: #d03b3b; margin-right: 5px; }
.legende { color: var(--encre-3); }

@media (max-width: 1080px) {
  .carte { grid-template-columns: 176px minmax(0,1fr) 92px; }
  .carte .pourquoi { grid-column: 1 / -1; }
}
@media (max-width: 700px) {
  .carte { grid-template-columns: 1fr 92px; }
  .carte-img { grid-column: 1 / -1; height: 150px; }
}
</style>
</head>
<body>
<header class="masthead">
  <div class="masthead-inner">
    <h1 class="wordmark">Les Murs.<small>veille quotidienne — locaux commerciaux · Paris &amp; Île-de-France</small></h1>
    <div class="masthead-stats" id="masthead-stats"></div>
  </div>
</header>
<div class="page">

  <div class="filtres">
    <div class="filtre"><label for="f-type">Type</label>
      <select id="f-type">
        <option value="tous">Tous</option>
        <option value="murs_occupes">Murs occupés</option>
        <option value="murs_libres">Murs libres</option>
      </select></div>
    <div class="filtre"><label for="f-dep">Département</label>
      <select id="f-dep"><option value="tous">Tous</option></select></div>
    <div class="filtre"><label for="f-rdt">Rendement min (%)</label>
      <input id="f-rdt" type="number" min="0" max="15" step="0.5" placeholder="ex. 6"></div>
    <div class="filtre"><label for="f-score">Score min</label>
      <input id="f-score" type="number" min="0" max="100" step="5" placeholder="ex. 60"></div>
    <div class="filtre"><label for="f-nouv">Fraîcheur</label>
      <label style="font-size:14px;color:var(--encre-1);padding:6px 0"><input id="f-nouv" type="checkbox"> 🆕 seulement</label></div>
    <button id="f-reset" type="button">Réinitialiser</button>
    <span class="compteur" id="compteur"></span>
  </div>

  <section id="bloc-prio"></section>
  <section id="bloc-etudier"></section>
  <details class="repli" id="bloc-reste"><summary></summary><div id="reste-liste"></div></details>

  <details class="repli exclues" id="exclues-bloc">
    <summary></summary>
    <table id="exclues-table"></table>
  </details>

  <footer>
    <div><strong>Santé des sources</strong> — dernier passage : <span id="pied-maj"></span></div>
    <div class="sante" id="sante"></div>
    <div class="legende" id="legende"></div>
  </footer>
</div>

<script id="donnees" type="application/json">__DONNEES__</script>
<script>
"use strict";
const D = JSON.parse(document.getElementById("donnees").textContent);
const CLE_FILTRES = "veille-murs-filtres";
const LIBELLES_SCORE = {
  rendement: "Rendement", emplacement: "Emplacement",
  prix_m2_vs_benchmark: "Prix vs marché", proximite: "Trajet Paris 18e"
};

function ech(s) {
  return String(s ?? "").replace(/[&<>"']/g,
    c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}
const fmtEuros = n => n == null ? "—" :
  new Intl.NumberFormat("fr-FR", {maximumFractionDigits: 0}).format(n) + " €";
const fmtPct = n => n == null ? "—" :
  new Intl.NumberFormat("fr-FR", {maximumFractionDigits: 1}).format(n) + " %";
const fmtDate = d => d ? new Date(d).toLocaleDateString("fr-FR",
  {day: "numeric", month: "short", year: "numeric"}) : "—";

function classeScore(s) {
  if (s == null) return "gris";
  if (s >= D.seuils.vert) return "vert";
  if (s >= D.seuils.orange) return "orange";
  return "gris";
}

function jaugeMarcheHtml(a) {
  if (a.prix_m2 == null || a.marche_prix_m2_bas == null) return "";
  const bas = a.marche_prix_m2_bas, haut = a.marche_prix_m2_haut;
  const med = (bas + haut) / 2;
  const min = Math.min(bas, a.prix_m2) * 0.85, max = Math.max(haut, a.prix_m2) * 1.1;
  const pos = v => Math.max(0, Math.min(100, (v - min) / (max - min) * 100));
  let verdict;
  if (a.decote_pct >= 3) verdict = `<span class="decote-plus">≈ ${fmtPct(a.decote_pct)} sous le marché</span>`;
  else if (a.decote_pct <= -3) verdict = `<span class="decote-moins">≈ ${fmtPct(-a.decote_pct)} au-dessus du marché</span>`;
  else verdict = "dans le prix du marché";
  return `<div class="marche">
    <div>${fmtEuros(a.prix_m2)}/m² — ${verdict}</div>
    <div class="marche-piste">
      <div class="ligne"></div>
      <div class="bande-marche" style="left:${pos(bas)}%;width:${pos(haut) - pos(bas)}%"></div>
      <div class="mediane" style="left:${pos(med)}%" title="médiane locale ${fmtEuros(med)}/m²"></div>
      <div class="bien" style="left:calc(${pos(a.prix_m2)}% - 4px)" title="ce bien : ${fmtEuros(a.prix_m2)}/m²"></div>
    </div>
    <div>marché local : ${fmtEuros(bas)} – ${fmtEuros(haut)} /m² <span style="color:var(--encre-3)">(référentiel modifiable)</span></div>
  </div>`;
}

function pourquoiHtml(a) {
  const d = a.detail_score || {};
  const lignes = Object.entries(D.maxima).map(([cle, max]) => {
    const v = d[cle] ?? 0;
    return `<div class="jauge"><span>${LIBELLES_SCORE[cle]}</span>
      <div class="piste"><div style="width:${Math.max(0, Math.min(100, v / max * 100))}%"></div></div>
      <span class="val">${v}/${max}</span></div>`;
  });
  const bonus = d.bonus_malus ?? 0;
  const signe = bonus > 0 ? "+" : "";
  lignes.push(`<div class="bonus-ligne">Bonus/malus : <b>${signe}${bonus}</b> (bail récent, taxe foncière, travaux…)</div>`);
  return `<div class="pourquoi"><div class="titre-bloc">Pourquoi ce score</div>${lignes.join("")}</div>`;
}

function carteHtml(a, prio) {
  const badges = [];
  badges.push(`<span class="badge badge-type">${a.type_murs === "murs_occupes" ? "Murs occupés" : "Murs libres"}</span>`);
  if (a.est_nouvelle) badges.push('<span class="badge badge-nouveau">🆕 nouveau</span>');
  if ((a.flags || []).includes("rendement_anormalement_eleve"))
    badges.push('<span class="badge badge-alerte">⚠️ rendement à vérifier</span>');

  const img = a.image_url
    ? `<img src="${ech(a.image_url)}" alt="" loading="lazy" referrerpolicy="no-referrer"
         onerror="this.parentElement.textContent='🏪'">`
    : "🏪";

  const liens = (a.urls_multiples || []).map((u, i) =>
    ` · <a href="${ech(u)}" target="_blank" rel="noopener">aussi vu ici (${i + 2})</a>`).join("");

  const loyer = a.loyer_mensuel ?? a.loyer_mensuel_estime;
  const est = (a.loyer_mensuel == null && a.loyer_mensuel_estime != null) || a.loyer_estime
    ? " <small>est.</small>" : "";
  const metriques = [
    ["Prix", fmtEuros(a.prix)],
    ["Surface", a.surface_m2 == null ? "—" : new Intl.NumberFormat("fr-FR").format(a.surface_m2) + " m²"],
    ["Loyer/mois", loyer == null ? "—" : fmtEuros(loyer) + est],
    ["Rdt brut", fmtPct(a.rendement_brut_pct) + (a.rendement_brut_pct != null ? est : "")],
    ["Rdt acte en main", fmtPct(a.rendement_acte_en_main_pct)],
  ].map(([l, v]) =>
    `<div class="metrique"><div class="libelle">${l}</div><div class="valeur">${v}</div></div>`).join("");

  return `<article class="carte${prio ? " prio" : ""}">
    <div class="carte-img">${img}</div>
    <div>
      <div class="carte-titre"><a href="${ech(a.url)}" target="_blank" rel="noopener">${ech(a.titre)}</a>
        <span class="badges">${badges.join("")}</span></div>
      <div class="carte-lieu">${ech(a.ville)}${a.code_postal ? " (" + ech(a.code_postal) + ")" : ""}
        · détectée le ${fmtDate(a.date_premiere_vue)}${liens}</div>
      <div class="metriques">${metriques}</div>
      ${jaugeMarcheHtml(a)}
    </div>
    ${pourquoiHtml(a)}
    <div class="carte-score">
      <div class="score ${classeScore(a.score)}">${a.score ?? "—"}</div>
      <div class="score-libelle">score /100</div>
    </div>
  </article>`;
}

function ligneCompacteHtml(a) {
  const cls = classeScore(a.score);
  const fonds = {vert: "var(--vert-fond)", orange: "var(--orange-fond)", gris: "var(--gris-fond)"}[cls];
  const encres = {vert: "var(--vert-texte)", orange: "var(--orange-texte)", gris: "var(--gris-texte)"}[cls];
  return `<div class="ligne-compacte">
    <span class="mini-score" style="background:${fonds};color:${encres}">${a.score ?? "—"}</span>
    <span class="t"><a href="${ech(a.url)}" target="_blank" rel="noopener">${ech(a.titre)}</a></span>
    <span class="d">${ech(a.ville)} · ${fmtEuros(a.prix)} · rdt ${fmtPct(a.rendement_brut_pct)}</span>
  </div>`;
}

function filtres() {
  return {
    type: document.getElementById("f-type").value,
    dep: document.getElementById("f-dep").value,
    rdt: document.getElementById("f-rdt").value,
    score: document.getElementById("f-score").value,
    nouv: document.getElementById("f-nouv").checked,
  };
}

function appliquer(a, f) {
  if (f.type !== "tous" && a.type_murs !== f.type) return false;
  if (f.dep !== "tous" && a.departement !== f.dep) return false;
  if (f.rdt !== "" && (a.rendement_brut_pct == null || a.rendement_brut_pct < parseFloat(f.rdt))) return false;
  if (f.score !== "" && (a.score == null || a.score < parseFloat(f.score))) return false;
  if (f.nouv && !a.est_nouvelle) return false;
  return true;
}

function rendre() {
  const f = filtres();
  localStorage.setItem(CLE_FILTRES, JSON.stringify(f));
  const visibles = D.retenues.filter(a => appliquer(a, f));
  const prio = visibles.filter(a => (a.score ?? 0) >= D.seuils.vert);
  const etudier = visibles.filter(a => (a.score ?? 0) >= D.seuils.affichage && (a.score ?? 0) < D.seuils.vert);
  const reste = visibles.filter(a => (a.score ?? 0) < D.seuils.affichage);

  document.getElementById("bloc-prio").innerHTML =
    `<h2 class="section">🔥 À voir en priorité <span class="nb">score ≥ ${D.seuils.vert}</span></h2>` +
    (prio.length ? prio.map(a => carteHtml(a, true)).join("")
      : `<div class="note-vide">Rien au-dessus de ${D.seuils.vert} aujourd'hui — les meilleures du moment sont ci-dessous. Le stock grossit à chaque passage quotidien.</div>`);

  document.getElementById("bloc-etudier").innerHTML =
    `<h2 class="section">À étudier <span class="nb">score ${D.seuils.affichage}–${D.seuils.vert - 1}</span></h2>` +
    (etudier.length ? etudier.map(a => carteHtml(a, false)).join("")
      : '<div class="note-vide">Aucune annonce dans cette tranche avec ces filtres.</div>');

  const bloc = document.getElementById("bloc-reste");
  bloc.querySelector("summary").textContent =
    `Le reste du marché surveillé (${reste.length}) — score sous ${D.seuils.affichage}`;
  document.getElementById("reste-liste").innerHTML = reste.map(ligneCompacteHtml).join("");

  document.getElementById("compteur").textContent =
    `${visibles.length} / ${D.retenues.length} annonces`;
}

function initialiser() {
  const s = D.stats;
  document.getElementById("masthead-stats").innerHTML =
    `<b>${s.retenues}</b> en veille<span class="sep">·</span>` +
    `<b>${s.nouvelles}</b> nouvelle${s.nouvelles > 1 ? "s" : ""} (48 h)<span class="sep">·</span>` +
    `<b>${s.pepites}</b> pépite${s.pepites > 1 ? "s" : ""} 🔥<span class="sep">·</span>` +
    `<b>${s.exclues_recentes}</b> exclues (7 j)<span class="sep">·</span>` +
    `maj ${fmtDate(D.derniere_execution)}`;
  document.getElementById("pied-maj").textContent =
    new Date(D.derniere_execution).toLocaleString("fr-FR");

  const deps = [...new Set(D.retenues.map(a => a.departement).filter(Boolean))].sort();
  const selDep = document.getElementById("f-dep");
  for (const d of deps) selDep.insertAdjacentHTML("beforeend", `<option value="${d}">${d}</option>`);

  const bloc = document.getElementById("exclues-bloc");
  bloc.querySelector("summary").textContent =
    `Exclues cette semaine (${D.exclues_recentes.length}) — pourquoi le filtre les a écartées`;
  document.getElementById("exclues-table").innerHTML = D.exclues_recentes.map(e =>
    `<tr><td>${fmtDate(e.date_derniere_vue)}</td>
     <td><a href="${ech(e.url)}" target="_blank" rel="noopener">${ech(e.titre)}</a><br>
     <span class="raison">${ech(e.ville)} — ${ech(e.raison)}</span></td></tr>`).join("");

  document.getElementById("sante").innerHTML = Object.entries(D.sante).map(([nom, x]) => {
    const detail = x.statut === "ok"
      ? `${x.annonces} annonces` + (x.avertissements ? " · " + ech(x.avertissements.join(" ; ")) : "")
      : ech(x.message || "erreur");
    return `<span class="${x.statut === "ok" ? "ok" : "erreur"}">${ech(nom)} — ${detail}</span>`;
  }).join("");

  document.getElementById("legende").textContent =
    `Score /100 : ≥ ${D.seuils.vert} bon dossier · ${D.seuils.orange}–${D.seuils.vert - 1} à étudier · ` +
    `< ${D.seuils.orange} faible. Un score ≥ ${D.seuils.pepite} déclenche l'email « pépite ». ` +
    `⚠️ = rendement anormalement élevé, vérifier locataire et quartier. ` +
    `« est. » = loyer estimé d'après le référentiel local (data/benchmarks.json, modifiable).`;

  try {
    const memo = JSON.parse(localStorage.getItem(CLE_FILTRES) || "{}");
    if (memo.type) document.getElementById("f-type").value = memo.type;
    if (memo.dep && [...selDep.options].some(o => o.value === memo.dep))
      document.getElementById("f-dep").value = memo.dep;
    if (memo.rdt) document.getElementById("f-rdt").value = memo.rdt;
    if (memo.score) document.getElementById("f-score").value = memo.score;
    if (memo.nouv) document.getElementById("f-nouv").checked = true;
  } catch (e) { /* filtres mémorisés illisibles : on repart à zéro */ }

  for (const id of ["f-type", "f-dep", "f-rdt", "f-score", "f-nouv"])
    document.getElementById(id).addEventListener("input", rendre);
  document.getElementById("f-reset").addEventListener("click", () => {
    localStorage.removeItem(CLE_FILTRES);
    document.getElementById("f-type").value = "tous";
    document.getElementById("f-dep").value = "tous";
    document.getElementById("f-rdt").value = "";
    document.getElementById("f-score").value = "";
    document.getElementById("f-nouv").checked = false;
    rendre();
  });
  rendre();
}
initialiser();
</script>
</body>
</html>
"""
