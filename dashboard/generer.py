"""Génération du dashboard statique (docs/index.html), publié par GitHub Pages.

Un seul fichier HTML autonome (CSS/JS inclus, données embarquées en JSON) :
rien à builder, consultable aussi en local en ouvrant le fichier. Le site est
non référencé (meta noindex + docs/robots.txt).

La préparation des données (tri, badge nouveau < 48 h, exclues < 7 jours,
hors-zone agrégé, lecture du prix) est faite en Python pour être testable ;
le JavaScript ne fait que filtrer/afficher.

Identité « Les Murs. » : devanture de boutique parisienne — store scalloped
sous le bandeau, pictogrammes SVG tracés à la main (pas d'emoji), tampons
encrés pour le podium, or réservé aux trophées. Mobile : filtres repliés,
comparateur et jauges de score masqués. Animations coupées si
prefers-reduced-motion.
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
_HORS_ZONE = "hors Île-de-France"


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
                "caracteristiques": a.caracteristiques,
                "decote_pct": a.decote_pct,
                "marche_prix_m2_bas": a.marche_prix_m2_bas,
                "marche_prix_m2_haut": a.marche_prix_m2_haut,
                "lecture_prix": a.lecture_prix,
                "temps_trajet_min": a.temps_trajet_min,
                "image_url": a.image_url,
                "date_premiere_vue": a.date_premiere_vue,
                "est_nouvelle": _iso(a.date_premiere_vue) >= seuil_nouveaute,
            }
        )

    # Exclusions récentes : le hors-zone est compté mais pas détaillé — seules
    # les exclusions instructives (prix, fonds déguisé, trajet) ont une ligne.
    exclues_recentes = [
        a for a in annonces.values()
        if a.exclue and _iso(a.date_derniere_vue) >= seuil_exclues
    ]
    exclues_detail = [
        {
            "titre": a.titre,
            "url": a.url,
            "ville": a.ville,
            "raison": a.raison_exclusion,
            "date_derniere_vue": a.date_derniere_vue,
        }
        for a in sorted(exclues_recentes, key=lambda a: a.date_derniere_vue, reverse=True)
        if not (a.raison_exclusion or "").startswith(_HORS_ZONE)
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
        "maxima": {
            "rendement": scoring["rendement"]["points"],
            "emplacement": scoring["emplacement"]["paris"],
            "prix_m2_vs_benchmark": scoring["prix_m2_vs_benchmark"]["decote_forte"],
            "proximite": scoring["proximite"]["moins_de_20_min"],
            "quartier": scoring["quartier"]["points"],
        },
        "stats": {
            "retenues": len(retenues),
            "nouvelles": sum(1 for a in retenues if a["est_nouvelle"]),
            "pepites": sum(1 for a in retenues if (a["score"] or 0) >= seuils["pepite"]),
            "analysees": len(retenues) + len(exclues_recentes),
            "exclues_recentes": len(exclues_recentes),
            "exclues_hors_zone": len(exclues_recentes) - len(exclues_detail),
        },
        "retenues": retenues,
        "exclues_recentes": exclues_detail,
        "encheres": meta.get("encheres", []),
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
<title>Les Murs — carnet de chasse</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,560;0,9..144,700;1,9..144,500&display=swap" rel="stylesheet">
<style>
:root {
  --plan: #f6f6f1; --surface: #fdfdfa;
  --marque: #1d5240; --marque-fonce: #143a2d; --marque-encre: #f2efe4;
  --or: #a87c1f; --or-clair: #f4e5bd; --or-vif: #d6a532;
  --encre-1: #171a16; --encre-2: #4e544e; --encre-3: #82887e;
  --filet: #e3e3da; --bord: rgba(20, 30, 20, .12);
  --vert-fond: #e3efe4; --vert-texte: #1c5e2a;
  --orange-fond: #f9edd2; --orange-texte: #8a5a00;
  --gris-fond: #ecede7; --gris-texte: #4e544e;
  --alerte-fond: #f9e6dc; --alerte-texte: #98351b;
  --bande: #eef4ef;
}
@media (prefers-color-scheme: dark) {
  :root {
    --plan: #101210; --surface: #191c19;
    --marque: #1d5240; --marque-fonce: #0f2c22; --marque-encre: #eceade;
    --or: #d6a532; --or-clair: #3a2f10; --or-vif: #e7bc4e;
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
svg.ic { width: 1em; height: 1em; vertical-align: -.12em; fill: none;
  stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }

/* ---- Bandeau + store de devanture ---- */
.masthead { background: linear-gradient(115deg, var(--marque-fonce), var(--marque) 55%, var(--marque-fonce));
  color: var(--marque-encre); }
.masthead-inner { max-width: 1380px; margin: 0 auto; padding: 20px 24px 14px;
  display: flex; align-items: center; gap: 18px; flex-wrap: wrap; }
.enseigne { display: flex; align-items: center; gap: 14px; }
.enseigne svg { width: 40px; height: 40px; color: var(--or-vif); }
.wordmark { font-family: Fraunces, Georgia, serif; font-weight: 700; font-size: 34px;
  letter-spacing: .01em; margin: 0; line-height: 1; }
.wordmark .point { color: var(--or-vif); }
.wordmark .trait { display: block; margin-top: 4px; }
.hud { margin-left: auto; display: flex; gap: 8px; flex-wrap: wrap; align-items: center;
  font-size: 13px; font-variant-numeric: tabular-nums; }
.hud .puce { background: rgba(255,255,255,.09); border: 1px solid rgba(255,255,255,.16);
  border-radius: 999px; padding: 4px 12px; white-space: nowrap; display: inline-flex;
  align-items: center; gap: 6px; }
.hud b { font-size: 15px; }
.hud .maj { opacity: .75; }
.auvent { height: 15px; background: repeating-linear-gradient(90deg,
    var(--marque) 0 26px, var(--marque-fonce) 26px 52px);
  -webkit-mask: radial-gradient(13px at 13px 0, #000 97%, #0000) 0 0 / 26px 15px repeat-x;
  mask: radial-gradient(13px at 13px 0, #000 97%, #0000) 0 0 / 26px 15px repeat-x; }

.page { max-width: 1380px; margin: 0 auto; padding: 10px 24px 90px; }

/* ---- Filtres (repliables sur mobile) ---- */
.volet-filtres { position: sticky; top: 0; z-index: 5; background: var(--plan);
  border-bottom: 1px solid var(--filet); margin-bottom: 4px; }
.volet-filtres > summary { display: none; cursor: pointer; padding: 10px 0;
  font-weight: 600; color: var(--encre-2); list-style: none; }
.volet-filtres > summary::-webkit-details-marker { display: none; }
.filtres { display: flex; align-items: end; gap: 14px; flex-wrap: wrap; padding: 12px 0; }
.filtre { display: flex; flex-direction: column; gap: 3px; }
.filtre label { font-size: 11px; color: var(--encre-3); text-transform: uppercase; letter-spacing: .06em; }
.filtre select, .filtre input { background: var(--surface); color: var(--encre-1);
  border: 1px solid var(--bord); border-radius: 7px; padding: 6px 8px; font: inherit; font-size: 14px; }
.filtre input[type=number] { width: 86px; }
.filtres .compteur { margin-left: auto; color: var(--encre-2); font-size: 13px; }
.filtres button { background: none; border: none; color: var(--marque); cursor: pointer;
  font: inherit; font-size: 13px; padding: 6px 0; text-decoration: underline; }
@media (prefers-color-scheme: dark) { .filtres button { color: #8fbfa9; } }

/* ---- Sections ---- */
h2.section { font-family: Fraunces, Georgia, serif; font-weight: 560; font-size: 21px;
  margin: 28px 0 12px; display: flex; align-items: baseline; gap: 10px; }
h2.section svg.ic { color: var(--or); font-size: 19px; }
h2.section .nb { font: 600 12px system-ui, sans-serif; color: var(--encre-3);
  text-transform: uppercase; letter-spacing: .05em; }
.note-vide { color: var(--encre-2); font-size: 14px; margin: 4px 0 8px;
  background: var(--surface); border: 1px dashed var(--filet); border-radius: 10px; padding: 14px 16px; }

/* ---- Cartes ---- */
@keyframes surgir { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }
.carte { display: grid; grid-template-columns: 176px minmax(0,1fr) 265px 96px;
  gap: 16px; background: var(--surface); border: 1px solid var(--bord);
  border-radius: 12px; padding: 14px; margin-bottom: 12px; align-items: start;
  animation: surgir .4s ease both; transition: transform .15s ease, box-shadow .15s ease; }
.carte:hover { transform: translateY(-2px); box-shadow: 0 6px 18px rgba(15, 40, 25, .10); }
.carte.prio { background: var(--bande); border-color: var(--marque); }
.carte.podium-1 { border-color: var(--or); box-shadow: 0 0 0 1px var(--or); }
.tampon { display: inline-block; font-family: Fraunces, Georgia, serif; font-weight: 700;
  font-size: 11px; letter-spacing: .1em; text-transform: uppercase;
  color: var(--or); border: 2px solid var(--or); border-radius: 6px;
  padding: 2px 9px; transform: rotate(-2.5deg); box-shadow: inset 0 0 0 1.5px var(--surface),
  inset 0 0 0 3px var(--or); background: var(--or-clair); margin-bottom: 7px; }
.carte-img { height: 124px; border-radius: 8px; overflow: hidden;
  background: var(--gris-fond); display: flex; align-items: center; justify-content: center;
  color: var(--encre-3); }
.carte-img svg { width: 54px; height: 54px; opacity: .5; }
.carte-img img { width: 100%; height: 100%; object-fit: cover; display: block; }
.carte-titre { font-size: 16px; font-weight: 600; margin: 0 0 2px; }
.carte-titre a { color: var(--encre-1); }
.carte-lieu { color: var(--encre-2); font-size: 13px; margin-bottom: 7px; }
.badges { display: inline-flex; gap: 6px; margin-left: 8px; vertical-align: 2px; flex-wrap: wrap; }
.badge { font-size: 11.5px; font-weight: 600; padding: 2px 8px; border-radius: 999px; white-space: nowrap; }
.badge-type { background: var(--gris-fond); color: var(--gris-texte); }
.badge-nouveau { background: var(--vert-fond); color: var(--vert-texte); }
.badge-alerte { background: var(--alerte-fond); color: var(--alerte-texte); }
.etiquettes { display: flex; gap: 6px; flex-wrap: wrap; margin: 0 0 9px; }
.etiquette { font-size: 11.5px; color: var(--encre-2); border: 1px solid var(--filet);
  border-radius: 6px; padding: 1px 7px; background: var(--plan); }

.metriques { display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 10px; }
.metrique .libelle { font-size: 10.5px; text-transform: uppercase; letter-spacing: .05em; color: var(--encre-3); }
.metrique .valeur { font-size: 15px; font-weight: 600; font-variant-numeric: tabular-nums; }
.metrique .valeur small { font-weight: 400; color: var(--encre-2); }

/* Jauge marché + lecture du prix */
.marche { font-size: 12.5px; color: var(--encre-2); max-width: 480px; }
.marche-piste { position: relative; height: 14px; margin: 4px 0 2px; }
.marche-piste .ligne { position: absolute; top: 6px; left: 0; right: 0; height: 2px;
  background: var(--filet); border-radius: 2px; }
.marche-piste .bande-marche { position: absolute; top: 4px; height: 6px;
  background: color-mix(in srgb, var(--marque) 30%, transparent); border-radius: 3px; }
.marche-piste .mediane { position: absolute; top: 2px; width: 2px; height: 10px; background: var(--encre-3); }
.marche-piste .bien { position: absolute; top: 3px; width: 9px; height: 9px;
  border-radius: 50%; background: var(--marque); border: 2px solid var(--surface); }
.marche .bon { color: var(--vert-texte); font-weight: 600; }
.marche .mauvais { color: var(--alerte-texte); font-weight: 600; }
.lecture { font-style: italic; color: var(--encre-2); margin-top: 5px;
  border-left: 3px solid var(--or); padding-left: 8px; }

/* Pourquoi ce score */
.pourquoi { font-size: 12px; color: var(--encre-2); }
.pourquoi .titre-bloc { font-size: 10.5px; text-transform: uppercase; letter-spacing: .06em;
  color: var(--encre-3); margin-bottom: 6px; }
.jauge { display: grid; grid-template-columns: 96px 1fr 44px; gap: 7px; align-items: center; margin-bottom: 5px; }
.jauge .piste { height: 7px; background: var(--gris-fond); border-radius: 4px; overflow: hidden; }
.jauge .piste div { height: 100%; width: 0;
  background: linear-gradient(90deg, var(--marque), #3f8f6b); border-radius: 4px;
  transition: width .7s cubic-bezier(.2,.7,.3,1); }
.jauge .val { text-align: right; font-variant-numeric: tabular-nums; }

.carte-score { display: flex; flex-direction: column; align-items: center; gap: 5px; justify-content: start; }
.rang { font-family: Fraunces, Georgia, serif; font-weight: 700; font-size: 15px;
  width: 30px; height: 30px; border-radius: 50%; display: flex; align-items: center; justify-content: center; }
.rang-S { background: var(--or-clair); color: var(--or); box-shadow: 0 0 0 2px var(--or); }
.rang-A { background: var(--vert-fond); color: var(--vert-texte); box-shadow: 0 0 0 2px var(--vert-texte); }
.rang-B { background: var(--orange-fond); color: var(--orange-texte); }
.rang-C { background: var(--gris-fond); color: var(--gris-texte); }
.score { width: 64px; height: 64px; border-radius: 14px; display: flex; align-items: center;
  justify-content: center; font-family: Fraunces, Georgia, serif;
  font-size: 27px; font-weight: 700; font-variant-numeric: tabular-nums; }
.score.vert { background: var(--vert-fond); color: var(--vert-texte); }
.score.orange { background: var(--orange-fond); color: var(--orange-texte); }
.score.gris { background: var(--gris-fond); color: var(--gris-texte); }
.score-libelle { font-size: 10px; color: var(--encre-3); text-transform: uppercase; letter-spacing: .05em; }
.btn-comp { font: 600 11.5px system-ui, sans-serif; color: var(--marque);
  background: var(--plan); border: 1px solid var(--bord); border-radius: 7px;
  padding: 4px 9px; cursor: pointer; margin-top: 4px; display: inline-flex; gap: 5px; align-items: center; }
.btn-comp.actif { background: var(--marque); color: var(--marque-encre); border-color: var(--marque); }

/* Rangées compactes */
details.repli { margin-top: 24px; border-top: 1px solid var(--filet); padding-top: 12px; }
details.repli summary { cursor: pointer; color: var(--encre-2); font-weight: 600; font-size: 14px; }
.ligne-compacte { display: flex; gap: 12px; align-items: center; padding: 7px 2px;
  border-bottom: 1px solid var(--filet); font-size: 13.5px; }
.ligne-compacte .mini-score { flex: 0 0 34px; text-align: center; border-radius: 7px;
  font-weight: 700; font-variant-numeric: tabular-nums; padding: 2px 0; }
.ligne-compacte .t { flex: 1 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ligne-compacte .d { color: var(--encre-2); white-space: nowrap; font-variant-numeric: tabular-nums; }

/* Enchères */
.enchere { display: flex; gap: 14px; align-items: baseline; padding: 9px 2px;
  border-bottom: 1px solid var(--filet); font-size: 14px; flex-wrap: wrap; }
.enchere .date { flex: 0 0 auto; font-weight: 700; font-variant-numeric: tabular-nums;
  color: var(--or); font-family: Fraunces, Georgia, serif; }
.enchere .t { flex: 1 1 320px; min-width: 0; }
.enchere .d { color: var(--encre-2); white-space: nowrap; font-variant-numeric: tabular-nums; }
.note-encheres { font-size: 12.5px; color: var(--encre-3); margin-top: 8px; }

.exclues table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13.5px; }
.exclues td { padding: 6px 10px 6px 0; border-bottom: 1px solid var(--filet); vertical-align: top; }
.exclues .raison { color: var(--encre-2); }

/* Comparateur */
.plateau { position: fixed; bottom: 16px; left: 50%; transform: translateX(-50%);
  background: var(--marque-fonce); color: var(--marque-encre); border: 1px solid var(--or);
  border-radius: 999px; padding: 9px 18px; font-size: 14px; display: none; z-index: 20;
  box-shadow: 0 8px 24px rgba(0,0,0,.25); }
.plateau button { background: none; border: none; color: var(--or-vif); font: inherit;
  font-weight: 700; cursor: pointer; margin-left: 10px; }
.comparateur-fond { position: fixed; inset: 0; background: rgba(10, 20, 14, .55);
  display: none; z-index: 30; padding: 4vh 3vw; }
.comparateur { background: var(--surface); border-radius: 14px; max-width: 1180px;
  margin: 0 auto; max-height: 92vh; overflow: auto; padding: 20px 24px; }
.comparateur h3 { font-family: Fraunces, Georgia, serif; margin: 0 0 12px; font-size: 22px; }
.comparateur table { border-collapse: collapse; width: 100%; font-size: 13.5px; }
.comparateur th, .comparateur td { border-bottom: 1px solid var(--filet); padding: 7px 12px 7px 0;
  text-align: left; vertical-align: top; font-variant-numeric: tabular-nums; }
.comparateur th { color: var(--encre-3); font-weight: 600; white-space: nowrap; width: 130px; }
.comparateur .meilleur { color: var(--vert-texte); font-weight: 700; }
.comparateur img { width: 130px; height: 84px; object-fit: cover; border-radius: 7px; }
.comparateur .fermer { float: right; background: var(--gris-fond); border: none;
  border-radius: 8px; padding: 6px 12px; cursor: pointer; font: 600 13px system-ui, sans-serif;
  color: var(--encre-1); }

footer { margin-top: 34px; border-top: 1px solid var(--filet); padding-top: 14px;
  color: var(--encre-2); font-size: 13px; }
.sante { display: flex; gap: 18px; flex-wrap: wrap; margin: 6px 0; }
.sante .ok::before { content: "●"; color: #0ca30c; margin-right: 5px; }
.sante .erreur::before { content: "●"; color: #d03b3b; margin-right: 5px; }
.legende { color: var(--encre-3); }

/* ---- Mobile : on allège ---- */
@media (max-width: 1100px) {
  .carte { grid-template-columns: 176px minmax(0,1fr) 96px; }
  .carte .pourquoi { grid-column: 1 / -1; }
}
@media (max-width: 760px) {
  .page { padding: 8px 14px 40px; }
  .masthead-inner { padding: 14px 16px 10px; }
  .wordmark { font-size: 26px; }
  .hud, .btn-comp, .plateau, .carte .pourquoi { display: none !important; }
  .volet-filtres > summary { display: block; }
  .carte { grid-template-columns: 1fr 84px; gap: 12px; padding: 12px; }
  .carte-img { grid-column: 1 / -1; height: 150px; }
  .metriques { gap: 12px 18px; }
  .score { width: 54px; height: 54px; font-size: 23px; }
  .comparateur-fond { display: none !important; }
}
@media (prefers-reduced-motion: reduce) {
  * { animation: none !important; transition: none !important; }
}
</style>
</head>
<body>
<header class="masthead">
  <div class="masthead-inner">
    <div class="enseigne">
      <svg viewBox="0 0 48 48" aria-hidden="true"><path d="M8 20v20h32V20"/><path d="M8 40h32"/><path d="M14 40V28h8v12"/><rect x="27" y="28" width="9" height="7" rx="1"/><path d="M4 20c0-2 1-8 4-8h32c3 0 4 6 4 8"/><path d="M4 20c0 2.2 2 4 4.5 4S13 22.2 13 20c0 2.2 2 4 4.5 4s4.5-1.8 4.5-4c0 2.2 2 4 4.5 4s4.5-1.8 4.5-4c0 2.2 2 4 4.5 4s4.5-1.8 4.5-4c0 2.2 2 4 4.5 4S44 22.2 44 20"/></svg>
      <h1 class="wordmark">Les Murs<span class="point">.</span>
        <svg class="trait" width="128" height="7" viewBox="0 0 128 7" aria-hidden="true"><path d="M2 4.5 C 24 1.5, 40 6, 64 3.5 S 108 5.5, 126 2.5" stroke="var(--or-vif)" stroke-width="2.2" fill="none" stroke-linecap="round"/></svg>
      </h1>
    </div>
    <div class="hud" id="hud"></div>
  </div>
</header>
<div class="auvent" aria-hidden="true"></div>
<div class="page">

  <details class="volet-filtres" id="volet-filtres">
    <summary>Filtres &amp; réglages ▾</summary>
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
        <label style="font-size:14px;color:var(--encre-1);padding:6px 0"><input id="f-nouv" type="checkbox"> Nouveautés seulement</label></div>
      <button id="f-reset" type="button">Réinitialiser</button>
      <span class="compteur" id="compteur"></span>
    </div>
  </details>

  <section id="bloc-prio"></section>
  <section id="bloc-etudier"></section>
  <details class="repli" id="bloc-reste"><summary></summary><div id="reste-liste"></div></details>

  <section id="bloc-encheres"></section>

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

<div class="plateau" id="plateau"></div>
<div class="comparateur-fond" id="comparateur-fond">
  <div class="comparateur">
    <button class="fermer" id="comp-fermer">Fermer ✕</button>
    <h3>Face à face</h3>
    <div id="comp-table"></div>
  </div>
</div>

<script id="donnees" type="application/json">__DONNEES__</script>
<script>
"use strict";
const D = JSON.parse(document.getElementById("donnees").textContent);
const CLE_FILTRES = "veille-murs-filtres";
const CLE_COMP = "veille-murs-comparateur";
const LIBELLES_SCORE = {
  rendement: "Rendement", emplacement: "Emplacement",
  prix_m2_vs_benchmark: "Prix vs marché", proximite: "Trajet 18e", quartier: "Quartier 18e"
};
const TAMPONS = ["Nº 1 du jour", "Nº 2", "Nº 3"];

/* Pictogrammes tracés (pas d'emoji) */
const IC = {
  boutique: '<svg class="ic" viewBox="0 0 24 24"><path d="M4 10v10h16V10"/><path d="M7 20v-6h4v6"/><rect x="13.5" y="14" width="4.5" height="3.5" rx=".8"/><path d="M2 10c0-1 .6-4 2-4h16c1.4 0 2 3 2 4"/><path d="M2 10c0 1.2 1 2.2 2.5 2.2S7 11.2 7 10c0 1.2 1 2.2 2.5 2.2S12 11.2 12 10c0 1.2 1 2.2 2.5 2.2S17 11.2 17 10c0 1.2 1 2.2 2.5 2.2S22 11.2 22 10"/></svg>',
  etincelle: '<svg class="ic" viewBox="0 0 24 24"><path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M18 6l-2.5 2.5M8.5 15.5 6 18"/></svg>',
  pepite: '<svg class="ic" viewBox="0 0 24 24"><path d="M7 4h10l4 6-9 10L3 10Z"/><path d="M3 10h18M12 20 8.5 10l2-6M12 20l3.5-10-2-6"/></svg>',
  cible: '<svg class="ic" viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r="1" fill="currentColor"/></svg>',
  marteau: '<svg class="ic" viewBox="0 0 24 24"><path d="m9.5 7 6 6M13 3.5 19.5 10M11 5.5 17.5 12M12.5 9.5l-8.5 8.5a1.6 1.6 0 0 0 2.3 2.3L14.8 12"/><path d="M13 21h8"/></svg>',
  balance: '<svg class="ic" viewBox="0 0 24 24"><path d="M12 4v16M6 4.8 18 4M7 20h10"/><path d="M6 5 3 12h6L6 5ZM18 4l-3 7h6l-3-7Z"/></svg>',
  loupe: '<svg class="ic" viewBox="0 0 24 24"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m15.5 15.5 5 5"/></svg>',
  trophee: '<svg class="ic" viewBox="0 0 24 24"><path d="M7 4h10v5a5 5 0 0 1-10 0Z"/><path d="M7 5H4c0 3 1.3 4.8 3 5M17 5h3c0 3-1.3 4.8-3 5M12 14v3M8.5 20h7M10 17h4"/></svg>',
  alerte: '<svg class="ic" viewBox="0 0 24 24"><path d="M12 4 2.5 20h19L12 4Z"/><path d="M12 10v5M12 17.5v.5"/></svg>',
  horloge: '<svg class="ic" viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5"/><path d="M12 7v5l3.5 2"/></svg>'
};

let comparaison = [];
try { comparaison = JSON.parse(localStorage.getItem(CLE_COMP) || "[]"); } catch (e) {}

function ech(s) {
  return String(s ?? "").replace(/[&<>"']/g,
    c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}
const fmtEuros = n => n == null ? "—" :
  new Intl.NumberFormat("fr-FR", {maximumFractionDigits: 0}).format(n) + " €";
const fmtPct = n => n == null ? "—" :
  new Intl.NumberFormat("fr-FR", {maximumFractionDigits: 1}).format(n) + " %";
const fmtDate = d => d ? new Date(d).toLocaleDateString("fr-FR",
  {day: "numeric", month: "short"}) : "—";

function classeScore(s) {
  if (s == null) return "gris";
  if (s >= D.seuils.vert) return "vert";
  if (s >= D.seuils.orange) return "orange";
  return "gris";
}
function rang(s) {
  if (s == null) return "C";
  if (s >= D.seuils.pepite) return "S";
  if (s >= D.seuils.vert) return "A";
  if (s >= D.seuils.orange) return "B";
  return "C";
}

function verdictMarche(a) {
  if (a.prix_m2 < a.marche_prix_m2_bas)
    return '<span class="bon">sous la fourchette du marché</span>';
  if (a.prix_m2 > a.marche_prix_m2_haut)
    return '<span class="mauvais">au-dessus du marché local</span>';
  return a.decote_pct >= 0
    ? '<span class="bon">dans la fourchette, moitié basse</span>'
    : "dans la fourchette, moitié haute";
}

function jaugeMarcheHtml(a) {
  if (a.prix_m2 == null || a.marche_prix_m2_bas == null) return "";
  const bas = a.marche_prix_m2_bas, haut = a.marche_prix_m2_haut;
  const med = (bas + haut) / 2;
  const min = Math.min(bas, a.prix_m2) * 0.85, max = Math.max(haut, a.prix_m2) * 1.1;
  const pos = v => Math.max(0, Math.min(100, (v - min) / (max - min) * 100));
  const lecture = a.lecture_prix ? `<div class="lecture">${ech(a.lecture_prix)}</div>` : "";
  return `<div class="marche">
    <div>${fmtEuros(a.prix_m2)}/m² — ${verdictMarche(a)}
      <span style="color:var(--encre-3)" title="écart à la médiane locale">(${a.decote_pct >= 0 ? "-" : "+"}${fmtPct(Math.abs(a.decote_pct))} vs médiane)</span></div>
    <div class="marche-piste">
      <div class="ligne"></div>
      <div class="bande-marche" style="left:${pos(bas)}%;width:${pos(haut) - pos(bas)}%"></div>
      <div class="mediane" style="left:${pos(med)}%" title="médiane locale ${fmtEuros(med)}/m²"></div>
      <div class="bien" style="left:calc(${pos(a.prix_m2)}% - 4px)" title="ce bien : ${fmtEuros(a.prix_m2)}/m²"></div>
    </div>
    <div>marché local : ${fmtEuros(bas)} – ${fmtEuros(haut)} /m²</div>
    ${lecture}
  </div>`;
}

function pourquoiHtml(a) {
  const d = a.detail_score || {};
  const lignes = Object.entries(D.maxima).map(([cle, max]) => {
    const v = d[cle] ?? 0;
    return `<div class="jauge"><span>${LIBELLES_SCORE[cle]}</span>
      <div class="piste"><div data-l="${Math.max(0, Math.min(100, v / max * 100))}"></div></div>
      <span class="val">${v}/${max}</span></div>`;
  });
  const bonus = d.bonus_malus ?? 0;
  lignes.push(`<div class="jauge"><span>Bonus/malus</span><span></span>
    <span class="val">${bonus > 0 ? "+" : ""}${bonus}/5</span></div>`);
  return `<div class="pourquoi"><div class="titre-bloc">Pourquoi ce score</div>${lignes.join("")}</div>`;
}

function carteHtml(a, options) {
  const badges = [];
  badges.push(`<span class="badge badge-type">${a.type_murs === "murs_occupes" ? "Murs occupés" : "Murs libres"}</span>`);
  if (a.est_nouvelle) badges.push(`<span class="badge badge-nouveau">${IC.etincelle} nouveau</span>`);
  if ((a.flags || []).includes("rendement_anormalement_eleve"))
    badges.push(`<span class="badge badge-alerte">${IC.alerte} rendement à vérifier</span>`);

  const img = a.image_url
    ? `<img src="${ech(a.image_url)}" alt="" loading="lazy" referrerpolicy="no-referrer"
         onerror="this.parentElement.innerHTML=IC.boutique">`
    : IC.boutique;

  const liens = (a.urls_multiples || []).map((u, i) =>
    ` · <a href="${ech(u)}" target="_blank" rel="noopener">aussi vu ici (${i + 2})</a>`).join("");

  const etiquettes = (a.caracteristiques || []).map(c =>
    `<span class="etiquette">${ech(c)}</span>`).join("");

  const loyer = a.loyer_mensuel ?? a.loyer_mensuel_estime;
  const est = (a.loyer_mensuel == null && a.loyer_mensuel_estime != null) || a.loyer_estime
    ? " <small>est.</small>" : "";
  const metriques = [
    ["Prix", fmtEuros(a.prix)],
    ["Surface", a.surface_m2 == null ? "—" : new Intl.NumberFormat("fr-FR").format(a.surface_m2) + " m²"],
    ["Loyer/mois", loyer == null ? "—" : fmtEuros(loyer) + est],
    ["Rdt brut", fmtPct(a.rendement_brut_pct) + (a.rendement_brut_pct != null ? est : "")],
    ["Rdt acte en main", fmtPct(a.rendement_acte_en_main_pct)],
    ["Trajet 18e", a.temps_trajet_min == null ? "—" : "≈ " + a.temps_trajet_min + " min"],
  ].map(([l, v]) =>
    `<div class="metrique"><div class="libelle">${l}</div><div class="valeur">${v}</div></div>`).join("");

  const tampon = options.medaille != null
    ? `<div><span class="tampon">${TAMPONS[options.medaille]}</span></div>` : "";
  const lettreRang = rang(a.score);
  const dansComp = comparaison.includes(a.id);

  return `<article class="carte${options.prio ? " prio" : ""}${options.medaille === 0 ? " podium-1" : ""}"
      style="animation-delay:${(options.index || 0) * 45}ms">
    <div class="carte-img">${img}</div>
    <div>
      ${tampon}
      <div class="carte-titre"><a href="${ech(a.url)}" target="_blank" rel="noopener">${ech(a.titre)}</a>
        <span class="badges">${badges.join("")}</span></div>
      <div class="carte-lieu">${ech(a.ville)}${a.code_postal ? " (" + ech(a.code_postal) + ")" : ""}
        · détectée le ${fmtDate(a.date_premiere_vue)}${liens}</div>
      ${etiquettes ? `<div class="etiquettes">${etiquettes}</div>` : ""}
      <div class="metriques">${metriques}</div>
      ${jaugeMarcheHtml(a)}
    </div>
    ${pourquoiHtml(a)}
    <div class="carte-score">
      <span class="rang rang-${lettreRang}" title="Rang ${lettreRang} — S ≥ ${D.seuils.pepite}, A ≥ ${D.seuils.vert}, B ≥ ${D.seuils.orange}">${lettreRang}</span>
      <div class="score ${classeScore(a.score)}">${a.score ?? "—"}</div>
      <div class="score-libelle">/100</div>
      <button type="button" class="btn-comp${dansComp ? " actif" : ""}" data-id="${ech(a.id)}">
        ${IC.balance} ${dansComp ? "Comparé" : "Comparer"}</button>
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

function enchereHtml(e) {
  const date = e.date_vente
    ? new Date(e.date_vente).toLocaleDateString("fr-FR", {day: "numeric", month: "short"})
    : "date ?";
  const m2 = e.prix_m2_mise_a_prix ? ` · ${fmtEuros(e.prix_m2_mise_a_prix)}/m² (mise à prix)` : "";
  return `<div class="enchere">
    <span class="date">${IC.horloge} ${date}</span>
    <span class="t"><a href="${ech(e.url)}" target="_blank" rel="noopener">${ech(e.titre)}</a></span>
    <span class="d">dépt ${ech(e.departement)} · mise à prix ${fmtEuros(e.mise_a_prix)}${m2} · ${ech(e.type_vente)}</span>
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

  const podium = [...prio, ...etudier].slice(0, 3).map(a => a.id);
  const opts = a => ({
    prio: (a.score ?? 0) >= D.seuils.vert,
    medaille: podium.indexOf(a.id) >= 0 ? podium.indexOf(a.id) : null,
  });

  let index = 0;
  document.getElementById("bloc-prio").innerHTML =
    `<h2 class="section">${IC.trophee} Le haut du panier <span class="nb">score ≥ ${D.seuils.vert}</span></h2>` +
    (prio.length ? prio.map(a => carteHtml(a, {...opts(a), index: index++})).join("")
      : `<div class="note-vide">Aucun trophée au-dessus de ${D.seuils.vert} aujourd'hui — les mieux classées sont ci-dessous.
         La chasse reprend chaque matin à 7 h ; une pépite (≥ ${D.seuils.pepite}) déclenchera un email immédiat.</div>`);

  document.getElementById("bloc-etudier").innerHTML =
    `<h2 class="section">${IC.loupe} À étudier de près <span class="nb">score ${D.seuils.affichage}–${D.seuils.vert - 1}</span></h2>` +
    (etudier.length ? etudier.map(a => carteHtml(a, {...opts(a), index: index++})).join("")
      : '<div class="note-vide">Rien dans cette tranche avec ces filtres.</div>');

  const bloc = document.getElementById("bloc-reste");
  bloc.querySelector("summary").textContent =
    `Le reste du tableau de chasse (${reste.length}) — score sous ${D.seuils.affichage}`;
  document.getElementById("reste-liste").innerHTML = reste.map(ligneCompacteHtml).join("");

  document.getElementById("compteur").textContent =
    `${visibles.length} / ${D.retenues.length} annonces`;

  requestAnimationFrame(() => {
    document.querySelectorAll(".piste div[data-l]").forEach(el => { el.style.width = el.dataset.l + "%"; });
  });
  majPlateau();
}

/* ---- Comparateur (bureau uniquement) ---- */
function majPlateau() {
  const plateau = document.getElementById("plateau");
  if (comparaison.length === 0) { plateau.style.display = "none"; return; }
  plateau.style.display = "block";
  plateau.innerHTML = `${IC.balance} ${comparaison.length} bien${comparaison.length > 1 ? "s" : ""} sélectionné${comparaison.length > 1 ? "s" : ""}
    <button type="button" id="comp-ouvrir" ${comparaison.length < 2 ? "disabled style='opacity:.5'" : ""}>Face à face</button>
    <button type="button" id="comp-vider">Vider</button>`;
}

function basculerComparaison(id) {
  const i = comparaison.indexOf(id);
  if (i >= 0) comparaison.splice(i, 1);
  else if (comparaison.length < 4) comparaison.push(id);
  localStorage.setItem(CLE_COMP, JSON.stringify(comparaison));
  rendre();
}

function ouvrirComparateur() {
  const biens = comparaison.map(id => D.retenues.find(a => a.id === id)).filter(Boolean);
  if (biens.length < 2) return;
  const meilleur = fn => Math.max(...biens.map(fn).filter(v => v != null && !isNaN(v)));
  const lignes = [
    ["", b => b.image_url ? `<img src="${ech(b.image_url)}" referrerpolicy="no-referrer" onerror="this.remove()">` : IC.boutique],
    ["Annonce", b => `<a href="${ech(b.url)}" target="_blank" rel="noopener">${ech(b.titre)}</a><br>
       <span style="color:var(--encre-3)">${ech(b.ville)} (${ech(b.code_postal)})</span>`],
    ["Score", b => {
      const top = (b.score ?? -1) === meilleur(x => x.score);
      return `<span class="${top ? "meilleur" : ""}">${b.score} /100 · rang ${rang(b.score)}</span>`;
    }],
    ["Prix", b => fmtEuros(b.prix)],
    ["Prix/m²", b => `${fmtEuros(b.prix_m2)} <span style="color:var(--encre-3)">(marché ${fmtEuros(b.marche_prix_m2_bas)}–${fmtEuros(b.marche_prix_m2_haut)})</span>`],
    ["Lecture du prix", b => ech(b.lecture_prix || "—")],
    ["Surface", b => b.surface_m2 == null ? "—" : b.surface_m2 + " m²"],
    ["Loyer/mois", b => {
      const l = b.loyer_mensuel ?? b.loyer_mensuel_estime;
      return l == null ? "—" : fmtEuros(l) + (b.loyer_mensuel == null || b.loyer_estime ? " (est.)" : "");
    }],
    ["Rendement brut", b => {
      const top = (b.rendement_brut_pct ?? -1) === meilleur(x => x.rendement_brut_pct);
      return `<span class="${top ? "meilleur" : ""}">${fmtPct(b.rendement_brut_pct)}</span>`;
    }],
    ["Rdt acte en main", b => fmtPct(b.rendement_acte_en_main_pct)],
    ["Écart à la médiane", b => b.decote_pct == null ? "—" :
      (b.decote_pct >= 0 ? `<span class="meilleur">-${fmtPct(b.decote_pct)}</span>` : `+${fmtPct(-b.decote_pct)}`)],
    ["Trajet Paris 18e", b => b.temps_trajet_min == null ? "—" : `≈ ${b.temps_trajet_min} min`],
    ["Type", b => b.type_murs === "murs_occupes" ? "Murs occupés" : "Murs libres"],
    ["Atouts", b => (b.caracteristiques || []).join(" · ") || "—"],
    ["", b => `<button type="button" class="btn-comp" data-id="${ech(b.id)}">Retirer</button>`],
  ];
  document.getElementById("comp-table").innerHTML = "<table>" + lignes.map(([titre, fn]) =>
    `<tr><th>${titre}</th>${biens.map(b => `<td>${fn(b)}</td>`).join("")}</tr>`).join("") + "</table>";
  document.getElementById("comparateur-fond").style.display = "block";
}

document.addEventListener("click", ev => {
  const btn = ev.target.closest(".btn-comp");
  if (btn) {
    basculerComparaison(btn.dataset.id);
    if (document.getElementById("comparateur-fond").style.display === "block") ouvrirComparateur();
    return;
  }
  if (ev.target.id === "comp-ouvrir") ouvrirComparateur();
  if (ev.target.id === "comp-vider") { comparaison = []; localStorage.setItem(CLE_COMP, "[]"); rendre(); }
  if (ev.target.id === "comp-fermer" || ev.target.id === "comparateur-fond")
    document.getElementById("comparateur-fond").style.display = "none";
});

function initialiser() {
  // Filtres ouverts d'office sur grand écran, repliés sur mobile
  if (window.innerWidth > 760) document.getElementById("volet-filtres").open = true;

  const s = D.stats;
  document.getElementById("hud").innerHTML =
    `<span class="puce">${IC.etincelle} <b>${s.nouvelles}</b> nouvelle${s.nouvelles > 1 ? "s" : ""} (48 h)</span>` +
    `<span class="puce">${IC.pepite} <b>${s.pepites}</b> pépite${s.pepites > 1 ? "s" : ""}</span>` +
    `<span class="puce">${IC.cible} <b>${s.analysees}</b> passées au crible (7 j)</span>` +
    `<span class="maj">maj ${fmtDate(D.derniere_execution)}</span>`;
  document.getElementById("pied-maj").textContent =
    new Date(D.derniere_execution).toLocaleString("fr-FR");

  const deps = [...new Set(D.retenues.map(a => a.departement).filter(Boolean))].sort();
  const selDep = document.getElementById("f-dep");
  for (const d of deps) selDep.insertAdjacentHTML("beforeend", `<option value="${d}">${d}</option>`);

  const encheres = D.encheres || [];
  document.getElementById("bloc-encheres").innerHTML = encheres.length
    ? `<h2 class="section">${IC.marteau} Sous le marteau <span class="nb">${encheres.length} vente${encheres.length > 1 ? "s" : ""} aux enchères à venir en IdF</span></h2>` +
      encheres.map(enchereHtml).join("") +
      `<div class="note-encheres">La mise à prix n'est pas le prix final (comptez souvent 1,5× à 3×).
       Enchérir en salle exige un avocat et une consignation (~10 %). Section informative, hors scoring.</div>`
    : "";

  const bloc = document.getElementById("exclues-bloc");
  bloc.querySelector("summary").textContent =
    `Écartées cette semaine : ${s.exclues_recentes}, dont ${s.exclues_hors_zone} hors Île-de-France — ` +
    `détail des ${D.exclues_recentes.length} écartées dans la zone`;
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
    `Barème /100 : rendement 40 + emplacement 25 + prix vs marché 20 + trajet 5 + quartier 18e 5 ` +
    `+ bonus/malus (−3 à +5, plafonné à 100). Rangs : S ≥ ${D.seuils.pepite} (pépite, email immédiat), ` +
    `A ≥ ${D.seuils.vert}, B ≥ ${D.seuils.orange}, C en dessous. Un rendement > 10 % est plafonné ` +
    `sous ${D.seuils.affichage} (piège probable) jusqu'à vérification. ` +
    `« est. » = loyer estimé ou promis, non prouvé par un bail.`;

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
