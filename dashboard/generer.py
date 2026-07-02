"""Génération du dashboard statique (docs/index.html), publié par GitHub Pages.

Un seul fichier HTML autonome (CSS/JS inclus, données embarquées en JSON) :
rien à builder, consultable aussi en local en ouvrant le fichier. Le site est
non référencé (meta noindex + docs/robots.txt).

La préparation des données (tri, badge 🆕 < 48 h, exclues < 7 jours) est faite
ici en Python pour être testable ; le JavaScript ne fait que filtrer/afficher.
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
                "loyer_estime": a.loyer_estime,
                "rendement_brut_pct": a.rendement_brut_pct,
                "rendement_acte_en_main_pct": a.rendement_acte_en_main_pct,
                "score": a.score,
                "detail_score": a.detail_score,
                "flags": a.flags,
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

    seuils = config.scoring["seuils"]
    return {
        "genere_le": maintenant.isoformat(timespec="seconds"),
        "derniere_execution": meta.get("derniere_execution", ""),
        "seuils": {
            "vert": seuils["vert"],
            "orange": seuils["orange"],
            "pepite": seuils["pepite"],
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
<title>Veille murs commerciaux</title>
<style>
:root {
  --plan: #f9f9f7; --surface: #fcfcfb;
  --encre-1: #0b0b0b; --encre-2: #52514e; --encre-3: #898781;
  --filet: #e1e0d9; --bord: rgba(11,11,11,0.10);
  --vert-fond: #e6f4e6; --vert-texte: #006300;
  --orange-fond: #fdf0d5; --orange-texte: #8a5a00;
  --gris-fond: #efeeea; --gris-texte: #52514e;
  --alerte-fond: #fdeae2; --alerte-texte: #99331a;
  --accent: #2a78d6;
}
@media (prefers-color-scheme: dark) {
  :root {
    --plan: #0d0d0d; --surface: #1a1a19;
    --encre-1: #ffffff; --encre-2: #c3c2b7; --encre-3: #898781;
    --filet: #2c2c2a; --bord: rgba(255,255,255,0.10);
    --vert-fond: #12300f; --vert-texte: #6fd06f;
    --orange-fond: #38290a; --orange-texte: #f0bd58;
    --gris-fond: #262624; --gris-texte: #c3c2b7;
    --alerte-fond: #3a1c12; --alerte-texte: #f0a186;
    --accent: #3987e5;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--plan); color: var(--encre-1);
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  font-size: 15px; line-height: 1.45;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
.page { max-width: 1180px; margin: 0 auto; padding: 24px 20px 60px; }

header.entete { display: flex; align-items: baseline; justify-content: space-between; flex-wrap: wrap; gap: 8px; }
.entete h1 { font-size: 22px; margin: 0; }
.entete .maj { color: var(--encre-3); font-size: 13px; }

.tuiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin: 18px 0; }
.tuile { background: var(--surface); border: 1px solid var(--bord); border-radius: 10px; padding: 12px 16px; }
.tuile .libelle { color: var(--encre-3); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }
.tuile .valeur { font-size: 26px; font-weight: 650; margin-top: 2px; }
.tuile .valeur small { font-size: 14px; font-weight: 500; color: var(--encre-2); }

.filtres { position: sticky; top: 0; z-index: 5; background: var(--plan);
  display: flex; align-items: end; gap: 14px; flex-wrap: wrap;
  padding: 12px 0; border-bottom: 1px solid var(--filet); margin-bottom: 16px; }
.filtre { display: flex; flex-direction: column; gap: 3px; }
.filtre label { font-size: 12px; color: var(--encre-3); }
.filtre select, .filtre input { background: var(--surface); color: var(--encre-1);
  border: 1px solid var(--bord); border-radius: 7px; padding: 6px 8px; font: inherit; font-size: 14px; }
.filtre input[type=number] { width: 90px; }
.filtres .compteur { margin-left: auto; color: var(--encre-2); font-size: 13px; }
.filtres button { background: none; border: none; color: var(--accent); cursor: pointer; font: inherit; font-size: 13px; padding: 6px 0; }

.carte { display: flex; gap: 16px; background: var(--surface); border: 1px solid var(--bord);
  border-radius: 12px; padding: 14px; margin-bottom: 12px; }
.carte-img { flex: 0 0 168px; height: 118px; border-radius: 8px; overflow: hidden;
  background: var(--gris-fond); display: flex; align-items: center; justify-content: center;
  font-size: 34px; color: var(--encre-3); }
.carte-img img { width: 100%; height: 100%; object-fit: cover; display: block; }
.carte-corps { flex: 1 1 auto; min-width: 0; }
.carte-titre { font-size: 16px; font-weight: 600; margin: 0 0 2px; }
.carte-titre a { color: var(--encre-1); }
.carte-lieu { color: var(--encre-2); font-size: 13px; margin-bottom: 10px; }
.badges { display: inline-flex; gap: 6px; margin-left: 8px; vertical-align: 2px; flex-wrap: wrap; }
.badge { font-size: 11.5px; font-weight: 600; padding: 2px 8px; border-radius: 999px; white-space: nowrap; }
.badge-type { background: var(--gris-fond); color: var(--gris-texte); }
.badge-nouveau { background: var(--vert-fond); color: var(--vert-texte); }
.badge-alerte { background: var(--alerte-fond); color: var(--alerte-texte); }

.metriques { display: flex; gap: 22px; flex-wrap: wrap; }
.metrique .libelle { font-size: 11px; text-transform: uppercase; letter-spacing: .04em; color: var(--encre-3); }
.metrique .valeur { font-size: 15px; font-weight: 600; font-variant-numeric: tabular-nums; }
.metrique .valeur small { font-weight: 400; color: var(--encre-2); }

.carte-score { flex: 0 0 auto; display: flex; flex-direction: column; align-items: center; gap: 6px; justify-content: center; }
.score { width: 56px; height: 56px; border-radius: 12px; display: flex; align-items: center; justify-content: center;
  font-size: 22px; font-weight: 700; font-variant-numeric: tabular-nums; cursor: default; }
.score.vert { background: var(--vert-fond); color: var(--vert-texte); }
.score.orange { background: var(--orange-fond); color: var(--orange-texte); }
.score.gris { background: var(--gris-fond); color: var(--gris-texte); }
.score-libelle { font-size: 11px; color: var(--encre-3); }

.vide { text-align: center; color: var(--encre-2); padding: 40px 0; }

details.exclues { margin-top: 28px; border-top: 1px solid var(--filet); padding-top: 14px; }
details.exclues summary { cursor: pointer; color: var(--encre-2); font-weight: 600; }
.exclues table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13.5px; }
.exclues td { padding: 6px 10px 6px 0; border-bottom: 1px solid var(--filet); vertical-align: top; }
.exclues .raison { color: var(--encre-2); }

footer { margin-top: 32px; border-top: 1px solid var(--filet); padding-top: 14px;
  color: var(--encre-2); font-size: 13px; }
.sante { display: flex; gap: 18px; flex-wrap: wrap; margin: 6px 0; }
.sante .ok::before { content: "●"; color: #0ca30c; margin-right: 5px; }
.sante .erreur::before { content: "●"; color: #d03b3b; margin-right: 5px; }
.legende { color: var(--encre-3); }
@media (max-width: 720px) {
  .carte { flex-wrap: wrap; }
  .carte-img { flex-basis: 100%; height: 150px; }
  .carte-score { flex-direction: row; }
}
</style>
</head>
<body>
<div class="page">
  <header class="entete">
    <h1>🏪 Veille murs commerciaux — Paris &amp; Île-de-France</h1>
    <span class="maj" id="maj"></span>
  </header>

  <div class="tuiles" id="tuiles"></div>

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
    <div class="filtre"><label for="f-nouv">&nbsp;</label>
      <label style="font-size:14px;color:var(--encre-1)"><input id="f-nouv" type="checkbox"> 🆕 seulement</label></div>
    <button id="f-reset" type="button">Réinitialiser</button>
    <span class="compteur" id="compteur"></span>
  </div>

  <main id="liste"></main>

  <details class="exclues" id="exclues-bloc">
    <summary></summary>
    <table id="exclues-table"></table>
  </details>

  <footer>
    <div><strong>Santé des sources</strong> — dernier passage : <span id="pied-maj"></span></div>
    <div class="sante" id="sante"></div>
    <div class="legende">Score /100 : <span style="color:var(--vert-texte)">■</span> ≥ <span class="s-vert"></span> bon dossier ·
      <span style="color:var(--orange-texte)">■</span> <span class="s-orange"></span>–<span class="s-vert-moins"></span> à étudier ·
      <span style="color:var(--gris-texte)">■</span> &lt; <span class="s-orange2"></span> faible.
      ⚠️ = rendement anormalement élevé, vérifier locataire et quartier. Loyers « est. » = estimés au marché local.</div>
  </footer>
</div>

<script id="donnees" type="application/json">__DONNEES__</script>
<script>
"use strict";
const D = JSON.parse(document.getElementById("donnees").textContent);
const CLE_FILTRES = "veille-murs-filtres";
const LIBELLES_SCORE = {
  rendement: "Rendement", emplacement: "Emplacement",
  prix_m2_vs_benchmark: "Prix/m² vs marché", proximite: "Proximité Paris 18e",
  bonus_malus: "Bonus/malus"
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

function infobulleScore(a) {
  const lignes = Object.entries(a.detail_score || {})
    .map(([k, v]) => `${LIBELLES_SCORE[k] || k} : ${v}`);
  return lignes.join("\\n");
}

function carteHtml(a) {
  const badges = [];
  badges.push(`<span class="badge badge-type">${a.type_murs === "murs_occupes" ? "Murs occupés" : "Murs libres"}</span>`);
  if (a.est_nouvelle) badges.push('<span class="badge badge-nouveau">🆕 nouveau</span>');
  if ((a.flags || []).includes("rendement_anormalement_eleve"))
    badges.push('<span class="badge badge-alerte">⚠️ rendement à vérifier</span>');

  const img = a.image_url
    ? `<img src="${ech(a.image_url)}" alt="" loading="lazy" onerror="this.parentElement.textContent='🏪'">`
    : "🏪";

  const liens = (a.urls_multiples || []).map((u, i) =>
    ` · <a href="${ech(u)}" target="_blank" rel="noopener">aussi vu ici (${i + 2})</a>`).join("");

  const est = a.loyer_estime ? " <small>est.</small>" : "";
  const metriques = [
    ["Prix", fmtEuros(a.prix)],
    ["Prix/m²", a.prix_m2 == null ? "—" : fmtEuros(a.prix_m2)],
    ["Surface", a.surface_m2 == null ? "—" : new Intl.NumberFormat("fr-FR").format(a.surface_m2) + " m²"],
    ["Loyer/mois", a.loyer_mensuel == null ? "—" : fmtEuros(a.loyer_mensuel) + est],
    ["Rdt brut", fmtPct(a.rendement_brut_pct) + est],
    ["Rdt acte en main", fmtPct(a.rendement_acte_en_main_pct)],
  ].map(([l, v]) =>
    `<div class="metrique"><div class="libelle">${l}</div><div class="valeur">${v}</div></div>`).join("");

  return `<article class="carte">
    <div class="carte-img">${img}</div>
    <div class="carte-corps">
      <div class="carte-titre"><a href="${ech(a.url)}" target="_blank" rel="noopener">${ech(a.titre)}</a>
        <span class="badges">${badges.join("")}</span></div>
      <div class="carte-lieu">${ech(a.ville)}${a.code_postal ? " (" + ech(a.code_postal) + ")" : ""}
        · détectée le ${fmtDate(a.date_premiere_vue)}${liens}</div>
      <div class="metriques">${metriques}</div>
    </div>
    <div class="carte-score">
      <div class="score ${classeScore(a.score)}" title="${ech(infobulleScore(a))}">${a.score ?? "—"}</div>
      <div class="score-libelle">score /100</div>
    </div>
  </article>`;
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
  document.getElementById("liste").innerHTML = visibles.length
    ? visibles.map(carteHtml).join("")
    : '<div class="vide">Aucune annonce ne passe ces filtres. Élargissez les critères ou revenez demain 🙂</div>';
  document.getElementById("compteur").textContent =
    `${visibles.length} / ${D.retenues.length} annonces`;
}

function initialiser() {
  document.getElementById("maj").textContent = "Mis à jour le " + fmtDate(D.derniere_execution);
  document.getElementById("pied-maj").textContent =
    new Date(D.derniere_execution).toLocaleString("fr-FR");

  const tuiles = [
    ["En veille", D.stats.retenues, ""],
    ["Nouvelles (48 h)", D.stats.nouvelles, ""],
    ["Pépites 🔥 (≥ " + D.seuils.pepite + ")", D.stats.pepites, ""],
    ["Exclues (7 j)", D.stats.exclues_recentes, ""],
  ];
  document.getElementById("tuiles").innerHTML = tuiles.map(([l, v]) =>
    `<div class="tuile"><div class="libelle">${l}</div><div class="valeur">${v}</div></div>`).join("");

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

  document.getElementById("sante").innerHTML = Object.entries(D.sante).map(([nom, s]) => {
    const detail = s.statut === "ok"
      ? `${s.annonces} annonces` + (s.avertissements ? " · " + ech(s.avertissements.join(" ; ")) : "")
      : ech(s.message || "erreur");
    return `<span class="${s.statut === "ok" ? "ok" : "erreur"}">${ech(nom)} — ${detail}</span>`;
  }).join("");

  document.querySelectorAll(".s-vert").forEach(e => e.textContent = D.seuils.vert);
  document.querySelectorAll(".s-vert-moins").forEach(e => e.textContent = D.seuils.vert - 1);
  document.querySelectorAll(".s-orange, .s-orange2").forEach(e => e.textContent = D.seuils.orange);

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
