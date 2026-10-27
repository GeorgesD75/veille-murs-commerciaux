"""Génération du dashboard statique (docs/index.html), publié par GitHub Pages.

Un seul fichier HTML autonome (CSS/JS inclus, données embarquées en JSON) :
rien à builder, consultable aussi en local en ouvrant le fichier. Le site est
non référencé (meta noindex + docs/robots.txt).

La préparation des données (tri, badge nouveau < 48 h, exclues < 7 jours,
hors-zone agrégé, lecture du prix) est faite en Python pour être testable ;
le JavaScript ne fait que filtrer/afficher.

Identité « Les Murs. » : enseigne verte et dorée, devanture et annonces dès
le premier écran. Filtres et analyse repliés ; signal discret pour les pépites,
y compris hors des préférences de surface/trajet. Animations coupées si
prefers-reduced-motion.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from dashboard.dossier_banque import generer_dossiers
from pipeline.config import Config
from pipeline.decision import analyser_decision, est_pepite, priorite_recherche
from pipeline.contact import message_negociation, messages_contact
from pipeline.negociation import plan_negociation
from pipeline.modeles import Annonce

HEURES_NOUVEAUTE = 48
JOURS_EXCLUES = 7
# Annonce plus revue en ligne depuis ce délai : probablement vendue ou retirée
# (3 tournées/jour = ~42 passages manqués, une panne de source ne dure pas si
# longtemps). Elle n'est jamais supprimée, mais reléguée et signalée : perdre
# du temps sur un bien déjà vendu est le pire gaspillage pour un investisseur.
JOURS_PEUT_ETRE_RETIREE = 14
_HORS_ZONE = "hors Île-de-France"


def _iso(date: str) -> datetime:
    return datetime.fromisoformat(date)


def preparer_payload(
    annonces: dict[str, Annonce],
    meta: dict[str, Any],
    config: Config,
    maintenant: datetime,
    dossiers: dict[str, str] | None = None,
    marche: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Données embarquées dans la page, prêtes à afficher."""
    seuil_nouveaute = maintenant - timedelta(hours=HEURES_NOUVEAUTE)
    seuil_exclues = maintenant - timedelta(days=JOURS_EXCLUES)
    seuil_retiree = maintenant - timedelta(days=JOURS_PEUT_ETRE_RETIREE)

    # Une source actuellement EN PANNE ne revoit aucune de ses annonces : sans
    # ce garde-fou, un site qui change de structure ferait basculer tout son
    # stock en « peut-être vendue » à tort au bout de 14 jours.
    sante = meta.get("sante_sources", {})
    modeles_contact: list[str] = []
    index_modeles: dict[str, int] = {}

    def contact_compact(a):
        resultat = {}
        for mode, texte in messages_contact(a).items():
            texte = texte.replace(f"{a.titre} à {a.ville}", "__REFERENCE__").replace(a.url, "__URL__")
            if a.loyer_mensuel:
                texte = texte.replace(f"{a.loyer_mensuel:,.0f}".replace(",", " ") + " €/mois", "__LOYER__")
            if texte not in index_modeles:
                index_modeles[texte] = len(modeles_contact)
                modeles_contact.append(texte)
            resultat[mode] = index_modeles[texte]
        return resultat

    def _source_en_panne(source: str) -> bool:
        cle = "imap" if source.startswith("alerte_") else source
        etat = sante.get(cle)
        return bool(etat) and etat.get("statut") != "ok"

    retenues = []
    for a in sorted(
        (a for a in annonces.values() if not a.exclue),
        key=lambda a: (a.score or 0),
        reverse=True,
    ):
        negociation = plan_negociation(a, config, maintenant)
        decision = analyser_decision(a, config)
        if negociation["prix_plafond"] is not None:
            negociation["message"] = message_negociation(a, negociation)
        retenues.append(
            {
                "id": a.id,
                "pepite": est_pepite(a, config) and _iso(a.date_derniere_vue) >= seuil_retiree
                    and decision["relocation"]["niveau"] != "vigilance",
                "recherche": priorite_recherche(a, config),
                "decision": decision,
                "negociation": negociation,
                "modeles_contact": contact_compact(a),
                "etat_detail": a.etat_detail,
                "date_detail_vue": a.date_detail_vue,
                "titre": a.titre,
                "source": a.source,
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
                "honoraires": a.honoraires,
                "loyer_mensuel_estime": a.loyer_mensuel_estime,
                "loyer_estime": a.loyer_estime,
                "loyer_confiance": a.loyer_confiance,
                "loyer_nb_comparables": a.loyer_nb_comparables,
                "rendement_brut_pct": a.rendement_brut_pct,
                "rendement_acte_en_main_pct": a.rendement_acte_en_main_pct,
                "score": a.score,
                "detail_score": a.detail_score,
                "flags": a.flags,
                "bonus_detectes": a.bonus_detectes,
                "fiscalite_detectes": a.fiscalite_detectes,
                "caracteristiques": a.caracteristiques,
                "decote_pct": a.decote_pct,
                "marche_prix_m2_bas": a.marche_prix_m2_bas,
                "marche_prix_m2_median": a.marche_prix_m2_median,
                "marche_prix_m2_haut": a.marche_prix_m2_haut,
                "benchmark_source": a.benchmark_source,
                "dpe_classe": a.dpe_classe,
                "bail_echeance_annee": a.bail_echeance_annee,
                "emplacement_numero": a.emplacement_numero,
                "taxe_fonciere_annuelle": a.taxe_fonciere_annuelle,
                "lecture_prix": a.lecture_prix,
                "prix_cible_rendement": a.prix_cible_rendement,
                "temps_trajet_min": a.temps_trajet_min,
                "historique_prix": a.historique_prix,
                "rue_categorie": a.rue_categorie,
                "rue_voie": a.rue_voie,
                "rue_nb_commerces": a.rue_nb_commerces,
                "rue_nb_vacants": a.rue_nb_vacants,
                "rue_distance_metro_m": a.rue_distance_metro_m,
                "critique_ia": a.critique_ia,
                "image_url": a.image_url,
                "images": a.images,
                "date_premiere_vue": a.date_premiere_vue,
                "date_derniere_vue": a.date_derniere_vue,
                "est_nouvelle": _iso(a.date_premiere_vue) >= seuil_nouveaute,
                "jours_sans_vue": (maintenant - _iso(a.date_derniere_vue)).days,
                "peut_etre_retiree": a.etat_detail == "retiree" or (_iso(a.date_derniere_vue) < seuil_retiree
                                     and not _source_en_panne(a.source)),
                # classeur Excel « dossier banque », si généré pour ce bien
                "dossier": f"dossiers/{dossiers[a.id]}" if dossiers and a.id in dossiers and not decision["diagnostic"]["bloquant"] else None,
            }
        )

    # Rang parmi les annonces encore VUES en ligne (la liste est triée par score
    # décroissant) : répond à « est-ce mieux que les autres vues cette semaine ? ».
    # Une annonce probablement retirée ne prend pas de rang — un bien vendu qui
    # occuperait la 1re place fausserait toute la comparaison.
    rang = 0
    for a in retenues:
        if a["peut_etre_retiree"] or a["decision"]["diagnostic"]["transaction"]["nature"] != "murs":
            a["rang_score"] = None
        else:
            rang += 1
            a["rang_score"] = rang

    # Nombre d'autres annonces retenues dans le même secteur (code postal) :
    # peu de comparables = valorisation plus incertaine, à dire honnêtement.
    compte_secteur: dict[str, int] = {}
    for a in retenues:
        if a["decision"]["diagnostic"]["transaction"]["nature"] == "murs":
            compte_secteur[a["code_postal"]] = compte_secteur.get(a["code_postal"], 0) + 1
    for a in retenues:
        a["nb_comparables_secteur"] = max(0, compte_secteur.get(a["code_postal"], 0) - int(a["decision"]["diagnostic"]["transaction"]["nature"] == "murs"))

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
            "financement": scoring["financement"]["points"],
            "fiscalite": scoring["fiscalite"]["points"],
            "proximite": scoring["proximite"]["moins_de_20_min"],
            "quartier": scoring["quartier"]["points"],
        },
        "stats": {
            # « retenues » = encore vues en ligne : c'est le dénominateur du
            # classement affiché (« se classe Xᵉ sur Y ») — les annonces
            # probablement retirées n'y comptent pas.
            "retenues": rang,
            "nouvelles": sum(1 for a in retenues if a["est_nouvelle"] and not a["peut_etre_retiree"] and a["decision"]["diagnostic"]["transaction"]["nature"] == "murs"),
            "pepites": sum(1 for a in retenues if a["pepite"]),
            "analysees": len(retenues) + len(exclues_recentes),
            "exclues_recentes": len(exclues_recentes),
            "exclues_hors_zone": len(exclues_recentes) - len(exclues_detail),
            "encheres_ecartees": meta.get("encheres_ecartees", 0),
        },
        "retenues": retenues,
        "modeles_contact": modeles_contact,
        "recherche": config.donnees.get("recherche", {"surface_max_m2": 40, "trajet_cible_min": 30}),
        "exclues_recentes": exclues_detail,
        "encheres": meta.get("encheres", []),
        "analyse": config["analyse"],
        "taux_marche": meta.get("taux_marche"),
        "sante": meta.get("sante_sources", {}),
        "collecte_ciblee": meta.get("collecte_ciblee"),
        "enrichissement_detail": meta.get("enrichissement_detail"),
        "qualite_donnees": {"fiches_tracees": sum(a.etat_detail == "lu" for a in annonces.values()),
                            "listes_ecartees": sum(a.etat_detail == "redirection_liste" for a in annonces.values()),
                            "nettoyage": meta.get("nettoyage_fiches")},
        "marche": marche,
    }


def generer_html(payload: dict[str, Any]) -> str:
    donnees = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    scripts = "\n".join((Path(__file__).parent / nom).read_text(encoding="utf-8")
                        for nom in ["reponses_moteur.js", "reponses_interface.js"])
    return _GABARIT.replace("__REPONSES_VENDEUR__", scripts).replace("__DONNEES__", donnees)


def generer_dashboard(
    annonces: dict[str, Annonce],
    meta: dict[str, Any],
    config: Config,
    dossier: Path,
    maintenant: datetime | None = None,
    marche: dict[str, Any] | None = None,
) -> Path:
    maintenant = maintenant or datetime.now().astimezone()
    dossier.mkdir(parents=True, exist_ok=True)
    # Dossiers banque Excel d'abord : le payload référence leurs fichiers.
    dossiers_banque = generer_dossiers(annonces, config, dossier / "dossiers")
    payload = preparer_payload(annonces, meta, config, maintenant, dossiers_banque, marche=marche)
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
:focus-visible { outline: 3px solid var(--or); outline-offset: 3px; }
.recherche-intro { display:flex; justify-content:space-between; gap:24px; align-items:center;
  padding:22px 0 12px; }
.recherche-intro h2 { font: 700 clamp(24px, 4vw, 34px)/1.15 Fraunces, Georgia, serif; margin:0 0 8px; }
.recherche-intro p { margin:0; color:var(--encre-2); max-width:680px; }
.recherche-chiffres { display:flex; gap:22px; flex-shrink:0; }
.recherche-chiffres strong { display:block; font-size:26px; color:var(--vert-texte); }
.recherche-chiffres span { font-size:12px; color:var(--encre-2); }
.decision { background:var(--bande); border:1px solid var(--filet); border-radius:10px; padding:12px 14px; margin:14px 0; }
.decision p { margin:5px 0; font-size:13px; }
.decision summary { cursor:pointer; font-size:13px; margin-top:8px; }
.decision ul { padding-left:20px; font-size:13px; }
.decision .priorite { display:flex; gap:10px; align-items:center; flex-wrap:wrap; font-weight:650; }
.decision small { display:block; color:var(--encre-2); line-height:1.5; }
.decision-action { font-size:15px; font-weight:700; color:var(--encre-1); }
.badge-vert { background:var(--vert-fond); color:var(--vert-texte); }
.decision-chiffres { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; margin:12px 0; }
.decision-chiffres > div { background:var(--surface); padding:10px; border-radius:8px; border:1px solid var(--filet); }
.decision-chiffres span { display:block; font-size:11px; color:var(--encre-2); }
.decision-chiffres b { font-size:17px; font-variant-numeric:tabular-nums; }
.alerte-donnee { border-left:3px solid var(--or); padding-left:9px; }
.alerte-donnee.fort { border-color:var(--alerte-texte); color:var(--alerte-texte); }
.preuves-table { border-collapse:collapse; width:100%; margin:10px 0; font-size:12px; }
.preuves-table td,.preuves-table th { text-align:left; border-bottom:1px solid var(--filet); padding:6px 5px; overflow-wrap:anywhere; }
.contact-modes { display:flex; flex-wrap:wrap; gap:8px; margin:16px 0; }
.contact-modes .actif { background:var(--marque); color:var(--marque-encre); }
.recherche-raccourcis { display:flex; gap:8px; flex-wrap:wrap; margin:10px 0; }
.recherche-raccourcis button { padding:7px 12px; border:1px solid var(--filet); border-radius:20px; background:var(--surface); color:var(--encre-1); cursor:pointer; }
.recherche-raccourcis button[aria-pressed=true] { background:var(--marque); color:var(--marque-encre); }
@media(max-width:600px) { .decision-chiffres { grid-template-columns:1fr; } .preuves-table { font-size:11px; } }
.reglages-finance { flex-basis:100%; border-top:1px solid var(--filet); padding-top:10px; }
.reglages-finance > summary { cursor:pointer; font-weight:600; color:var(--encre-2); }
.reglages-contenu { display:flex; flex-wrap:wrap; gap:12px; padding-top:12px; }
#recherche-etat { color:var(--encre-2); font-size:13px; padding:10px 0; }
@media(max-width:760px) { .recherche-intro { align-items:flex-start; flex-direction:column; gap:12px; }
  .recherche-chiffres { gap:24px; } .decision { padding:10px; } }
body { margin: 0; background: var(--plan); color: var(--encre-1);
  font: 15px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }
a { color: var(--marque); text-decoration: none; }
@media (prefers-color-scheme: dark) { a { color: #8fbfa9; } }
a:hover { text-decoration: underline; }
svg.ic { width: 1em; height: 1em; vertical-align: -.12em; fill: none;
  stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }

/* ---- Bandeau façon enseigne de commerce + store de devanture ---- */
.masthead { background: linear-gradient(115deg, var(--marque-fonce), var(--marque) 55%, var(--marque-fonce));
  color: var(--marque-encre);
  border-top: 3px solid var(--or); box-shadow: inset 0 -1px 0 rgba(255,255,255,.08); }
.masthead-inner { max-width: 1380px; margin: 0 auto; padding: 18px 24px 14px;
  display: flex; align-items: center; gap: 18px; flex-wrap: wrap; }
.enseigne { display: flex; align-items: center; gap: 14px; }
.enseigne svg.devanture { width: 50px; height: 50px; color: var(--or-vif); flex: none; }
.wordmark { font-family: Fraunces, Georgia, serif; font-weight: 700; font-size: 42px;
  letter-spacing: .015em; margin: 0; line-height: .95;
  text-shadow: 0 2px 0 rgba(0,0,0,.28); }
.wordmark .point { color: var(--or-vif); }
.wordmark .trait { display: block; margin-top: 4px; }
.hud { margin-left: auto; }
.hud-texte { text-align: right; font-size: 12.5px; line-height: 1.42;
  font-variant-numeric: tabular-nums; max-width: 360px;
  background: rgba(255, 255, 255, .10); border: 1px solid rgba(255, 255, 255, .20);
  border-radius: 12px; padding: 7px 14px;
  backdrop-filter: blur(10px) saturate(1.2); -webkit-backdrop-filter: blur(10px) saturate(1.2);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, .18), 0 4px 14px rgba(0, 0, 0, .12); }
.hud-texte b { font-size: 13.5px; color: var(--or-vif); }
.hud-texte a { color: var(--or-vif); font-weight: 700; text-underline-offset: 3px; }
.hud-texte .maj { opacity: .7; display: block; font-size: 11px; }
.auvent { height: 10px; background: repeating-linear-gradient(90deg,
    var(--marque) 0 26px, var(--marque-fonce) 26px 52px);
  -webkit-mask: radial-gradient(9px at 13px 0, #000 97%, #0000) 0 0 / 26px 10px repeat-x;
  mask: radial-gradient(9px at 13px 0, #000 97%, #0000) 0 0 / 26px 10px repeat-x; }

.page { max-width: 1380px; margin: 0 auto; padding: 10px 24px 90px; }

/* ---- Onglets La chasse / Le marché ---- */
.onglets { display: flex; gap: 4px; margin: 10px 0 2px; border-bottom: 1px solid var(--filet); }
.onglet { font: 600 14.5px Fraunces, Georgia, serif; color: var(--encre-2); background: none;
  border: none; border-bottom: 2.5px solid transparent; padding: 8px 14px 9px; cursor: pointer; }
.onglet.actif { color: var(--encre-1); border-bottom-color: var(--or-vif); }
.onglet:hover { color: var(--encre-1); }

/* ---- Évolution du prix, en clair sur la carte ---- */
.evolution-prix { margin: 7px 0 2px; font-size: 12.5px; color: var(--encre-2);
  font-variant-numeric: tabular-nums; }
.evolution-prix .evo-titre { font-size: 10.5px; text-transform: uppercase;
  letter-spacing: .05em; color: var(--encre-3); margin-right: 4px; }
.evolution-prix .evo-date { color: var(--encre-3); font-size: 11px; }
.evolution-prix .evo-baisse { color: var(--vert-texte); font-weight: 600; }
.evolution-prix .evo-hausse { color: var(--alerte-texte); font-weight: 600; }

/* ---- Mon suivi : le carnet de chasse ---- */
.suivi-select { font: 600 11.5px system-ui, sans-serif; color: var(--marque);
  background: var(--plan); border: 1px solid var(--bord); border-radius: 7px;
  padding: 4px 6px; cursor: pointer; margin-top: 4px; max-width: 118px; }
.suivi-select.actif { background: var(--vert-fond); color: var(--vert-texte); border-color: var(--vert-texte); }
.suivi-item { background: var(--surface); border: 1px solid var(--bord); border-radius: 10px;
  padding: 8px 14px 10px; margin-bottom: 10px; }
.suivi-item .ligne-compacte { border-bottom: none; }
.suivi-meta { font-size: 12px; color: var(--encre-3); margin: 2px 0 6px; }
.suivi-alerte { color: var(--alerte-texte); font-weight: 600; }
.suivi-note { width: 100%; box-sizing: border-box; font-family: inherit; font-size: 13px;
  line-height: 1.45; color: var(--encre-1);
  background: var(--plan); border: 1px solid var(--filet); border-radius: 8px; padding: 7px 10px;
  resize: vertical; }
.suivi-note:focus { outline: none; border-color: var(--marque); }

/* ---- Le marché : graphiques (palette catégorielle VALIDÉE par mode —
   scripts dataviz : light warn contraste couvert par la vue tableau) ---- */
:root { --g1: #2a78d6; --g2: #1baf7a; --g3: #eda100; }
@media (prefers-color-scheme: dark) { :root { --g1: #3987e5; --g2: #199e70; --g3: #c98500; } }
.marche-intro { color: var(--encre-2); font-size: 13.5px; margin: 12px 0 6px; }
.marche-pied { color: var(--encre-3); font-size: 12.5px; margin: 10px 0 18px; }
.periodes { display: flex; gap: 6px; margin: 8px 0 12px; }
.periodes button { font: 600 12px system-ui, sans-serif; color: var(--encre-2);
  background: var(--surface); border: 1px solid var(--bord); border-radius: 999px;
  padding: 4px 12px; cursor: pointer; }
.periodes button.actif { color: var(--marque-encre); background: var(--marque); border-color: var(--marque); }
.grille-marche { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
@media (max-width: 900px) { .grille-marche { grid-template-columns: 1fr; } }
.carte-graph { background: var(--surface); border: 1px solid var(--bord); border-radius: 12px;
  padding: 14px 16px 10px; }
.carte-graph h3 { font: 600 15.5px Fraunces, Georgia, serif; color: var(--encre-1); margin: 0; }
.carte-graph .delta-an { font: 600 12.5px system-ui, sans-serif; margin-left: 8px; white-space: nowrap; }
.delta-an.hausse { color: var(--vert-texte); } .delta-an.baisse { color: var(--alerte-texte); }
.carte-graph .lecture { color: var(--encre-2); font-size: 12.5px; margin: 3px 0 8px; }
.carte-graph .source-graph { color: var(--encre-3); font-size: 11.5px; margin-top: 4px; }
.carte-graph .source-graph a { color: var(--encre-3); }
.carte-graph svg { display: block; width: 100%; height: auto; }
.graph-legende { display: flex; gap: 14px; flex-wrap: wrap; margin: 2px 0 6px;
  font-size: 12px; color: var(--encre-2); }
.graph-legende .cle { display: inline-block; width: 16px; height: 0; border-top: 2.5px solid;
  vertical-align: middle; margin-right: 5px; border-radius: 2px; }
.graph-tooltip { position: fixed; z-index: 40; pointer-events: none; display: none;
  background: var(--surface); border: 1px solid var(--bord); border-radius: 9px;
  box-shadow: 0 6px 18px rgba(0,0,0,.14); padding: 8px 11px; font-size: 12.5px; min-width: 130px; }
.graph-tooltip .qt { color: var(--encre-3); font-size: 11px; margin-bottom: 3px; }
.graph-tooltip .vl { display: flex; align-items: center; gap: 6px; }
.graph-tooltip .vl b { font-size: 13px; color: var(--encre-1); }
.graph-tooltip .vl span { color: var(--encre-2); }
.voir-valeurs { margin: 4px 0 2px; }
.voir-valeurs > summary { cursor: pointer; font-size: 11.5px; color: var(--encre-3); list-style: none; }
.voir-valeurs > summary::-webkit-details-marker { display: none; }
.voir-valeurs table { width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 6px;
  font-variant-numeric: tabular-nums; }
.voir-valeurs th, .voir-valeurs td { text-align: right; padding: 2px 8px; border-bottom: 1px solid var(--filet); }
.voir-valeurs th:first-child, .voir-valeurs td:first-child { text-align: left; }
.voir-valeurs tbody { display: block; max-height: 190px; overflow-y: auto; }
.voir-valeurs thead, .voir-valeurs tbody tr { display: table; width: 100%; table-layout: fixed; }

/* ---- Filtres (repliables sur mobile) — volontairement PAS sticky :
   la barre défile avec la page au lieu de manger l'écran en permanence. ---- */
.volet-filtres { background: var(--plan);
  border-bottom: 1px solid var(--filet); margin-bottom: 4px; }
.volet-filtres > summary { display: block; cursor: pointer; padding: 10px 0;
  font-weight: 600; color: var(--encre-2); list-style: none; }
.volet-filtres > summary::-webkit-details-marker { display: none; }
.filtres { display: flex; align-items: end; gap: 14px; flex-wrap: wrap; padding: 12px 0; }
.filtre { display: flex; flex-direction: column; gap: 3px; }
.filtre label { font-size: 11px; color: var(--encre-3); text-transform: uppercase; letter-spacing: .06em; }
.filtre select, .filtre input { background: var(--surface); color: var(--encre-1);
  border: 1px solid var(--bord); border-radius: 7px; padding: 6px 8px; font: inherit; font-size: 14px; }
.filtre input[type=number] { width: 86px; }
.filtres .compteur { margin-left: auto; color: var(--encre-2); font-size: 13px; }
.multi { position: relative; }
.multi summary { list-style: none; cursor: pointer; background: var(--surface);
  color: var(--encre-1); border: 1px solid var(--bord); border-radius: 7px;
  padding: 6px 8px; font-size: 14px; min-width: 132px; max-width: 210px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.multi summary::-webkit-details-marker { display: none; }
.multi summary::after { content: " ▾"; color: var(--encre-3); }
.multi-liste { position: absolute; z-index: 30; top: calc(100% + 5px); left: 0;
  min-width: 220px; background: var(--surface); border: 1px solid var(--bord);
  border-radius: 9px; box-shadow: 0 8px 22px rgba(0,0,0,.16); padding: 9px 11px;
  display: flex; flex-direction: column; gap: 6px; }
.multi-liste label { display: flex; gap: 8px; align-items: center; font-size: 13.5px;
  color: var(--encre-1); cursor: pointer; white-space: nowrap; }
/* Le profil n'est pas un filtre : il ne trie rien, il RECALCULE tout le site.
   Un simple liseré doré ne le disait pas assez — le fond teinté et le titre
   posé au-dessus séparent enfin les deux natures de réglage. */
.profil-groupe { display: flex; align-items: end; gap: 14px; position: relative;
  border-left: 3px solid var(--or); padding: 20px 14px 10px; margin-left: 4px;
  background: color-mix(in srgb, var(--or) 7%, transparent);
  border-radius: 0 8px 8px 0; }
.profil-groupe::before { content: attr(data-titre); position: absolute; top: 5px; left: 14px;
  font-size: 9.5px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase;
  color: var(--or); opacity: .85; }
.profil-groupe .filtre label { color: var(--or); font-weight: 700; }
/* L'unité de l'apport (€ / %) est un réglage du champ, pas un champ de plus :
   discrète, collée à son libellé. */
#p-apport-mode { font-size: 10px; padding: 1px 3px; margin-left: 4px;
  border: 1px solid var(--filet); border-radius: 4px;
  background: var(--surface); color: var(--encre-2); text-transform: none;
  letter-spacing: 0; font-weight: 600; vertical-align: 1px; }
.profil-note { font-size: 12.5px; color: var(--encre-3); margin: -4px 0 10px; }
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
.carte { position: relative; display: grid; grid-template-columns: 176px minmax(0,1fr) 265px 96px;
  gap: 16px; background: var(--surface); border: 1px solid var(--bord);
  border-radius: 12px; padding: 14px; margin-bottom: 12px; align-items: start;
  animation: surgir .4s ease both; transition: transform .15s ease, box-shadow .15s ease; }
.carte:hover { transform: translateY(-2px); box-shadow: 0 6px 18px rgba(15, 40, 25, .10); }
.carte.prio { background: var(--bande); border-color: var(--marque); }
.carte.podium-1 { border-color: var(--or); box-shadow: 0 0 0 1px var(--or); }

.btn-masquer { position: absolute; top: -4px; left: 14px; z-index: 3;
  width: 23px; height: 23px; border-radius: 50%; background: var(--surface);
  border: 1.4px solid var(--bord); color: var(--encre-2); font: 700 13px system-ui, sans-serif;
  cursor: pointer; display: flex; align-items: center; justify-content: center;
  box-shadow: 0 1px 4px rgba(0,0,0,.12); }
.btn-masquer:hover { background: var(--alerte-fond); color: var(--alerte-texte); border-color: var(--alerte-texte); }

/* Autocollants d'exception + reflet doré sur les pépites */
.sticker { position: absolute; top: -11px; right: 14px; z-index: 2;
  display: inline-flex; align-items: center; justify-content: center; gap: 4px;
  min-width: 42px; height: 42px; padding: 0 8px; border-radius: 50%;
  font: 700 12.5px Fraunces, Georgia, serif; transform: rotate(7deg);
  box-shadow: 0 3px 8px rgba(0,0,0,.18); pointer-events: none; }
.sticker-marteau { background: radial-gradient(circle at 35% 30%, var(--or-vif), var(--or));
  color: #fff8e6; font-size: 17px; }
@keyframes fretiller { 0%, 100% { transform: rotate(7deg); } 35% { transform: rotate(-6deg) scale(1.12); } 70% { transform: rotate(10deg); } }
.carte:hover .sticker, .carte-enchere:hover .sticker { animation: fretiller .55s ease; }
.carte.rang-s { border-color: var(--or);
  box-shadow: 0 0 0 1px var(--or), 0 8px 26px rgba(180, 138, 30, .16);
  animation: surgir .4s ease both, lueur-pepite 2.6s ease-in-out infinite; }
@keyframes lueur-pepite {
  0%, 100% { box-shadow: 0 0 0 1px var(--or), 0 8px 26px rgba(180, 138, 30, .16); }
  50% { box-shadow: 0 0 0 1.5px var(--or-vif), 0 10px 34px rgba(214, 165, 50, .30); }
}
/* Carte visée par un lien direct (email pépite) : anneau qui s'estompe, pour
   la retrouver d'un coup d'œil sans se battre avec le box-shadow de .rang-s */
.carte-ciblee { animation: ping-cible 1.3s ease-out 2; }
@keyframes ping-cible {
  0% { outline: 3px solid var(--marque); outline-offset: 3px; }
  100% { outline: 3px solid transparent; outline-offset: 10px; }
}
.pepite-pourquoi { margin-top: 10px; padding: 10px 13px; border-radius: 0 9px 9px 0;
  border-left: 3px solid var(--or-vif); background: var(--or-clair); font-size: 13.5px;
  color: var(--encre-1); }
.pepite-pourquoi b { color: var(--marque-fonce); }
@media (prefers-color-scheme: dark) { .pepite-pourquoi b { color: var(--or-vif); } }
@media (prefers-reduced-motion: reduce) {
  .carte.rang-s { animation: none; }
}
.tampon { display: inline-block; font-family: Fraunces, Georgia, serif; font-weight: 700;
  font-size: 11px; letter-spacing: .1em; text-transform: uppercase;
  color: var(--or); border: 2px solid var(--or); border-radius: 6px;
  padding: 2px 9px; transform: rotate(-2.5deg); box-shadow: inset 0 0 0 1.5px var(--surface),
  inset 0 0 0 3px var(--or); background: var(--or-clair); margin-bottom: 7px; }
.carte-img { position: relative; height: 124px; border-radius: 8px; overflow: hidden;
  background: var(--gris-fond); display: flex; align-items: center; justify-content: center;
  color: var(--encre-3); }
.carte-img svg { width: 54px; height: 54px; opacity: .5; }
.carte-img img { width: 100%; height: 100%; object-fit: cover; display: block; }
.car-btn { position: absolute; top: 50%; transform: translateY(-50%);
  width: 26px; height: 26px; border-radius: 50%; border: none; cursor: pointer;
  background: rgba(15, 25, 18, .55); color: #fff; font: 700 15px/1 system-ui;
  opacity: 0; transition: opacity .15s ease; }
.carte-img:hover .car-btn { opacity: 1; }
.car-btn.prec { left: 6px; }
.car-btn.suiv { right: 6px; }
.car-compteur { position: absolute; bottom: 5px; right: 7px;
  background: rgba(15, 25, 18, .55); color: #fff; font-size: 10.5px;
  border-radius: 999px; padding: 1px 7px; font-variant-numeric: tabular-nums; }
@media (max-width: 760px) { .car-btn { opacity: 1; } }
.carte-titre { font-size: 16px; font-weight: 600; margin: 0 0 2px; }
.carte-titre a { color: var(--encre-1); }
.carte-lieu { color: var(--encre-2); font-size: 13px; margin-bottom: 7px; }
.jours-marche-stale { color: var(--vert-texte); font-weight: 600; cursor: help; }
.badges { display: inline-flex; gap: 6px; margin-left: 8px; vertical-align: 2px; flex-wrap: wrap; }
.badge { font-size: 11.5px; font-weight: 600; padding: 2px 8px; border-radius: 999px; white-space: nowrap; }
.badge-type { background: var(--gris-fond); color: var(--gris-texte); }
.badge-nouveau { background: var(--vert-fond); color: var(--vert-texte); }
.badge-alerte { background: var(--alerte-fond); color: var(--alerte-texte); }
.badge-rue-plus { background: var(--vert-fond); color: var(--vert-texte); }
.badge-autofinance { background: var(--vert-fond); color: var(--vert-texte); border: 1px solid currentColor; }
.badge-decote { background: var(--vert-fond); color: var(--vert-texte); border: 1px solid currentColor; }
.badge-decote-estime { border-style: dashed; }
.enclair { margin-top: 10px; padding: 9px 12px; border-left: 3px solid var(--or);
  background: var(--bande); border-radius: 0 9px 9px 0; font-size: 13.5px; color: var(--encre-2); }
.enclair-titre { font-weight: 700; color: var(--encre-1); font-variant: small-caps; margin-right: 4px; }
.faits-cles, .questions-reponses { }
.faits-cles .titre-bloc, .questions-reponses .titre-bloc { font-size: 10.5px; text-transform: uppercase;
  letter-spacing: .06em; color: var(--encre-3); cursor: pointer; list-style: none;
  display: flex; align-items: center; gap: 5px; }
.faits-cles .titre-bloc::-webkit-details-marker,
.questions-reponses .titre-bloc::-webkit-details-marker { display: none; }
.faits-cles .titre-bloc::before, .questions-reponses .titre-bloc::before {
  content: "▸"; font-size: 9px; color: var(--encre-3); transition: transform .15s ease; }
.faits-cles[open] .titre-bloc::before, .questions-reponses[open] .titre-bloc::before { transform: rotate(90deg); }
.faits-cles { margin-top: 10px; font-size: 13px; }
.faits-cles ul { margin: 4px 0 0; padding-left: 0; list-style: none; display: flex; flex-direction: column; gap: 3px; }
.faits-cles li { padding-left: 18px; position: relative; color: var(--encre-1); }
.faits-cles li::before { position: absolute; left: 0; font-weight: 700; }
.faits-cles li.fait-plus::before { content: "+"; color: var(--vert-texte); }
.faits-cles li.fait-moins::before { content: "–"; color: var(--alerte-texte); }
.questions-reponses { margin-top: 12px; font-size: 13px; border-top: 1px dashed var(--filet); padding-top: 10px; }
.qr-item { margin-bottom: 7px; }
.qr-q { font-weight: 600; color: var(--encre-1); }
.qr-r { color: var(--encre-2); margin-top: 1px; }
a.btn-outil { text-decoration: none; }
a.btn-outil:hover { text-decoration: none; border-color: var(--marque); }
.etiquettes { display: flex; gap: 6px; flex-wrap: wrap; margin: 0 0 9px; }
.etiquette { font-size: 11.5px; color: var(--encre-2); border: 1px solid var(--filet);
  border-radius: 6px; padding: 1px 7px; background: var(--plan); }
.etiquette-plus { border-color: var(--vert-texte); color: var(--vert-texte); }
.etiquette-moins { border-color: var(--alerte-texte); color: var(--alerte-texte); }
.btn-outil { font: 600 11.5px system-ui, sans-serif; color: var(--marque);
  background: var(--plan); border: 1px solid var(--bord); border-radius: 7px;
  padding: 4px 9px; cursor: pointer; margin-top: 4px; display: inline-flex; gap: 5px; align-items: center; }
/* Sept boutons au même poids ne disaient pas lequel conclut. Tous les autres
   servent à ÉTUDIER le bien ; celui-ci est le seul qui engage quelque chose
   au dehors — écrire au vendeur. Il est donc plein, les autres restent des
   contours : une seule action colorée par carte, la hiérarchie se lit sans
   avoir à comparer les libellés. */
.btn-outil--primaire { background: var(--marque); color: #fff; border-color: var(--marque); }
.btn-outil--primaire:hover { filter: brightness(1.08); }
@media (prefers-color-scheme: dark) {
  .btn-outil--primaire { background: #2f6b52; border-color: #2f6b52; color: #f4f1e8; }
}
.info-i { display: inline-flex; width: 15px; height: 15px; border-radius: 50%;
  border: 1.4px solid var(--encre-3); color: var(--encre-3); font: 700 10px Georgia, serif;
  align-items: center; justify-content: center; cursor: pointer; vertical-align: 1px; margin-left: 4px; }
.sim-grille { border-collapse: collapse; margin-top: 10px; font-variant-numeric: tabular-nums; }
.sim-grille th, .sim-grille td { border: 1px solid var(--filet); padding: 6px 12px;
  text-align: right; font-size: 13.5px; }
.sim-grille th { color: var(--encre-3); font-weight: 600; }
.sim-grille td.top { background: var(--vert-fond); color: var(--vert-texte); font-weight: 700; }
.sim-champs { display: flex; gap: 16px; flex-wrap: wrap; margin: 12px 0; }
.sim-champs label { display: flex; flex-direction: column; gap: 3px; font-size: 12px; color: var(--encre-3); }
.sim-champs input { background: var(--plan); color: var(--encre-1); border: 1px solid var(--bord);
  border-radius: 7px; padding: 6px 8px; font: inherit; width: 110px; }
.sim-resultats { display: flex; gap: 22px; flex-wrap: wrap; margin-top: 6px; }
.sim-bilan { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; margin:16px 0; }
.sim-bilan .metrique { padding:14px; border:1px solid var(--filet); border-radius:10px; background:var(--plan); }
.sim-bilan .valeur { margin-top:5px; font-size:23px; }
.check-groupe h4 { font-family: Fraunces, Georgia, serif; margin: 14px 0 6px; font-size: 15px; }
.check-item { display: flex; gap: 9px; align-items: baseline; padding: 4px 0; font-size: 14px; }
.check-item .auto { font-size: 11.5px; color: var(--vert-texte); background: var(--vert-fond);
  border-radius: 999px; padding: 1px 8px; white-space: nowrap; }
.check-item .auto.negatif { color: var(--alerte-texte); background: var(--alerte-fond); }
.contact-texte { width: 100%; box-sizing: border-box; background: var(--plan); color: var(--encre-1);
  border: 1px solid var(--bord); border-radius: 9px; padding: 12px; font: 13.5px/1.55 system-ui, sans-serif;
  resize: vertical; margin-top: 10px; }
.contact-actions { display:flex; flex-wrap:wrap; gap:10px; align-items:center; margin-top:10px; }
.contact-brouillon { display:block; font-size:12px; color:var(--encre-2); margin-top:8px; }
.rep-intro { color:var(--encre-2); margin:0 0 18px; max-width:850px; }
#rep-association > summary { cursor:pointer; font-size:13px; font-weight:600; margin-bottom:14px; }
.rep-choix { display:grid; grid-template-columns:minmax(180px,1fr) minmax(0,2fr); gap:14px; }
.rep-choix label,.rep-champs label { display:flex; flex-direction:column; gap:5px; min-width:0; font-size:12px; color:var(--encre-2); }
.rep-choix input,.rep-choix select,.rep-champs input,.rep-champs select { box-sizing:border-box; width:100%; min-width:0; padding:10px; border:1px solid var(--filet); border-radius:8px; background:var(--surface); color:var(--encre-1); font:inherit; font-size:14px; }
.rep-note { color:var(--encre-2); font-size:12px; line-height:1.6; }
.rep-dossier { background:var(--surface); border:1px solid var(--filet); padding:22px; border-radius:12px; margin:18px 0; }
.rep-dossier h3,.rep-dossier p { overflow-wrap:anywhere; }
.rep-entete h3 { margin:0; font-size:18px; }
.rep-entete { display:flex; justify-content:space-between; align-items:baseline; gap:12px; flex-wrap:wrap; }
.rep-message { white-space:pre-wrap; overflow-wrap:anywhere; font-size:13px; color:var(--encre-2); border-left:2px solid var(--filet); margin:10px 0; padding-left:12px; }
.rep-entete p { font-size:12px; color:var(--encre-2); margin:6px 0 18px; }
.rep-principal { background:var(--marque)!important; color:var(--marque-encre)!important; border-color:var(--marque)!important; }
.rep-resultat { margin:20px 0; padding:18px; border:1px solid var(--filet); border-left:3px solid var(--or); border-radius:0 10px 10px 0; }
.rep-resultat.interessant { border-left-color:var(--vert-texte); background:var(--vert-fond); }
.rep-resultat.vigilance,.rep-resultat.hors_cible { border-left-color:var(--alerte-texte); }
.rep-etat { font-size:12px; color:var(--encre-2); margin:0 0 8px; }
.rep-resultat h3 { font-size:18px; margin:0 0 14px; }
.rep-bilan { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }
.rep-bilan span { display:block; font-size:12px; color:var(--encre-2); }
.rep-bilan b { display:block; font-size:22px; margin-top:5px; }
.rep-prix { font-size:15px; }
.rep-informations > summary,.rep-calcul > summary,.rep-preuves > summary,.rep-complements > summary,.rep-relance > summary { cursor:pointer; font-size:13px; font-weight:600; margin:14px 0; }
.rep-champs { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; margin:14px 0; }
.rep-preuves li,.rep-manquants li { margin:5px 0; font-size:13px; overflow-wrap:anywhere; }
.rep-sauvegarde { display:flex; flex-wrap:wrap; align-items:center; gap:12px; font-size:12px; color:var(--encre-2); margin:20px 0; }
.rep-import { position:relative; cursor:pointer; }
.rep-import input { position:absolute; inset:0; opacity:0; width:100%; cursor:pointer; }
@media(max-width:760px) { .rep-champs { grid-template-columns:repeat(2,minmax(0,1fr)); } .rep-choix { grid-template-columns:1fr; } }
@media(max-width:600px) { .onglets { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); } .onglets .onglet { min-width:0; font-size:13px; padding:12px 3px; white-space:nowrap; } .onglets #suivi-compteur { display:none; } .rep-dossier { padding:14px; } .rep-champs { grid-template-columns:1fr; } .rep-bilan b { font-size:18px; } }
.critique-texte { background: var(--plan); border-left: 3px solid var(--marque); border-radius: 0 9px 9px 0;
  padding: 14px 16px; font-size: 14px; line-height: 1.6; color: var(--encre-1); white-space: pre-wrap; }
.critique-note { font-size: 12.5px; color: var(--encre-3); margin-top: 10px; }
.btn-outil.a-critique { border-color: var(--marque); color: var(--marque); }

.metriques { display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 10px; }
.metrique .libelle { font-size: 10.5px; text-transform: uppercase; letter-spacing: .05em; color: var(--encre-3); }
.metrique .valeur { font-size: 15px; font-weight: 600; font-variant-numeric: tabular-nums; }
.metrique .valeur small { font-weight: 400; color: var(--encre-2); }
/* Hiérarchie de lecture. Ce projet vit du CASH-FLOW et du rendement : ces deux
   chiffres décident d'acheter ou pas, les autres ne font que situer le bien.
   Affichés au même poids, les huit obligeaient à tout relire pour retrouver
   les deux qui comptent. « Clé » domine, « détail » s'efface sans disparaître. */
.metrique--cle .libelle { color: var(--encre-1); font-weight: 700; }
.metrique--cle .valeur { font-size: 22px; line-height: 1.15; }
.metrique--detail .valeur { font-size: 13px; font-weight: 500; color: var(--encre-2); }
.metrique--detail .libelle { opacity: .7; }
/* Sépare le groupe « détail » d'un simple filet, posé sur le PREMIER d'entre
   eux. CSS ne sait pas viser « le premier de cette classe » (:first-of-type
   compte les types d'éléments, pas les classes) : on le met donc sur tous,
   puis on le retire dès qu'un détail en suit un autre. */
.metrique--detail { border-left: 1px solid var(--filet); padding-left: 18px; }
.metrique--detail + .metrique--detail { border-left: none; padding-left: 0; }

/* Jauge marché + lecture du prix */
.marche { font-size: 12.5px; color: var(--encre-2); max-width: 480px; }
.marche-source { font-size: 11px; color: var(--encre-3); margin-top: 2px; }
.marche-piste { position: relative; height: 18px; margin: 6px 0 1px; }
.marche-piste .ligne { position: absolute; top: 8px; left: 0; right: 0; height: 2px;
  background: var(--filet); border-radius: 2px; }
.marche-piste .bande-marche { position: absolute; top: 5px; height: 8px;
  background: color-mix(in srgb, var(--marque) 30%, transparent); border-radius: 4px; }
.marche-piste .mediane { position: absolute; top: 3px; width: 2px; height: 12px; background: var(--encre-3); }
.marche-piste .bien { position: absolute; top: 2px; width: 14px; height: 14px;
  border-radius: 50%; background: var(--or-vif); border: 2.5px solid var(--encre-1);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--or-vif) 30%, transparent); }
.marche-piste .cible { position: absolute; top: 13px; width: 0; height: 0;
  border-left: 5px solid transparent; border-right: 5px solid transparent;
  border-bottom: 7px solid var(--alerte-texte); }
.marche-piste .cible.usage { border-bottom-color: var(--vert-texte); }
.cible-txt.usage { color: var(--vert-texte); }
.marche-echelle { display: flex; justify-content: space-between; font-size: 11px;
  color: var(--encre-3); font-variant-numeric: tabular-nums; margin-bottom: 3px; }
.marche-legende-bien { color: var(--or); font-weight: 700; }
.cible-txt { color: var(--alerte-texte); font-weight: 600; font-size: 11.5px; }
.exp-ligne { grid-column: 1 / -1; font-size: 11.5px; color: var(--encre-2);
  background: var(--plan); border-left: 3px solid var(--or); border-radius: 0 6px 6px 0;
  padding: 6px 9px; margin: 2px 0 7px; }
.marche .bon { color: var(--vert-texte); font-weight: 600; }
.marche .mauvais { color: var(--alerte-texte); font-weight: 600; }
.lecture { font-style: italic; color: var(--encre-2); margin-top: 5px;
  border-left: 3px solid var(--or); padding-left: 8px; }
/* La négociation est le SEUL conseil de la carte qui se traduit en geste :
   un prix à annoncer au vendeur. Noyé au même poids que les paragraphes de
   lecture, il se lisait comme un commentaire de plus. Il devient l'action,
   annoncée comme telle — sans crier, la carte en compte déjà assez. */
.lecture.nego { border-left-color: var(--marque); border-left-width: 4px;
  font-style: normal; color: var(--encre-1); background: var(--vert-fond);
  padding: 8px 10px; border-radius: 0 7px 7px 0; margin-top: 8px; }
.lecture.nego::before { content: "Votre offre"; display: block;
  font-size: 9.5px; font-weight: 700; letter-spacing: .11em; text-transform: uppercase;
  color: var(--marque); margin-bottom: 2px; }
@media (prefers-color-scheme: dark) { .lecture.nego::before { color: #8fbfa9; } }

/* Méthode d'expert */
.methode { columns: 2; column-gap: 28px; font-size: 13.5px; color: var(--encre-2); margin-top: 10px; }
.methode h4 { font-family: Fraunces, Georgia, serif; color: var(--encre-1);
  margin: 0 0 4px; font-size: 15px; break-after: avoid; }
.methode ul { margin: 0 0 14px; padding-left: 18px; break-inside: avoid; }
.methode li { margin-bottom: 3px; }
@media (max-width: 760px) { .methode { columns: 1; } }

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
.score { width: 64px; height: 64px; border-radius: 14px; display: flex; align-items: center;
  justify-content: center; font-family: Fraunces, Georgia, serif;
  font-size: 27px; font-weight: 700; font-variant-numeric: tabular-nums; }
.score.vert { background: var(--vert-fond); color: var(--vert-texte); }
.score.orange { background: var(--orange-fond); color: var(--orange-texte); }
.score.gris { background: var(--gris-fond); color: var(--gris-texte); }
.score.or { background: var(--or-clair); color: var(--or); }
.score-libelle { font-size: 10px; color: var(--encre-3); text-transform: uppercase; letter-spacing: .05em; }
.btn-comp { font: 600 11.5px system-ui, sans-serif; color: var(--marque);
  background: var(--plan); border: 1px solid var(--bord); border-radius: 7px;
  padding: 4px 9px; cursor: pointer; margin-top: 4px; display: inline-flex; gap: 5px; align-items: center; }
.btn-comp.actif { background: var(--marque); color: var(--marque-encre); border-color: var(--marque); }

/* Rangées compactes, dépliables en carte complète */
details.repli { margin-top: 24px; border-top: 1px solid var(--filet); padding-top: 12px; }
details.repli > summary { cursor: pointer; color: var(--encre-2); font-weight: 600; font-size: 14px; }
details.ligne-depliable > summary { list-style: none; cursor: pointer; }
details.ligne-depliable > summary::-webkit-details-marker { display: none; }
details.ligne-depliable[open] > summary .chevron { transform: rotate(90deg); }
details.ligne-depliable .carte { margin: 8px 0 14px; animation: none; }
.ligne-compacte { display: flex; gap: 12px; align-items: center; padding: 7px 2px;
  border-bottom: 1px solid var(--filet); font-size: 13.5px; }
.ligne-compacte:hover { background: var(--bande); }
.ligne-compacte .chevron { flex: 0 0 auto; color: var(--encre-3); transition: transform .15s ease; }
.ligne-compacte .mini-score { flex: 0 0 34px; text-align: center; border-radius: 7px;
  font-weight: 700; font-variant-numeric: tabular-nums; padding: 2px 0; }
.ligne-compacte .t { flex: 1 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ligne-compacte .d { color: var(--encre-2); white-space: nowrap; font-variant-numeric: tabular-nums; }

/* Enchères : vraies cartes */
.carte-enchere { position: relative; display: grid; grid-template-columns: 176px minmax(0,1fr) 170px;
  gap: 16px; background: var(--surface); border: 1px solid var(--bord);
  border-radius: 12px; padding: 14px; margin-bottom: 12px; align-items: start;
  animation: surgir .4s ease both; transition: transform .15s ease, box-shadow .15s ease; }
.carte-enchere:hover { transform: translateY(-2px); box-shadow: 0 6px 18px rgba(15, 40, 25, .10); }
.carte-enchere.forte { border-color: var(--or); box-shadow: 0 0 0 1px var(--or); background: var(--bande); }
.carte-enchere .quand { font-family: Fraunces, Georgia, serif; font-weight: 700;
  color: var(--or); font-size: 15px; margin-bottom: 4px; }
.bloc-mise { text-align: center; }
.bloc-mise .libelle { font-size: 10.5px; text-transform: uppercase; letter-spacing: .05em; color: var(--encre-3); }
.bloc-mise .valeur { font-family: Fraunces, Georgia, serif; font-weight: 700; font-size: 22px;
  font-variant-numeric: tabular-nums; }
.bloc-mise .sous { font-size: 12px; color: var(--encre-2); margin-top: 2px; }
.plafond-conseille { margin-top: 8px; font-size: 12.5px; color: var(--encre-2);
  border-top: 1px dashed var(--filet); padding-top: 6px; }
.plafond-conseille b { color: var(--encre-1); }
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
.comparateur-fond, .outil-fond { position: fixed; inset: 0; background: rgba(10, 20, 14, .55);
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
.hud .hud-action { margin-top: 14px; display: inline-flex; flex-direction: column; align-items: flex-end; gap: 6px; }
.hud .btn-veille { display: inline-flex; align-items: center; gap: 8px; padding: 8px 14px;
  border-radius: 999px; background: linear-gradient(135deg, var(--or-vif), #ffbf47);
  color: #fff; font-weight: 700; font-size: 13px; text-decoration: none; box-shadow: 0 8px 20px rgba(255, 140, 0, 0.18);
  transition: transform 120ms ease, box-shadow 120ms ease; }
.hud .btn-veille:hover { transform: translateY(-1px); box-shadow: 0 10px 24px rgba(255, 140, 0, 0.25); }
.hud .btn-veille:active { transform: translateY(0); }

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
@media (max-width: 1100px) {
  .carte-enchere { grid-template-columns: 176px minmax(0,1fr); }
  .carte-enchere .bloc-mise { grid-column: 1 / -1; text-align: left; display: flex;
    gap: 16px; align-items: baseline; }
}
@media (max-width: 760px) {
  .profil-groupe { flex-wrap: wrap; max-width: 100%; gap:10px; margin-left:0; }
  .ligne-compacte { flex-wrap:wrap; }
  .ligne-compacte .d { flex:1 1 100%; min-width:0; white-space:normal; overflow-wrap:anywhere; }
  .multi-liste { min-width:180px; max-width:calc(100vw - 40px); }
  .multi-liste label { white-space:normal; }
  .decision { overflow-wrap:anywhere; }
  .page { padding: 8px 14px 40px; }
  .masthead-inner { padding: 16px 16px 12px; }
  .wordmark { font-size: 34px; }
  .enseigne svg.devanture { width: 42px; height: 42px; }
  /* .carte .pourquoi n'est plus masqué : le détail du score expliquait
     POURQUOI un bien vaut 84, et le cacher sur mobile laissait la note sans
     justification — or c'est au téléphone qu'on lit une alerte. Il passe
     pleine largeur (règle du palier 1100 px), sous les métriques. */
  .hud, .btn-comp, .plateau { display: none !important; }
  .carte .pourquoi { border-top: 1px solid var(--filet); margin-top: 10px; padding-top: 10px; }
  .volet-filtres > summary { display: block; }
  .carte { grid-template-columns: minmax(0,1fr) 72px; gap: 10px; padding: 12px; }
  .carte-img { grid-column: 1 / -1; height: 150px; }
  .carte-enchere { grid-template-columns: 1fr; }
  .metriques { gap: 12px 18px; }
  /* Sur mobile la hiérarchie reste, en plus sobre : 22 px tiendraient mal sur
     une ligne étroite, et le filet vertical du groupe « détail » couperait
     mal une fois les métriques passées à la ligne. */
  .metrique--cle .valeur { font-size: 18px; }
  .metrique--detail { border-left: none; padding-left: 0; }
  .score { width: 54px; height: 54px; font-size: 23px; }
  .comparateur-fond { display: none !important; }
  .sticker { top: -9px; right: 8px; min-width: 36px; height: 36px; }
}
@media (prefers-reduced-motion: reduce) {
  * { animation: none !important; transition: none !important; }
}
/* L'enseigne retrouve son caractère ; la recherche reste au premier écran. */
.masthead-inner { min-height:84px; padding:16px 24px; }
.enseigne { gap:14px; }
.enseigne svg.devanture { width:44px; height:44px; }
.wordmark { font-size:40px; }
.wordmark .trait { width:184px; height:8px; }
.page { padding-top:0; }
.onglets { margin:0 0 10px; }
.onglet { font-family:Fraunces, Georgia, serif; font-size:16px; font-weight:600; padding:12px 18px; }
.onglet.actif { font-weight:700; border-bottom-color:var(--or-vif); }
.volet-filtres { border:0; }
.volet-filtres > summary { display:flex; align-items:center; gap:12px; width:fit-content;
  max-width:100%; padding:6px 0; font-size:13px; font-weight:600; list-style:none; }
.bouton-filtres { display:inline-flex; align-items:center; gap:9px; flex-shrink:0;
  min-height:42px; padding:10px 14px; border:1px solid transparent; border-radius:9px;
  background:var(--marque); color:var(--marque-encre); box-shadow:0 2px 5px rgba(20,58,45,.12); }
.bouton-filtres .icone-filtres { width:18px; height:18px; color:var(--or-vif); }
.volet-filtres > summary:hover .bouton-filtres { background:var(--marque-fonce); }
.volet-filtres > summary:focus-visible { outline:none; }
.volet-filtres > summary:focus-visible .bouton-filtres { outline:3px solid var(--or); outline-offset:3px; }
.volet-filtres[open] .bouton-filtres { background:var(--marque-fonce); border-color:var(--or-vif); }
#resume-filtres { color:var(--encre-2); font-size:12px; font-weight:400; }
.filtre-chevron { width:14px; height:14px; margin-left:4px; }
.volet-filtres[open] .filtre-chevron { transform:rotate(180deg); }
h2.section { font-family:Fraunces, Georgia, serif; font-size:22px; font-weight:600; margin:18px 0 14px; }
.carte { grid-template-columns:160px minmax(0,1fr) 116px; padding:20px; gap:22px;
  border-radius:10px; margin-bottom:14px; animation:none; transition:none; }
.carte:hover { transform:none; box-shadow:none; border-color:var(--encre-3); }
.carte.prio,.carte.podium-1,.carte.rang-s { background:var(--surface); border-color:var(--filet); box-shadow:none; animation:none; }
.carte-img { height:130px; border-radius:6px; }
.carte-titre { font-size:16px; line-height:1.35; margin-bottom:6px; }
.carte-lieu { font-size:12px; margin-bottom:16px; }
.carte .badges { margin-left:8px; gap:4px; }
.badge { font-size:10.5px; padding:2px 6px; font-weight:500; }
.badge-pepite { background:var(--or-clair); color:var(--encre-1); }
.exception-recherche { margin:-6px 0 14px; font-size:12px; color:var(--encre-2); }
.offre-cible { margin:0 0 10px; padding:10px 12px; border-left:3px solid var(--or); background:var(--vert-fond); border-radius:0 8px 8px 0; font-size:12px; }
.offre-cible.financiere-seule { background:var(--surface); border-left-color:var(--filet); }
.offre-entete { display:flex; align-items:baseline; flex-wrap:wrap; gap:5px 12px; justify-content:space-between; }
.offre-entete strong { font-size:14px; }
.offre-prix-cashflow { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px 16px; margin:10px 0; }
.offre-prix-cashflow span { display:block; color:var(--encre-2); font-size:12px; }
.offre-prix-cashflow b { display:block; font-size:20px; line-height:1.35; }
.offre-prix-cashflow small { display:block; font-size:12px; margin-top:3px; }
.offre-plafond { padding-top:8px; border-top:1px solid var(--filet); }
.rep-prix-cible { padding:14px; background:var(--vert-fond); border-radius:8px; }
.offre-cible p { margin:5px 0 0; }
.offre-indisponible { font-size:12px; color:var(--encre-2); margin:0 0 8px; }
.relocation-annonce { font-size:12px; margin:0 0 12px; }
.relocation-annonce > summary { cursor:pointer; color:var(--encre-2); }
.relocation-annonce.vigilance > summary { color:var(--alerte-texte); }
.relocation-annonce ul { margin:6px 0; padding-left:18px; }
.offre-cible button { color:var(--marque); border:0; background:none; padding:3px 0; font:inherit; text-decoration:underline; cursor:pointer; }
.offre-chiffres { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:16px; margin:18px 0; }
.offre-chiffres span { display:block; font-size:12px; color:var(--encre-2); }
.offre-chiffres b { font-size:20px; }
.offre-note { font-size:13px; color:var(--encre-2); }
.metriques { gap:16px 24px; margin-bottom:14px; }
.metrique .libelle { font-size:11px; letter-spacing:0; text-transform:none; }
.metrique .valeur,.metrique--cle .valeur { font-size:16px; line-height:1.45; font-weight:600; }
.metrique--cle .libelle { font-weight:400; color:var(--encre-2); }
.metriques .info-i { display:none; }
.carte-score { gap:7px; }
.carte-score .score { width:44px; height:38px; border-radius:7px; font-size:20px; font-weight:600; }
.carte-score .score-libelle { font-size:10px; margin-bottom:4px; }
.carte-score > button { width:100%; padding:7px 8px; font-size:12px; }
.analyse-annonce { border-top:1px solid var(--filet); padding-top:10px; }
.analyse-annonce > summary { cursor:pointer; color:var(--encre-2); font-size:12px; list-style:none; }
.analyse-annonce > summary span { margin-left:6px; }
.analyse-annonce[open] > summary { color:var(--encre-1); }
.analyse-contenu { padding-top:12px; }
.analyse-contenu .pourquoi { padding:16px 0 0; margin-top:16px; border-top:1px solid var(--filet); }
.provenance-annonce { color:var(--encre-2); font-size:12px; }
.outils-annonce { width:100%; }
.outils-annonce > summary { cursor:pointer; color:var(--encre-2); font-size:11px; text-align:center; padding:5px 0; list-style:none; }
.outils-annonce button,.outils-annonce a,.outils-annonce select { display:block; width:100%; margin-top:7px; }
.infos-veille > summary { cursor:pointer; font-size:12px; color:var(--encre-2); }
.infos-veille > div,.infos-veille > details { margin-top:16px; }
.infos-veille .hud { margin:12px 0; }
.infos-veille .hud-texte { text-align:left; background:none; border:none; box-shadow:none; padding:0; }
@media(max-width:760px) {
  .masthead-inner { min-height:72px; padding:12px 16px; }
  .wordmark { font-size:34px; }
  .wordmark .trait { width:156px; height:7px; }
  .enseigne svg.devanture { width:36px; height:36px; }
  .onglet { font-size:15px; padding:12px; }
  h2.section { font-size:21px; }
  .carte { grid-template-columns:76px minmax(0,1fr); padding:14px; gap:14px; }
  .carte-img { grid-column:auto; height:94px; }
  .carte-titre { font-size:15px; }
  .carte-lieu .badges { display:flex; margin:5px 0 0; }
  .metriques { gap:10px 16px; }
  .metrique .valeur,.metrique--cle .valeur { font-size:15px; }
  .carte-score { grid-column:1 / -1; flex-direction:row; justify-content:flex-end; flex-wrap:wrap; gap:8px; }
  .carte-score .score { width:34px; height:30px; font-size:17px; }
  .carte-score .score-libelle { margin:0 auto 0 -4px; max-width:52px; }
  .carte-score > button { width:auto; padding:7px 9px; }
  .outils-annonce { width:100%; }
  .outils-annonce > summary { text-align:right; }
  .carte-enchere { grid-template-columns:1fr; }
  .carte-enchere .carte-img { height:130px; }
}
</style>
</head>
<body>
<header class="masthead">
  <div class="masthead-inner">
    <div class="enseigne">
      <svg class="devanture" viewBox="0 0 48 48" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 20v20h32V20"/><path d="M8 40h32"/><path d="M14 40V28h8v12"/><rect x="27" y="28" width="9" height="7" rx="1"/><path d="M4 20c0-2 1-8 4-8h32c3 0 4 6 4 8"/><path d="M4 20c0 2.2 2 4 4.5 4S13 22.2 13 20c0 2.2 2 4 4.5 4s4.5-1.8 4.5-4c0 2.2 2 4 4.5 4s4.5-1.8 4.5-4c0 2.2 2 4 4.5 4s4.5-1.8 4.5-4c0 2.2 2 4 4.5 4S44 22.2 44 20"/></svg>
      <h1 class="wordmark">Les Murs<span class="point">.</span>
        <svg class="trait" width="208" height="8" viewBox="0 0 208 8" aria-hidden="true"><path d="M2 5 C 38 1.5, 66 7, 104 4 S 172 6.5, 206 2.5" stroke="var(--or-vif)" stroke-width="2.4" fill="none" stroke-linecap="round"/></svg>
      </h1>
    </div>
  </div>
</header>
<div class="auvent" aria-hidden="true"></div>
<div class="page">

  <nav class="onglets" id="onglets">
    <button type="button" class="onglet actif" data-vue="chasse">La chasse</button>
    <button type="button" class="onglet" data-vue="suivi">Mon suivi <span id="suivi-compteur"></span></button>
    <button type="button" class="onglet" data-vue="reponses">Réponses</button>
    <button type="button" class="onglet" data-vue="marche">Le marché</button>
  </nav>

  <div id="vue-suivi" style="display:none">
    <p class="marche-intro">Vos démarches, annonce par annonce — statut et notes sont mémorisés
      sur cet appareil uniquement (rien n'est envoyé nulle part). Choisissez un statut sur
      n'importe quelle carte de la chasse pour qu'elle apparaisse ici.</p>
    <div id="suivi-contenu"></div>
  </div>

  <div id="vue-reponses" style="display:none"><div id="reponses-contenu"></div></div>

  <div id="vue-marche" style="display:none">
    <p class="marche-intro" id="marche-intro"></p>
    <div class="periodes" id="marche-periodes"></div>
    <div class="grille-marche" id="marche-grille"></div>
    <p class="marche-pied">Chaque série est officielle, gratuite et citée : cliquez la source
      sous un graphique pour vérifier les chiffres vous-même. Actualisation environ une fois
      par mois — ces indicateurs bougent lentement, c'est leur pente qui compte.</p>
  </div>

  <div id="vue-chasse">
  <details class="volet-filtres" id="volet-filtres">
    <summary><span class="bouton-filtres"><svg class="icone-filtres" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M4 7h3m4 0h9M4 17h9m4 0h3"/><circle cx="9" cy="7" r="2"/><circle cx="15" cy="17" r="2"/></svg><span>Filtres</span><svg class="filtre-chevron" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m4 6 4 4 4-4"/></svg></span><span id="resume-filtres"></span></summary>
    <div class="filtres">
      <div class="filtre"><label for="f-texte">Ville, rue, référence</label>
        <input id="f-texte" type="search" placeholder="ex. Saint-Ouen" style="max-width:200px"></div>
      <div class="filtre"><label for="f-signal">Signal recherché</label><select id="f-signal">
        <option value="tous">Tous</option><option value="baisses">Prix en baisse</option>
        <option value="negociation">Pépites à négocier</option><option value="completer">Données à compléter</option><option value="coherent">Sans contradiction détectée</option>
        <option value="prudent">Trésorerie prudente positive</option></select></div>
      <div class="filtre"><label for="f-surface">Surface souhaitée : moins de (m²)</label>
        <input id="f-surface" type="number" min="1" step="1" value="40" placeholder="Toutes"></div>
      <div class="filtre"><label for="f-pepites">Opportunités hors critères</label>
        <label><input id="f-pepites" type="checkbox" checked> Inclure les pépites et potentiels à négocier plus grands ou plus loin</label></div>
      <div class="filtre"><label for="f-trajet">Trajet max estimé (min)</label>
        <input id="f-trajet" type="number" min="1" step="5" placeholder="Sans limite"></div>
      <div class="filtre"><label for="f-tri">Classer par</label><select id="f-tri">
        <option value="recherche">Score puis mes critères</option><option value="score">Score économique</option>
        <option value="prix">Prix croissant</option><option value="trajet">Proximité</option>
        <option value="recent">Dernière détection</option></select></div>
      <div class="filtre"><label for="f-archives">Disponibilité</label>
        <label><input id="f-archives" type="checkbox"> Inclure les archives et fiches retirées</label></div>
      <div class="filtre"><label for="f-type">Type</label>
        <select id="f-type">
          <option value="tous">Tous</option>
          <option value="murs_occupes">Murs occupés</option>
          <option value="murs_libres">Murs libres</option>
        </select></div>
      <div class="filtre"><label>Secteur (choix multiples)</label>
        <details class="multi" id="f-dep-boite">
          <summary id="f-dep-resume">Tous</summary>
          <div class="multi-liste" id="f-dep-liste">
            <label><input type="checkbox" value="18e"> Paris 18e (mon quartier)</label>
          </div>
        </details></div>
      <div class="filtre"><label for="f-rdt">Rendement min (%)</label>
        <input id="f-rdt" type="number" min="0" max="15" step="0.5" placeholder="ex. 6"></div>
      <div class="filtre"><label for="f-score">Score min</label>
        <input id="f-score" type="number" min="0" max="100" step="5" placeholder="ex. 60"></div>
      <div class="filtre"><label for="f-nouv">Fraîcheur</label>
        <label style="font-size:14px;color:var(--encre-1);padding:6px 0"><input id="f-nouv" type="checkbox"> Nouveautés seulement</label></div>
      <div class="filtre"><label for="f-cf">Cash-flow</label>
        <label style="font-size:14px;color:var(--encre-1);padding:6px 0"
          title="Masque les biens qui vous coûteraient de l'argent chaque mois AVEC VOTRE profil de financement. Le score, lui, est calculé à un financement de référence fixe pour rester comparable d'une annonce à l'autre : un bien bien noté peut donc afficher un cash-flow négatif si votre profil est plus prudent que cette référence."><input id="f-cf" type="checkbox"> Positif seulement</label></div>
      <details class="reglages-finance"><summary>Mon financement et ma fiscalité — modifier les hypothèses</summary><div class="reglages-contenu">
      <div class="profil-groupe" data-titre="Mon profil de financement" title="Votre profil de financement : il recalcule tous les cash-flows du site.">
        <div class="filtre"><label for="p-apport">Mon apport
          <select id="p-apport-mode" title="En % : l'apport suit le prix de chaque bien (comparable d'une annonce à l'autre). En € : une somme fixe, la même partout — plus concret quand on raisonne à partir de son épargne disponible.">
            <option value="pct">en %</option>
            <option value="euros">en €</option>
          </select></label>
          <input id="p-apport" type="number" min="0" step="5"></div>
        <div class="filtre"><label for="p-taux">Mon taux (%)</label>
          <input id="p-taux" type="number" min="0.1" max="10" step="0.1"></div>
        <div class="filtre"><label for="p-duree">Durée crédit (ans)
          <span class="info-i" id="p-arbitrage-i" title="Pour un cash-flow positif dès maintenant avec le moins d'apport possible : une durée plus longue (20-25 ans) allège nettement la mensualité, quitte à accepter un taux un peu supérieur — l'effet de la durée domine largement celui du taux dans les écarts pratiqués par les banques. Revers : plus d'intérêts payés au total, et un capital remboursé plus lentement. À l'inverse, une durée courte coûte moins cher au total mais exige une mensualité plus lourde dès le départ.">i</span></label>
          <input id="p-duree" type="number" min="5" max="30" step="1"></div>
        <button id="p-reset" type="button" title="Revenir aux hypothèses par défaut">↺</button>
      </div>
      <div class="profil-groupe" data-titre="Ma fiscalité (estimation)" title="Votre profil fiscal : estimation grossière pour comparer deux régimes, pas un calcul officiel.">
        <div class="filtre"><label for="p-regime">Ma fiscalité</label>
          <select id="p-regime">
            <option value="non_renseigne">Non renseigné</option>
            <option value="ir">Nom propre (revenus fonciers)</option>
            <option value="is">Société à l'IS</option>
          </select></div>
        <div class="filtre"><label for="p-tmi">Ma tranche d'imposition (TMI)
          <span class="info-i" title="Visible sur votre avis d'imposition — s'applique seulement au régime « nom propre ». Le calcul ajoute 17,2 % de prélèvements sociaux à cette tranche.">i</span></label>
          <select id="p-tmi">
            <option value="0">0 %</option>
            <option value="11">11 %</option>
            <option value="30">30 %</option>
            <option value="41">41 %</option>
            <option value="45">45 %</option>
          </select></div>
        <button id="p-fiscal-reset" type="button" title="Revenir à « non renseigné »">↺</button>
      </div>
      </div>
      <p class="profil-note">Ces réglages sont mémorisés sur cet appareil et recalculent les cash-flows du site.
        Le scénario prudent utilise une référence fixe, indiquée sur chaque fiche.</p>
      </details>
      <button id="f-reset" type="button">Réinitialiser</button>
      <span class="compteur" id="compteur"></span>
    </div>
    <div class="profil-note">Les champs dorés forment votre <b>profil de financement</b> :
      apport, taux et durée sont mémorisés sur cet appareil et recalculent instantanément
      les cash-flows, badges « s'autofinance » et textes « En clair » de toutes les annonces.
      <span id="taux-marche-note"></span>
      Le profil fiscal (tant que renseigné) ajoute un rendement net d'impôt <b>estimatif</b> —
      à confirmer avec votre expert-comptable, jamais un calcul officiel.</div>
  </details>

  <section id="bloc-prio"></section>
  <section id="bloc-etudier"></section>
  <details class="repli" id="bloc-verifier"><summary></summary><div id="verifier-liste"></div></details>
  <details class="repli" id="bloc-reste"><summary></summary><div id="reste-liste"></div></details>

  <details class="repli" id="bloc-encheres"><summary></summary><div id="encheres-liste"></div></details>

  <details class="repli exclues" id="exclues-bloc">
    <summary></summary>
    <table id="exclues-table"></table>
  </details>

  <details class="repli">
    <summary>La méthode Les Murs. — que vérifier avant de faire une offre</summary>
    <div class="methode">
      <p>La recherche porte sur l’achat immobilier des murs. Un fonds de commerce ou un droit au bail n’achète pas le local.
        Les offres sans preuve de vente des murs restent à confirmer, hors recommandations.
        <a href="https://bpifrance-creation.fr/encyclopedie/reprendre-entreprise-etapes/choisir-montage-juridique-fiscal/achat-dun-fonds-commerce" target="_blank" rel="noopener">Comprendre la distinction</a>.</p>
      <h4>Le bail (le vrai produit que vous achetez)</h4>
      <ul>
        <li>Date de signature et prochaine échéance triennale — un bail récent sécurise, un bail en fin de période se renégocie.</li>
        <li>Indexation (ILC de préférence) et loyer à jour des indexations.</li>
        <li>Vérifier l’inventaire des charges et la refacturation de la taxe foncière au bail.
          Les grosses réparations de l’article 606 restent au bailleur pour les baux conclus ou renouvelés depuis novembre 2014.
          <a href="https://entreprendre.service-public.gouv.fr/vosdroits/F32336" target="_blank" rel="noopener">Règles officielles</a>.</li>
        <li>Dépôt de garantie, garanties personnelles, destination des lieux (« tous commerces » vaut de l'or).</li>
      </ul>
      <h4>Le locataire (celui qui paie votre retraite)</h4>
      <ul>
        <li>Extrait Kbis, 3 derniers bilans, ancienneté dans les lieux.</li>
        <li>Loyer ≤ 8-10 % de son chiffre d'affaires : au-delà, il souffre, vous aussi bientôt.</li>
        <li>Incidents de paiement — demandez les quittances des 12 derniers mois.</li>
      </ul>
      <h4>L'immeuble et le local</h4>
      <ul>
        <li>3 derniers PV d'assemblée générale : ravalement ou toiture votés = argument de négo.</li>
        <li>État des sols/vitrine/électricité — « peu de travaux » se vérifie sur place.</li>
        <li>Conformité de la destination au règlement de copropriété.</li>
      </ul>
      <h4>L'énergie (le volet « ESG » qui compte à votre échelle)</h4>
      <ul>
        <li>Demandez le DPE même s'il n'est pas affiché — obligatoire à la vente, souvent « oublié » quand il est mauvais.</li>
        <li>Les interdictions de location F/G visent les logements, pas les baux commerciaux — mais les banques et les acheteurs de demain, eux, regardent déjà : une passoire se négocie aujourd'hui et se revend mal demain.</li>
        <li>Vitrine simple vitrage, chauffage électrique ancien, pas d'isolation : chiffrez avant l'offre (un devis gratuit vaut un argument de négociation chiffré).</li>
        <li>Qui paie l'énergie ? Un local énergivore fragilise le commerce du locataire — donc votre loyer.</li>
      </ul>
      <h4>La rue (la valeur à 10 ans)</h4>
      <ul>
        <li>Comptez les rideaux baissés dans la rue — plus de 2 sur 10, méfiance.</li>
        <li>Passez un mardi à 15 h ET un samedi à 11 h : le flux ne ment pas.</li>
        <li>Projets urbains (tram, piétonnisation, ZAC) : mairie et PLU en ligne.</li>
      </ul>
      <h4>Les chiffres à refaire vous-même</h4>
      <ul>
        <li>Rendement ACTE EN MAIN (droits ~7,5 % + honoraires), pas le brut affiché de l'agence.</li>
        <li>Provision vacance/impayés : comptez 1 mois de loyer par an de prudence.</li>
        <li>Fiscalité : revenus fonciers au réel (intérêts et travaux déductibles) — un avis d'expert-comptable vaut le détour avant d'acheter.</li>
      </ul>
      <h4>La négociation</h4>
      <ul>
        <li>Utilisez la ligne « Pour 7 % brut : offrir ≤ … » de chaque carte comme ancre.</li>
        <li>Toute offre par écrit, conditionnée à l'obtention du prêt et à la lecture du bail.</li>
        <li>Un « non » aujourd'hui devient souvent un « oui » à 60 jours — l'annonce reste en veille ici.</li>
      </ul>
    </div>
  </details>
  </div><!-- /vue-chasse -->

  <footer>
    <details class="infos-veille"><summary>À propos de la veille</summary>
    <details id="qualite-veille"><summary id="qualite-veille-resume">État de la collecte</summary>
      <div id="qualite-veille-detail"></div></details>
    <div class="hud" id="hud"></div>
    <div><strong>Santé des sources</strong> — dernier passage : <span id="pied-maj"></span></div>
    <div class="sante" id="sante"></div>
    <div class="legende" id="legende"></div>
    </details>
  </footer>
</div>

<div class="plateau" id="plateau"></div>
<div class="comparateur-fond" id="comparateur-fond" role="dialog" aria-modal="true" aria-label="Comparaison des biens">
  <div class="comparateur">
    <button class="fermer" id="comp-fermer">Fermer ✕</button>
    <h3>Face à face</h3>
    <div id="comp-table"></div>
  </div>
</div>
<div class="outil-fond" id="outil-fond" role="dialog" aria-modal="true" aria-label="Outil d’aide à la décision">
  <div class="comparateur">
    <button class="fermer" id="outil-fermer">Fermer ✕</button>
    <div id="outil-contenu"></div>
  </div>
</div>

<script id="donnees" type="application/json">__DONNEES__</script>
<script>
"use strict";
const D = JSON.parse(document.getElementById("donnees").textContent);
// Focus dans les outils, fermeture au clavier, retour au bouton d'origine.
let dialogueActif = null, focusAvantDialogue = null;
for (const id of ["outil-fond", "comparateur-fond"]) {
  const fond = document.getElementById(id);
  new MutationObserver(() => {
    if (fond.style.display === "block") {
      if (dialogueActif !== fond) focusAvantDialogue = document.activeElement;
      dialogueActif = fond;
      fond.querySelector("button")?.focus();
    } else if (dialogueActif === fond) {
      dialogueActif = null;
      focusAvantDialogue?.focus();
    }
  }).observe(fond, {attributes:true, attributeFilter:["style"]});
}
document.addEventListener("keydown", ev => {
  if (!dialogueActif) return;
  if (ev.key === "Escape") { dialogueActif.style.display = "none"; ev.preventDefault(); return; }
  if (ev.key !== "Tab") return;
  const elements = [...dialogueActif.querySelectorAll("button, a[href], input, select, textarea, [tabindex='0']")]
    .filter(e => !e.disabled && e.getClientRects().length);
  const premier = elements[0], dernier = elements[elements.length - 1];
  if (ev.shiftKey && document.activeElement === premier) { dernier?.focus(); ev.preventDefault(); }
  else if (!ev.shiftKey && document.activeElement === dernier) { premier?.focus(); ev.preventDefault(); }
});
const CLE_FILTRES = "veille-murs-filtres";
const CLE_COMP = "veille-murs-comparateur";
const CLE_PROFIL = "veille-murs-profil";
const CLE_FISCAL = "veille-murs-fiscal";
const CLE_MASQUEES = "veille-murs-masquees";

// Profil de financement de l'utilisateur : pilote TOUS les cash-flows du site
// (métriques, badges « s'autofinance », blocs « En clair », simulateur).
// 20 % par défaut : aligné sur l'apport de RÉFÉRENCE utilisé par le score
// (config scoring.financement.apport_reference_pct) — sans ça, le cash-flow
// affiché à 0 % d'apport contredisait au premier coup d'œil un score qui,
// lui, jugeait déjà le bien finançable à 20 %.
// apportMode : "pct" (part du coût acte en main) ou "euros" (somme fixe). Le %
// reste le défaut — il se compare d'un bien à l'autre — mais raisonner « j'ai
// 80 000 € à mettre, que donne chaque annonce ? » est souvent plus concret :
// l'épargne disponible, elle, ne varie pas avec le prix du bien.
const PROFIL_DEFAUT = {apport: 20, apportMode: "pct", apportEuros: 50000,
                       taux: D.analyse.financement.taux_pct,
                       duree: D.analyse.financement.duree_ans};
let profil = {...PROFIL_DEFAUT};
try { profil = {...PROFIL_DEFAUT, ...JSON.parse(localStorage.getItem(CLE_PROFIL) || "{}")}; }
catch (e) {}

// Profil fiscal : "non_renseigne" par défaut — on n'affiche RIEN tant que
// l'utilisateur n'a pas choisi, plutôt que de deviner. Ce n'est PAS un calcul
// fiscal officiel : IR ignore les charges déductibles réelles (travaux,
// intérêts d'emprunt…), IS ignore l'amortissement comptable — les deux
// dépendent trop du montage personnel pour être généralisés honnêtement.
// Sert à COMPARER deux régimes, pas à remplacer un expert-comptable.
const PROFIL_FISCAL_DEFAUT = {regime: "non_renseigne", tmi: 30};
let profilFiscal = {...PROFIL_FISCAL_DEFAUT};
try { profilFiscal = {...PROFIL_FISCAL_DEFAUT, ...JSON.parse(localStorage.getItem(CLE_FISCAL) || "{}")}; }
catch (e) {}

function rendementNetImpot(a) {
  if (profilFiscal.regime === "non_renseigne" || a.rendement_brut_pct == null || a.prix == null) return null;
  if (profilFiscal.regime === "ir") {
    const taux = profilFiscal.tmi / 100 + 0.172;  // TMI + prélèvements sociaux
    return {pct: a.rendement_brut_pct * (1 - taux), libelle: `Rdt net d'impôt (IR, TMI ${profilFiscal.tmi} %)`};
  }
  // IS : barème 15 % jusqu'à 42 500 €, 25 % au-delà — appliqué au loyer
  // annuel affiché, pas à un bénéfice comptable réel (amortissement non
  // modélisé, cf. commentaire du profil ci-dessus).
  const loyer = a.loyer_mensuel ?? a.loyer_mensuel_estime;
  if (loyer == null) return null;
  const loyerAnnuel = loyer * 12;
  const impot = loyerAnnuel <= 42500 ? loyerAnnuel * 0.15 : 42500 * 0.15 + (loyerAnnuel - 42500) * 0.25;
  return {pct: (loyerAnnuel - impot) / a.prix * 100, libelle: "Rdt net d'impôt (société à l'IS)"};
}

function finTxt() {  // description du financement courant, pour textes et infobulles
  const apportTxt = apportEstNul() ? "en crédit 100 %"
    : (profil.apportMode === "euros"
        ? `avec ${fmtEuros(profil.apportEuros)} d'apport`
        : `avec ${profil.apport} % d'apport`);
  return apportTxt + `, sur ${profil.duree} ans à ${String(profil.taux).replace(".", ",")} %`;
}
const LIBELLES_SCORE = {
  rendement: "Rendement", emplacement: "Emplacement",
  prix_m2_vs_benchmark: "Prix vs marché", financement: "Financement", fiscalite: "Fiscalité",
  proximite: "Trajet domicile", quartier: "Quartier 18e"
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
  horloge: '<svg class="ic" viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5"/><path d="M12 7v5l3.5 2"/></svg>',
  calc: '<svg class="ic" viewBox="0 0 24 24"><rect x="5" y="3" width="14" height="18" rx="2"/><path d="M8.5 7.5h7M8.5 12h.5M12 12h.5M15.5 12h.5M8.5 15.5h.5M12 15.5h.5M15.5 15.5v2.5"/></svg>',
  coche: '<svg class="ic" viewBox="0 0 24 24"><rect x="4" y="4" width="16" height="16" rx="3"/><path d="m8.5 12.5 2.5 2.5 5-5.5"/></svg>',
  banque: '<svg class="ic" viewBox="0 0 24 24"><path d="M12 3 3.5 8.5h17L12 3Z"/><path d="M5 8.5V17M9.7 8.5V17M14.3 8.5V17M19 8.5V17M3.5 17h17M3 20.5h18"/></svg>',
  enveloppe: '<svg class="ic" viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3.5 6 8.5 7 8.5-7"/></svg>',
  esprit: '<svg class="ic" viewBox="0 0 24 24"><path d="M9 3.5a4 4 0 0 0-3.8 5.3A3.5 3.5 0 0 0 6 15.5v.5a4 4 0 0 0 4 4h1.5"/><path d="M15 3.5a4 4 0 0 1 3.8 5.3A3.5 3.5 0 0 1 18 15.5v.5a4 4 0 0 1-4 4h-1.5"/><path d="M9 3.5v16.5M15 3.5v16.5M9 8h2.5M12.5 12H15M9 15h2"/></svg>'
};

let comparaison = [];
try { comparaison = JSON.parse(localStorage.getItem(CLE_COMP) || "[]"); } catch (e) {}

// Annonces retirées manuellement du haut du panier / à étudier de près : pas
// supprimées, juste reléguées dans « le reste du tableau de chasse » — utile
// pour un bien déjà vu/écarté sans avoir à baisser le score min.
let masquees = [];
try { masquees = JSON.parse(localStorage.getItem(CLE_MASQUEES) || "[]"); } catch (e) {}

// Carnet de chasse : statut et notes de VOS démarches, par annonce (local à
// cet appareil, rien n'est envoyé). Structure : {id: {statut, maj, note, instantane}}.
const CLE_SUIVI = "veille-murs-suivi";
let suivi = {};
try { suivi = JSON.parse(localStorage.getItem(CLE_SUIVI) || "{}"); } catch (e) {}

function basculerMasquage(id) {
  // La croix et le statut « Abandonnée » du suivi sont le MÊME geste (demande
  // utilisateur) : abandonner range l'annonce dans Mon suivi (notes conservées)
  // et la relègue dans le reste du tableau de chasse. L'ancienne liste des
  // masquées est migrée au passage.
  const i = masquees.indexOf(id);
  if (i >= 0) masquees.splice(i, 1);
  if (estAbandonnee(id)) {
    localStorage.setItem(CLE_MASQUEES, JSON.stringify(masquees));
    const s = suivi[id] || {};
    if (s.statut === "abandonnee") majSuivi(id, s.note ? "suivie" : "");
    else rendre();
  } else {
    localStorage.setItem(CLE_MASQUEES, JSON.stringify(masquees));
    majSuivi(id, "abandonnee");
  }
}

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
// Jours sur le marché : une date brute demande un calcul mental, un compteur
// est un argument de négociation immédiat (un bien qui traîne se négocie
// plus dur). Seuil à 90 j choisi large : en dessous, rien à en tirer.
function joursMarcheHtml(dateIso) {
  if (!dateIso) return "";
  const jours = Math.max(0, Math.round((Date.now() - new Date(dateIso)) / 86400000));
  const stale = jours >= 90;
  return ` · <span${stale ? ` class="jours-marche-stale" title="Un bien qui traîne depuis longtemps se négocie plus dur — bon point d'appui pour une offre."` : ""}>${jours} j sur le marché</span>`;
}
// Temps de bail restant, quand l'annonce donne une échéance explicite
// (jamais déduit) : un bail loin de toute échéance sécurise le cash-flow
// bien mieux qu'un point de rendement.
function bailEcheanceHtml(a) {
  if (a.bail_echeance_annee == null) return "";
  const restant = a.bail_echeance_annee - new Date().getFullYear();
  const classe = restant <= 2 ? "etiquette-moins" : "etiquette-plus";
  const texte = restant <= 0
    ? `Bail arrivé à échéance (${a.bail_echeance_annee})`
    : `Bail jusqu'en ${a.bail_echeance_annee} (~${restant} an${restant > 1 ? "s" : ""})`;
  return `<span class="etiquette ${classe}" title="Échéance déduite du texte de l'annonce — à confirmer par le bail avant toute offre.">${texte}</span>`;
}

function emplacementNumeroHtml(a) {
  if (!a.emplacement_numero) return "";
  const classe = a.emplacement_numero === "3" ? "etiquette-moins" : "etiquette-plus";
  const libelle = a.emplacement_numero === "1bis" ? "n°1 bis" : `n°${a.emplacement_numero}`;
  return `<span class="etiquette ${classe}" title="Classement d'emplacement donné par l'annonce elle-même (flux, visibilité) — jamais déduit, à vérifier sur place comme le reste.">Emplacement ${libelle}</span>`;
}

function taxeFonciereHtml(a) {
  if (a.taxe_fonciere_annuelle == null) return "";
  return `<span class="etiquette" title="Montant donné par l'annonce — déjà déduit du cash-flow affiché ci-dessus.">Taxe foncière ${fmtEuros(a.taxe_fonciere_annuelle)}/an</span>`;
}

function classeScore(s) {
  if (s == null) return "gris";
  if (s >= D.seuils.vert) return "vert";
  if (s >= D.seuils.orange) return "orange";
  return "gris";
}
function verdictMarche(a) {
  if (a.prix_m2 < a.marche_prix_m2_bas)
    return '<span class="bon">sous la fourchette du marché</span>';
  if (a.prix_m2 > a.marche_prix_m2_haut)
    return '<span class="mauvais">au-dessus du marché local</span>';
  const part = (a.prix_m2 - a.marche_prix_m2_bas) / (a.marche_prix_m2_haut - a.marche_prix_m2_bas);
  if (part <= 0.33) return '<span class="bon">dans le tiers bas de la fourchette</span>';
  if (part <= 0.66) return "au cœur de la fourchette locale";
  return "dans le tiers haut de la fourchette";
}

function jaugeMarcheHtml(a) {
  if (a.prix_m2 == null || a.marche_prix_m2_bas == null) return "";
  const bas = a.marche_prix_m2_bas, haut = a.marche_prix_m2_haut;
  const med = a.marche_prix_m2_median ?? (bas + haut) / 2;
  const cibleM2 = a.negociation?.prix_plafond && a.surface_m2 ? a.negociation.prix_plafond / a.surface_m2 : null;
  const min = Math.min(bas, a.prix_m2, cibleM2 ?? Infinity) * 0.85,
        max = Math.max(haut, a.prix_m2) * 1.1;
  const pos = v => Math.max(0, Math.min(100, (v - min) / (max - min) * 100));
  const cible = cibleM2 != null
    ? `<div class="cible" style="left:calc(${pos(cibleM2)}% - 5px)"
         title="Plafond simulé pour le seuil pépite et l’équilibre prudent : ${fmtEuros(Math.round(cibleM2))}/m². Voir les hypothèses de la proposition."></div>` : "";
  const cibleTxt = cibleM2 != null
    ? ` <span class="cible-txt">▲ plafond simulé : ${fmtEuros(Math.round(cibleM2))}/m²</span>` : "";
  const lecture = a.lecture_prix ? `<div class="lecture">${ech(a.lecture_prix)}</div>` : "";
  return `<div class="marche">
    <div><span class="marche-legende-bien">●</span> ce bien : <b>${fmtEuros(a.prix_m2)}/m²</b> — ${verdictMarche(a)}
      <span style="color:var(--encre-3)" title="écart à la médiane locale">(${a.decote_pct >= 0 ? "-" : "+"}${fmtPct(Math.abs(a.decote_pct))} vs médiane)</span>${cibleTxt}</div>
    <div class="marche-piste">
      <div class="ligne"></div>
      <div class="bande-marche" style="left:${pos(bas)}%;width:${pos(haut) - pos(bas)}%"></div>
      <div class="mediane" style="left:${pos(med)}%" title="médiane locale ${fmtEuros(med)}/m²"></div>
      ${cible}
      <div class="bien" style="left:calc(${pos(a.prix_m2)}% - 7px)" title="ce bien : ${fmtEuros(a.prix_m2)}/m²"></div>
    </div>
    <div class="marche-echelle"><span>${fmtEuros(bas)}/m²</span><span>médiane ${fmtEuros(med)}</span><span>${fmtEuros(haut)}/m²</span></div>
    ${a.benchmark_source ? `<div class="marche-source">Fourchette : ${ech(a.benchmark_source)}${a.benchmark_source.includes("DVF")
      ? ` <span class="info-i" title="DVF (« demandes de valeurs foncières », data.gouv.fr) : les prix effectivement payés chez le notaire pour des locaux commerciaux de cette commune, publiés en open data avec ~6 mois de retard. Fourchette = moitié centrale des ventes (P25-P75), comparaison à la médiane. Un garde-fou factuel, pas une expertise : l'état, l'emplacement précis et le bail de chaque local diffèrent.">i</span>`
      : ` <span class="info-i" title="Aucune vente réelle en nombre suffisant dans cette commune (source DVF) : la fourchette vient du référentiel interne de l'outil, rédigé à la main par grands secteurs — moins précis qu'un historique de ventes.">i</span>`}</div>` : ""}
    ${lecture}
  </div>`;
}

// Mêmes hypothèses prudentes que le score et le prix de négociation Python.
function exploitation(a, scenario = {}) {
  const loyer = scenario.loyer ?? a.loyer_mensuel ?? a.loyer_mensuel_estime;
  const vacance = scenario.vacance ?? D.recherche.vacance_prudente_pct ?? 8;
  const charges = scenario.charges ?? D.recherche.provision_charges_pct ?? 10;
  const taxeConnue = Number.isFinite(a.taxe_fonciere_annuelle) && a.taxe_fonciere_annuelle >= 0;
  const moisTaxe = D.analyse.dossier_banque?.taxe_fonciere_mois_loyer ?? 1;
  const taxe = scenario.taxe ?? (taxeConnue ? a.taxe_fonciere_annuelle : (loyer == null ? null : loyer * moisTaxe));
  return {loyer, vacance, charges, taxe,
    taxeEstimee: scenario.taxeEstimee ?? !taxeConnue,
    revenu: loyer == null ? null : loyer * (1 - (vacance + charges) / 100) - taxe / 12,
    stress: loyer == null ? null : loyer * .9 * (1 - Math.max(2/12, vacance/100) - charges/100) - taxe / 12};
}

function taxeFonciereTexte(a) {
  const e = exploitation(a);
  return e.taxe == null ? "Taxe foncière à préciser" :
    `Taxe foncière ${e.taxeEstimee ? "provisionnée" : "annoncée"} : ${fmtEuros(e.taxe)}/an`;
}

// --- Apport : pourcentage du coût, ou somme fixe en € (cf. PROFIL_DEFAUT) ---
// Une somme fixe est plafonnée au coût du bien : on ne peut pas apporter plus
// que ce qu'il coûte (sinon l'emprunt deviendrait négatif et la mensualité
// absurde sur les biens les moins chers).
function apportEurosPour(cout) {
  if (profil.apportMode === "euros")
    return Math.max(0, Math.min(profil.apportEuros, cout));
  return cout * profil.apport / 100;
}
function apportEstNul() {
  return profil.apportMode === "euros" ? !(profil.apportEuros > 0) : !(profil.apport > 0);
}
function apportLibelle() {  // « 20 % apport » / « 80 000 € apport »
  return profil.apportMode === "euros"
    ? `${fmtEuros(profil.apportEuros)} apport` : `${profil.apport} % apport`;
}

function cashflowMensuel(a) {
  const e = exploitation(a);
  if (e.revenu == null || a.prix == null || a.decision?.diagnostic?.bloquant) return null;
  const cout = a.prix * 1.08 + (a.honoraires || 0);
  const emprunt = cout - apportEurosPour(cout);
  return Math.round(e.revenu - (emprunt > 0 ? mensualite(emprunt, profil.taux, profil.duree) : 0));
}

function apportMinimalCashflowPositif(a) {
  // À quel apport le cash-flow devient-il positif, à VOTRE profil (taux/durée) ?
  // Distinct de la note "financement" du score (qui utilise un apport/taux DE
  // RÉFÉRENCE fixes, pour rester comparable d'un bien à l'autre) : ici on
  // répond à la question personnelle « avec MES conditions, il me faut combien ? »
  const loyer = a.loyer_mensuel ?? a.loyer_mensuel_estime;
  if (loyer == null || a.prix == null) return null;
  const revenu = exploitation(a).revenu;
  const cout = a.prix * 1.08 + (a.honoraires || 0);
  for (const apport of [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]) {
    const emprunt = cout * (1 - apport / 100);
    const m = emprunt > 0 ? mensualite(emprunt, profil.taux, profil.duree) : 0;
    // Le seuil est cherché en %, mais rendu AUSSI en € : c'est la somme que
    // l'acheteur doit réellement sortir, la seule qui se compare à son épargne.
    if (revenu - m >= 0) return {pct: apport, euros: Math.round(cout * apport / 100)};
  }
  return null;  // jamais positif, même à 90 % d'apport
}

function faitsClesHtml(a) {
  // Des faits concrets et sourcés, format mémo d'investisseur — jamais une
  // impression, toujours une donnée déjà calculée ailleurs sur la carte.
  const faits = [];
  if (a.decote_pct != null && a.decote_pct >= 5)
    faits.push(["plus", `Prix au m² inférieur de ${Math.round(a.decote_pct)} % aux biens comparables du secteur.`]);
  else if (a.decote_pct != null && a.decote_pct <= -5)
    faits.push(["moins", `Prix au m² supérieur de ${Math.round(-a.decote_pct)} % aux biens comparables — prime à justifier.`]);

  const apportMin = apportMinimalCashflowPositif(a);
  if (apportMin != null)
    faits.push(["plus", apportMin.pct === 0
      ? `Cash-flow positif même en crédit 100 % (${finTxt()}).`
      : `Cash-flow positif dès un apport de ${apportMin.pct} % — ${fmtEuros(apportMin.euros)} (${finTxt()}).`]);

  if (a.rue_categorie === "tres_commercante")
    faits.push(["plus", `Rue avec ${a.rue_nb_commerces} commerces actifs recensés à 150 m ; passage et demande locative à vérifier sur place.`]);
  else if (a.rue_categorie === "peu_commercante")
    faits.push(["moins", "Peu de commerces recensés autour du local ; vérifiez le passage et la demande locative sur place."]);

  if ((a.fiscalite_detectes || []).includes("tva_recuperable"))
    faits.push(["plus", "TVA récupérable pour l'acquéreur, d'après l'annonce."]);
  if ((a.fiscalite_detectes || []).includes("avantage_fiscal_zone"))
    faits.push(["plus", "Zone à avantage fiscal signalée (ZFU/QPV ou exonération) dans l'annonce."]);
  if ((a.fiscalite_detectes || []).includes("taxe_fonciere_elevee"))
    faits.push(["moins", "Taxe foncière signalée élevée dans l'annonce."]);

  if (a.nb_comparables_secteur != null && a.nb_comparables_secteur <= 1)
    faits.push(["moins", "Peu de ventes comparables récentes retenues dans ce secteur : valorisation plus incertaine."]);

  if (a.rue_nb_vacants != null && a.rue_nb_vacants >= 3)
    faits.push(["moins", `Vacance commerciale signalée à proximité (${a.rue_nb_vacants} locaux vacants ou fermés à 150 m).`]);

  if (a.dpe_classe === "F" || a.dpe_classe === "G")
    faits.push(["moins", `Passoire énergétique annoncée (DPE ${a.dpe_classe}) — décote à négocier, travaux d'énergie à chiffrer avant l'offre.`]);
  else if (a.dpe_classe === "A" || a.dpe_classe === "B")
    faits.push(["plus", `Très bonne classe énergie annoncée (DPE ${a.dpe_classe}).`]);
  if ((a.bonus_detectes || []).includes("travaux"))
    faits.push(["moins", "Travaux signalés dans l'annonce — à chiffrer avant toute offre."]);

  if (!faits.length) return "";
  return `<details class="faits-cles"><summary class="titre-bloc">Faits clés (${faits.length})</summary>
    <ul>${faits.map(([sens, texte]) => `<li class="fait-${sens}">${ech(texte)}</li>`).join("")}</ul></details>`;
}

function questionsReponsesHtml(a) {
  const suspect = (a.flags || []).includes("rendement_anormalement_eleve");
  const lignes = [];

  let visite;
  if (a.peut_etre_retiree) visite = `Vérifiez d'abord que l'annonce est toujours en ligne : plus revue depuis ${a.jours_sans_vue} jours, elle a probablement été vendue ou retirée.`;
  else if (suspect) visite = "À vérifier d'abord — le rendement affiché est suspect (voir l'alerte) avant d'envisager une visite.";
  else if ((a.score ?? 0) >= D.seuils.vert) visite = "Oui : un des mieux notés du moment, une visite est justifiée.";
  else if ((a.score ?? 0) >= D.seuils.affichage) visite = "Plutôt oui, checklist en main — des points corrects, sans être exceptionnel.";
  else visite = "Pas en priorité : d'autres biens mieux notés méritent votre temps d'abord.";
  lignes.push(["Ce bien vaut-il une visite ?", visite]);

  let urgence;
  if (suspect) urgence = "Non — vérifiez d'abord le bail et le loyer réel avant toute démarche.";
  else if (contactPrioritaire(a))
    urgence = "Contactez le vendeur en priorité : pépite récemment détectée. Confirmez la disponibilité et demandez les pièces avant toute offre.";
  else urgence = "Aucune urgence particulière détectée — prenez le temps de visiter et de vérifier.";
  lignes.push(["Dois-je faire une offre aujourd'hui ?", urgence]);

  lignes.push(["Le prix est-il cohérent ?",
    a.lecture_prix || "Pas assez de données de marché sur ce secteur pour se prononcer."]);

  const n = a.negociation;
  const negociation = n?.prix_plafond != null
    ? `Plafond simulé : ${fmtEuros(n.prix_plafond)} (${fmtPct(n.remise_pct)} sous le prix affiché), pour un score de ${n.score_cible}/100 et une trésorerie prudente à l’équilibre. Le vendeur peut refuser ; les pièces restent à vérifier.`
    : (n?.raisons || ["Pas assez de données pour chiffrer une proposition."]).join(" ");
  lignes.push(["À quel prix le dossier devient-il intéressant ?", negociation]);

  if (a.rang_score != null && D.stats.retenues) {
    lignes.push(["Est-ce mieux que les autres annonces du moment ?",
      `Se classe ${a.rang_score}ᵉ sur ${D.stats.retenues} annonces actuellement retenues par l'outil — pas les biens vus ailleurs, mais ceux suivis ici.`]);
  }

  return `<details class="questions-reponses"><summary class="titre-bloc">Ce que vous vous demandez sûrement</summary>
    ${lignes.map(([q, r]) => `<div class="qr-item"><div class="qr-q">${ech(q)}</div><div class="qr-r">${ech(r)}</div></div>`).join("")}
  </details>`;
}

function enClairHtml(a) {
  // Résumé pour quelqu'un qui ne connaît ni le score ni le jargon : l'argent
  // d'abord (cash-flow), la sûreté ensuite (emplacement), toujours honnête.
  const phrases = [];
  const loyer = a.loyer_mensuel ?? a.loyer_mensuel_estime;
  const cf = cashflowMensuel(a);
  const suspect = (a.flags || []).includes("rendement_anormalement_eleve");
  if (a.decision?.diagnostic?.bloquant) {
    phrases.push("Les données présentent une contradiction ou une information essentielle à confirmer. Clarifiez les alertes avec le vendeur avant de retenir une rentabilité.");
  } else if (cf == null) {
    phrases.push("Ni loyer ni estimation fiable : impossible de dire ce que ce bien rapporte sans creuser l'annonce.");
  } else if (suspect) {
    phrases.push(`Le vendeur promet ${fmtEuros(loyer)}/mois de loyer — un niveau anormalement élevé. À prouver par un bail signé avant d'y croire.`);
  } else if (a.type_murs === "murs_libres") {
    const base = a.loyer_confiance === "comparables"
      ? `estimé sur ${a.loyer_nb_comparables} loyers annoncés de locaux voisins occupés — à confirmer`
      : "estimé au référentiel du secteur — plus incertain";
    phrases.push(`Local vide : aucun loyer tant qu'un commerçant n'est pas trouvé. Au loyer ${base} (${fmtEuros(loyer)}/mois), financé ${finTxt()}, il ${cf >= 0 ? `laisserait ≈ ${fmtEuros(cf)}/mois` : `demanderait ≈ ${fmtEuros(-cf)}/mois de votre poche`}.`);
  } else if (cf >= 0) {
    phrases.push(`Financé ${finTxt()}, il resterait ≈ ${fmtEuros(cf)}/mois après crédit, provisions de vacance et charges, taxe foncière annoncée ou provisionnée ; avant impôt et assurance emprunteur.`);
  } else {
    phrases.push(`Financé ${finTxt()}, le loyer en place ne couvre pas tout : ≈ ${fmtEuros(-cf)}/mois à sortir de votre poche${apportEstNul() ? " — un apport ou une négociation réduit cet effort" : ""}.`);
  }
  // La rue MESURÉE (quand connue) prime sur le classement administratif : plus
  // précise, elle répond directement à « est-ce un coin sûr ou pas net ? ».
  if (a.rue_categorie === "peu_commercante")
    phrases.push(`Peu de commerces recensés (${a.rue_nb_commerces} à 150 m) : le passage réel et la demande locative restent à observer sur place.`);
  else if (a.rue_categorie === "tres_commercante")
    phrases.push(`Rue avec ${a.rue_nb_commerces} commerces actifs recensés à 150 m : indice local favorable, sans mesure du passage ni du délai de relocation.`);
  else {
    const emp = (a.detail_score || {}).emplacement ?? 0;
    if (emp >= 25) phrases.push("Paris intra-muros : la note de zone ne suffit pas à juger la rue, le passage et la demande locative.");
    else if (emp >= 20) phrases.push("Commune prioritaire de la grille : vérifier le passage et les commerces voisins sur place.");
    else if (emp >= 15) phrases.push("Petite couronne : emplacement à juger rue par rue.");
    else phrases.push("Secteur périphérique : la valeur dépend fortement de la rue exacte — visite indispensable.");
  }
  if (a.rue_nb_vacants != null && a.rue_nb_vacants >= 3)
    phrases.push(`⚠ ${a.rue_nb_vacants} locaux vacants ou fermés mesurés à 150 m : le secteur immédiat souffre peut-être d'une vacance commerciale — à vérifier sur place.`);
  if (a.temps_trajet_min != null && a.temps_trajet_min <= 20)
    phrases.push(`Et c'est à ≈ ${a.temps_trajet_min} min de chez vous : facile à surveiller.`);
  return `<div class="enclair"><span class="enclair-titre">En clair</span> ${phrases.join(" ")}</div>`;
}

function explicationPepiteHtml(a) {
  // Rare par construction (score ≥ seuil pépite) : on détaille CONCRÈTEMENT
  // ce qui justifie le niveau, plutôt qu'un simple superlatif.
  const d = a.detail_score || {};
  const atouts = [];
  if (d.rendement >= 32)
    atouts.push(`rendement bien noté dans sa zone (${fmtPct(a.rendement_brut_pct)} brut, ${d.rendement}/${D.maxima.rendement} pts)`);
  if (d.emplacement >= 20)
    atouts.push(`emplacement bien noté dans la grille (${d.emplacement}/25 pts)`);
  // La décote n'est PAS reprise ici : le badge près du titre et la jauge de
  // marché juste au-dessus la donnent déjà, chiffre à l'appui. Idem pour le
  // cash-flow (métrique en gros caractères + badge « s'autofinance »). Ce bloc
  // ne vaut que s'il apporte ce qu'on ne voit nulle part ailleurs — sinon il
  // dit trois fois la même chose et noie ses propres arguments.
  const signauxFavorables = {bail_recent:"bail récent", taxe_fonciere_locataire:"taxe foncière au locataire",
    enseigne_nationale:"enseigne nationale", bail_longue_duree_restante:"bail loin de son échéance"};
  const signaux = (a.bonus_detectes || []).filter(n => signauxFavorables[n]).map(n => signauxFavorables[n]);
  if (signaux.length) atouts.push(`signaux déclarés : ${signaux.join(", ")}`);
  if (a.rue_categorie === "tres_commercante" && a.rue_nb_commerces != null)
    atouts.push(`rue mesurée très commerçante (${a.rue_nb_commerces} commerces à 150 m)`);
  const liste = atouts.length ? atouts.join(" · ") : `score économique de ${a.score}/100 sur les données disponibles`;
  return `<div class="pepite-pourquoi">${IC.pepite} <b>Pourquoi une pépite :</b> ${liste}.
    Signal d’intérêt à partir de ${D.seuils.pepite}/100 ; le loyer reste déclaré par l’annonce.
    Bail, quittances, charges, copropriété et disponibilité à confirmer avant décision.</div>`;
}

function messageContact(a, mode = "court") {
  if (a.modeles_contact && D.modeles_contact) {
    const modele = D.modeles_contact[a.modeles_contact[mode]];
    if (modele) return modele.replace(/__REFERENCE__|__URL__|__LOYER__/g, cle => ({
      __REFERENCE__: `${a.titre} à ${a.ville}`, __URL__: a.url,
      __LOYER__: fmtEuros(a.loyer_mensuel) + "/mois"
    })[cle]);
  }
  return ["Bonjour,", "", a.url, "", "Ce bien est-il toujours disponible ?", "", "Cordialement,"].join(String.fromCharCode(10));
}

const CLE_BROUILLONS = "veille-murs-brouillons-v1";
let brouillonsContact = {};
try { brouillonsContact = JSON.parse(localStorage.getItem(CLE_BROUILLONS) || "{}") || {}; } catch (e) {}

function texteContact(a, mode) {
  const sauvegarde = brouillonsContact[a.id]?.textes?.[mode];
  if (typeof sauvegarde === "string") return sauvegarde;
  return mode === "negociation" ? (a.negociation?.message || "") : messageContact(a, mode);
}

function enregistrerBrouillons() {
  try { localStorage.setItem(CLE_BROUILLONS, JSON.stringify(brouillonsContact)); return true; }
  catch (e) { return false; }
}

function actionsContactHtml() {
  return `<div class="contact-actions">
    <button type="button" class="btn-outil" id="contact-copier">${IC.coche} Copier le message</button>
    <button type="button" class="btn-outil" id="contact-modele">Revenir au modèle</button>
    <span id="contact-copie-ok" role="status" style="display:none">Copié ✓</span>
  </div><span id="contact-brouillon" class="contact-brouillon" role="status">Vos modifications sont conservées sur cet appareil, par annonce et par étape. Aucun envoi automatique.</span>`;
}

function ouvrirContact(id) {
  const a = D.retenues.find(x => x.id === id);
  if (!a) return;
  const precedent = brouillonsContact[id]?.mode;
  const mode = ["court", "dossier", "relance"].includes(precedent) ? precedent : "court";
  document.getElementById("outil-contenu").innerHTML = `
    <h3>${IC.enveloppe} Contacter le vendeur — ${ech(a.titre)}</h3>
    <p style="font-size:13px;color:var(--encre-2)">Choisissez l’étape de votre démarche. Le message tient compte de l’occupation annoncée et des informations manquantes.
    Relisez-le avant de le copier ; aucun message n’est envoyé par l’application.</p>
    <div class="contact-modes" role="group" aria-label="Étape de contact">
      ${[["court", "1. Premier contact"], ["dossier", "2. Demander les pièces"], ["relance", "3. Relancer"]].map(([cle, label]) => `<button type="button" class="btn-outil${cle === mode ? " actif" : ""}" aria-pressed="${cle === mode}" data-contact-mode="${cle}" data-contact-id="${ech(id)}">${label}</button>`).join("")}
    </div>
    <label for="contact-texte">Message à personnaliser</label>
    <textarea id="contact-texte" class="contact-texte" data-contact-id="${ech(id)}" data-mode="${mode}" rows="15">${ech(texteContact(a, mode))}</textarea>
    ${actionsContactHtml()}`;
  document.getElementById("outil-contenu").insertAdjacentHTML("beforeend", `<p><button type="button" class="btn-outil" data-reponse-vendeur="${ech(id)}">J’ai sa réponse : l’analyser</button></p>`);
  document.getElementById("outil-fond").style.display = "block";
}

function ouvrirProposition(id) {
  const a = D.retenues.find(x => x.id === id), n = a?.negociation;
  if (!a || n?.prix_plafond == null) return;
  const h = n.hypotheses;
  const remiseMax = D.analyse.negociation?.remise_selection_max_pct ?? 35;
  const signe = v => `${v >= 0 ? "+" : "−"}${fmtEuros(Math.abs(v))}/mois`;
  document.getElementById("outil-contenu").innerHTML = `
    <h3>Étudier une proposition — ${ech(a.titre)}</h3>
    ${prixCashflowHtml(a, a.prix, "Prix demandé")}
    ${prixCashflowHtml(a, n.prix_ouverture ?? n.prix_plafond, "Prix à tenter · proposition de départ")}
    ${prixCashflowHtml(a, n.prix_plafond, "Plafond du modèle · maximum")}
    <p class="offre-note">Ces trois cash-flows utilisent votre financement : ${finTxt()}, avec les mêmes provisions de vacance, charges et taxe. Avant impôt, assurance emprunteur et travaux exceptionnels.</p>
    <p>${n.remise_pct > 0 ? `Le plafond demande une baisse de ${fmtEuros(n.remise_euros)} (−${fmtPct(n.remise_pct)}). ${n.remise_pct > remiseMax ? "Écart très important : ce scénario n’est pas promu dans la sélection." : n.remise_pct > 15 ? "Baisse importante à obtenir et à argumenter." : "Écart à discuter avec le vendeur."}` : "Le prix affiché remplit déjà les conditions du modèle."}
      L’acceptation du vendeur reste inconnue.</p>
    <p>Objectif du modèle : au moins ${fmtEuros(n.objectif_cashflow ?? D.analyse.negociation?.cashflow_cible_mensuel ?? 100)}/mois de cash-flow prudent. Au plafond avec le financement de référence : score simulé <b>${n.score_cible}/100</b> (actuel : ${a.score ?? "—"}),
      rendement brut ${fmtPct(n.rendement_cible_pct)}, trésorerie prudente <b>${signe(n.cashflow_cible)}</b>,
      scénario dégradé ${signe(n.stress_cible)}.</p>
    <p class="offre-note">Référence du modèle : ${h.apport_pct} % d’apport, ${h.duree_ans} ans à ${h.taux_pct} % ; avant impôt et assurance emprunteur. Ce prix cible est un plafond, pas un prix minimum à payer.</p>
    ${n.rendement_simule_eleve ? '<p class="offre-note">Le rendement simulé élevé provient du prix proposé plus bas ; le loyer annoncé reste identique et doit être justifié par le bail et les quittances.</p>' : ""}
    ${relocationHtml(a)}
    <button type="button" class="btn-outil" data-sim="${ech(a.id)}" data-sim-prix="${n.prix_plafond}">Tester ce prix avec mon financement</button>
    <details><summary>Comprendre le calcul et ses limites</summary>
      <p>Le plafond est le prix maximal trouvé sur une grille de ${fmtEuros(n.pas_euros)}, avec le seuil pépite et la marge mensuelle cible après provisions.
      Le loyer reste constant ; une baisse de prix ne résout pas un défaut du bien.
      Le point de départ ménage ${n.marge_ouverture_pct} % sous ce plafond, arrondis vers le bas, lorsque les contrôles restent satisfaits.
      Ce n’est ni une estimation de valeur, ni une prévision de négociation.</p>
      <p>Référence : ${h.apport_pct} % d’apport, ${h.duree_ans} ans à ${h.taux_pct} %, frais d’acquisition 8 %,
      honoraires séparés renseignés ajoutés (${fmtEuros(a.honoraires || 0)}). Coût total au plafond : ${fmtEuros(n.cout_total)}, apport : ${fmtEuros(n.apport_reference)}.
      Provisions : vacance ${h.vacance_pct} %, charges ${h.charges_pct} % ; taxe foncière ${fmtEuros(n.taxe_annuelle_retenue)}/an${n.taxe_estimee ? " provisionnée faute de montant connu" : " annoncée"}.
      Avant impôt, assurance emprunteur et travaux exceptionnels ; budget de travaux et base des honoraires à confirmer.</p>
      <p>${n.taxe_estimee ? "La taxe provisionnée doit être remplacée par l’avis réel. " : ""}La répartition des charges doit être vérifiée au bail :
      <a href="https://entreprendre.service-public.gouv.fr/vosdroits/F32336" target="_blank" rel="noopener">référence Service Public</a>.</p>
    </details>
    <p class="offre-note">Brouillon de discussion à personnaliser. Une offre d’achat formelle peut vous engager :
      <a href="https://www.service-public.gouv.fr/particuliers/vosdroits/F2753" target="_blank" rel="noopener">vérifier les conditions</a> avec votre notaire. Aucun envoi depuis l’application.</p>
    <label for="contact-texte">Message à personnaliser</label>
    <textarea id="contact-texte" class="contact-texte" data-contact-id="${ech(id)}" data-mode="negociation" rows="13">${ech(texteContact(a, "negociation"))}</textarea>
    ${actionsContactHtml()}`;
  document.getElementById("outil-fond").style.display = "block";
}

function ouvrirCritique(id) {
  const a = D.retenues.find(x => x.id === id);
  if (!a) return;
  const corps = a.critique_ia
    ? `<div class="critique-texte">${ech(a.critique_ia)}</div>
       <p class="critique-note">Généré automatiquement par Claude Haiku — un avis, pas une
       vérité : croisez-le toujours avec une visite et les pièces du dossier.</p>`
    : `<p class="critique-note">Pas encore disponible pour ce bien. La critique est générée pour
       les meilleures annonces, dans la limite du budget de chaque tournée — repassez plus tard,
       ou c'est que la fonctionnalité n'est pas configurée pour ce site.</p>`;
  document.getElementById("outil-contenu").innerHTML = `
    <h3>${IC.esprit} Critique IA — ${ech(a.titre)}</h3>
    ${corps}`;
  document.getElementById("outil-fond").style.display = "block";
}

const EXPLICATIONS = {
  rendement: "Loyer annuel divisé par le prix, avant charges et vacance. Le barème dépend de la zone : dans Paris, 3,5 % = 0 point et 8 % = maximum. Une estimation de zone perd 10 points ; une estimation sur au moins deux loyers annoncés de locaux occupés comparables perd 4 points. Les baux ne sont pas consultés : tous les loyers sont à justifier. Sous 7 % de rendement brut : pas de haut du panier. Consultez aussi le scénario prudent.",
  emplacement: a => {
    let base = "Où est la boutique ? Dans une rue passante, le commerçant gagne sa vie et paie son loyer ; dans une rue morte, il ferme. Paris = 25 pts, communes qui montent (Pantin, Saint-Ouen, Montreuil…) = 20, reste de la petite couronne = 15, centre-ville de grande couronne = 10, ailleurs = 5. Quand une rue précise est citée dans l'annonce, un signal mesuré (Base Adresse Nationale + densité de commerces OpenStreetMap à 150 m) ajuste ce chiffre de −4 à +4 pts, et pénalise les locaux vacants voisins.";
    if (a && a.rue_categorie) {
      const LIB = {tres_commercante: "très commerçante", commercante: "commerçante",
        calme: "calme", peu_commercante: "peu commerçante"};
      base += ` Ici : rue mesurée « ${LIB[a.rue_categorie] || a.rue_categorie} » (${a.rue_nb_commerces} commerce(s) actif(s) à 150 m${a.rue_nb_vacants ? `, ${a.rue_nb_vacants} vacant(s)` : ""}).`;
    }
    return base;
  },
  prix_m2_vs_benchmark: "Est-ce cher pour le quartier ? On compare le prix au m² à ce qui se vend autour — aux VENTES RÉELLES enregistrées chez le notaire (DVF) quand la commune en compte assez, sinon au référentiel interne. Nettement moins cher que le marché (−20 %) = 18 pts. Dans les prix = 8. Plus cher = 0.",
  financement: a => {
    let base = "Trésorerie prudente à un apport et un taux de référence fixes (20 % d'apport, taux du modèle), pour comparer les biens. Vacance, charges et taxe foncière annoncée ou provisionnée sont déduites. Trésorerie positive = 5 pts ; déficit inférieur à 10 % du loyer = 3 pts ; au-delà = 0. Votre profil personnel agit sur vos simulations, sans changer le score.";
    return base;
  },
  fiscalite: "Signaux fiscaux repérés dans l'annonce : TVA récupérable ou zone à avantage fiscal (+1,5 pt chacun), taxe foncière signalée élevée (−1,5 pt). Rien de mentionné = 2,5/5, neutre — une information absente n'est pas une mauvaise nouvelle en soi.",
  proximite: "Le temps de trajet estimé depuis chez vous, rue Francoeur (Paris 18e — Lamarck-Caulaincourt à 3 min à pied, Château Rouge à 12 min). Moins de 20 min = 3 pts, 20 à 40 min = 2, 40 à 60 min = 1. Un critère de confort, volontairement léger dans le score.",
  quartier: "Bonus de 2 pts si le bien est dans le 18e : votre quartier, que vous connaissez, et où vous pouvez passer à pied. Volontairement léger : connaître la rue ne rend pas un mauvais dossier meilleur.",
};

function explicationLoyer(a, loyer) {
  const m2 = a.surface_m2;
  const tauxM2An = m2 ? Math.round((loyer * 12) / m2) : null;
  if (a.loyer_confiance === "comparables") {
    return `Base : ${a.loyer_nb_comparables} loyers annoncés de locaux occupés de surface voisine (même code postal). Baux non consultés : estimation à confirmer.` +
      (tauxM2An != null ? `\nCalcul : ${m2} m² × ${tauxM2An} €/m²/an (médiane des loyers annoncés) ÷ 12 = ${fmtEuros(loyer)}/mois.` : "");
  }
  if (a.loyer_confiance === "benchmark") {
    return "Aucun bail réel voisin connu ici : estimation à partir d'un référentiel interne par secteur (data/benchmarks.json), pas une API officielle — fourchettes prudentes construites à la main (annonces constatées, études de réseaux spécialisés), à recouper vous-même (ex. observatoire local des loyers commerciaux)." +
      (tauxM2An != null ? `\nCalcul : ${m2} m² × ${tauxM2An} €/m²/an (référence secteur) ÷ 12 = ${fmtEuros(loyer)}/mois.` : "");
  }
  if (a.loyer_estime) {
    return "Loyer annoncé par le vendeur pour un local vide : une promesse, pas un bail signé — à faire confirmer avant d'y croire.";
  }
  return "Loyer réel du bail en cours, tel qu'indiqué dans l'annonce (pas une estimation).";
}

function explicationRendement(a, type) {
  const loyer = a.loyer_mensuel ?? a.loyer_mensuel_estime;
  const loyerAnnuel = loyer != null ? Math.round(loyer * 12) : null;
  if (type === "brut") {
    let t = "Rendement brut = loyer annuel ÷ prix affiché — ignore les frais d'acquisition (notaire, agence), donc toujours plus optimiste que le rendement « acte en main ».";
    if (loyerAnnuel != null && a.prix != null) t += `\nIci : ${fmtEuros(loyerAnnuel)}/an ÷ ${fmtEuros(a.prix)} = ${fmtPct(a.rendement_brut_pct)}.`;
    return t;
  }
  const coutActeEnMain = a.prix != null ? Math.round(a.prix * 1.08 + (a.honoraires || 0)) : null;
  let t = "Rendement acte en main = loyer annuel ÷ coût réel total (prix × 1,08 pour notaire/enregistrement, + honoraires d'agence si affichés séparément). C'est le chiffre le plus honnête : il reflète votre mise de fonds réelle.";
  if (loyerAnnuel != null && coutActeEnMain != null) t += `\nIci : ${fmtEuros(loyerAnnuel)}/an ÷ ${fmtEuros(coutActeEnMain)} (prix + ~8 % de frais${a.honoraires ? " + honoraires" : ""}) = ${fmtPct(a.rendement_acte_en_main_pct)}.`;
  return t;
}

function estAbandonnee(id) {
  return masquees.includes(id) || (suivi[id] || {}).statut === "abandonnee";
}

function evolutionPrixHtml(a) {
  // L'évolution du prix EN CLAIR sur la carte : chaque étape datée, puis la
  // variation totale — un vendeur qui baisse est un vendeur qui négocie.
  const hist = a.historique_prix || [];
  if (hist.length < 2) return "";
  // au-delà de 4 étapes : la première, puis les 3 dernières (l'histoire tient sur une ligne)
  const etapes = hist.length > 4 ? [hist[0], ...hist.slice(-3)] : hist;
  const abrege = hist.length > 4;
  const morceaux = etapes.map((p, i) => {
    const precedent = i > 0 ? etapes[i - 1].prix : null;
    const cls = precedent == null ? "" : p.prix < precedent ? " evo-baisse" : p.prix > precedent ? " evo-hausse" : "";
    return `<span class="evo-etape${cls}">${fmtEuros(p.prix)} <span class="evo-date">(${fmtDate(p.date)})</span></span>`;
  });
  const chaine = abrege
    ? `${morceaux[0]} → … → ${morceaux.slice(1).join(" → ")}`
    : morceaux.join(" → ");
  const total = (hist[hist.length - 1].prix / hist[0].prix - 1) * 100;
  const totalTxt = `${total < 0 ? "−" : "+"}${Math.abs(total).toLocaleString("fr-FR", {maximumFractionDigits: 1})} %`;
  return `<div class="evolution-prix"><span class="evo-titre">Prix demandé :</span> ${chaine}
    <b class="${total < 0 ? "evo-baisse" : "evo-hausse"}">${totalTxt}</b>${abrege ? `<span class="evo-date"> (${hist.length} étapes au total)</span>` : ""}</div>`;
}

function boutonMasquerHtml(id) {
  const deja = estAbandonnee(id);
  return `<button type="button" class="btn-masquer" data-masquer="${ech(id)}"
    title="${deja ? "Reprendre cette annonce : elle quitte « Abandonnée » et retrouve son classement normal." : "Abandonner cette annonce : statut « Abandonnée » dans Mon suivi, et elle descend dans « le reste du tableau de chasse » — rien n'est supprimé, vos notes restent."}">${deja ? "↺" : "×"}</button>`;
}

function fiabiliteRueHtml(a) {
  const voie = a.rue_voie ? `autour de « ${a.rue_voie} »` : "autour de l'adresse détectée";
  const t = `Ce qui est réellement mesuré : ${a.rue_nb_commerces} commerce(s) actif(s) recensés dans OpenStreetMap, ${voie}, dans un rayon de 150 m (adresse géocodée via la Base Adresse Nationale, service public gratuit).` +
    ` Ce n'est PAS un compteur de passage réel : pas de nombre de piétons/jour — seulement une densité de commerces autour d'un point.` +
    ` Limite à connaître : OpenStreetMap peut être incomplet ou daté sur certains secteurs, et la rue détectée dans le texte de l'annonce peut être approximative.`;
  return ` <span class="info-i" title="${ech(t)}">i</span>`;
}

function metroHtml(a) {
  if (a.rue_distance_metro_m == null) return "";
  const d = a.rue_distance_metro_m;
  const t = `Station de transport en commun la plus proche détectée dans OpenStreetMap, à ${d} m à vol d'oiseau de l'adresse géocodée (rayon de recherche : 800 m).` +
    ` À vol d'oiseau, pas en distance de marche réelle (détours, sens de circulation) — et OpenStreetMap peut manquer une station récente ou mal placer une entrée secondaire.`;
  return `<span class="badge badge-type" title="${ech(t)}">${IC.horloge} station à ~${d} m</span>`;
}

function fiabiliteVacanceHtml(a) {
  const voie = a.rue_voie ? `autour de « ${a.rue_voie} »` : "autour de l'adresse détectée";
  const t = `${a.rue_nb_vacants} local/locaux marqués vacants ou fermés dans OpenStreetMap, ${voie}, à 150 m — un indice de vacance commerciale du secteur, pas une statistique officielle.` +
    ` OpenStreetMap dépend de contributeurs bénévoles : un local peut avoir rouvert sans que la carte soit mise à jour, ou l'inverse — à vérifier sur place avant de s'en inquiéter.`;
  return ` <span class="info-i" title="${ech(t)}">i</span>`;
}

function pourquoiHtml(a) {
  const d = a.detail_score || {};
  const lignes = Object.entries(D.maxima).map(([cle, max]) => {
    const v = d[cle] ?? 0;
    const brut = EXPLICATIONS[cle];
    const exp = typeof brut === "function" ? brut(a) : brut;
    return `<div class="jauge"><span>${LIBELLES_SCORE[cle]}
        <span class="info-i" data-exp="${ech(exp || "")}">i</span></span>
      <div class="piste"><div data-l="${Math.max(0, Math.min(100, v / max * 100))}"></div></div>
      <span class="val">${v}/${max}</span></div>`;
  });
  const bonus = d.bonus_malus ?? 0;
  lignes.push(`<div class="jauge"><span>Bonus/malus</span><span></span>
    <span class="val">${bonus > 0 ? "+" : ""}${bonus}/5</span></div>`);
  return `<div class="pourquoi"><div class="titre-bloc">Pourquoi ce score</div>${lignes.join("")}</div>`;
}

function decisionHtml(a) {
  const d = a.decision, r = a.recherche;
  if (!d || !r) return "";
  const cf = d.cashflow_prudent;
  const diagnostic = d.diagnostic || {alertes:[], preuves:{}};
  const action = diagnostic.transaction && diagnostic.transaction.nature !== "murs" ? "Faire confirmer la vente des murs seuls" : diagnostic.bloquant ? "Vérifier les chiffres avant d’avancer" :
    d.loyer_estime ? "Confirmer le revenu locatif" : cf != null && cf < 0 ? "Étudier le prix et l’effort d’épargne" : "Demander les pièces pour qualifier le dossier";
  const montant = v => v == null ? "—" : `${v >= 0 ? "+" : "−"}${fmtEuros(Math.abs(v))}`;
  const NOMS = {prix:"Prix",surface_m2:"Surface",loyer_mensuel:"Loyer mensuel",code_postal:"Code postal",nature_transaction:"Nature de la vente"};
  const preuves = Object.entries(diagnostic.preuves || {}).flatMap(([champ, entrees]) => entrees.map(e =>
    `<tr><th scope="row">${NOMS[champ] || ech(champ)}</th><td>${ech(String(e.valeur))}${champ === "surface_m2" ? " m²" : ["prix","loyer_mensuel"].includes(champ) ? " €" : ""}</td>
      <td>${ech(e.origine)}<br>${fmtDate(e.observe_le)}</td></tr>`)).join("");
  return `<div class="decision">
    <div class="decision-action">${action}</div>
    <div class="priorite">Adéquation à votre recherche : ${r.score}/100
      ${r.petite_surface ? '<span class="badge badge-vert">Petite surface</span>' : ""}
      ${r.proche ? '<span class="badge badge-vert">Proche de chez vous</span>' : ""}</div>
    <p>Surface ${r.detail.surface}/40 · proximité ${r.detail.proximite}/30 · économie ${r.detail.economie}/30.
      Données renseignées : ${d.documentation} % des 5 repères (aucun document vérifié).</p>
    ${diagnostic.alertes.slice(0,2).map(e => `<p class="alerte-donnee ${e.niveau}">${ech(e.texte)}</p>`).join("")}
    ${cf == null ? `<p>${diagnostic.bloquant ? "Simulation suspendue : résoudre les contradictions de données." : "Scénario prudent indisponible : prix ou loyer manquant."}</p>` :
      `<div class="decision-chiffres"><div><span>Prudent · avant impôt</span><b>${montant(cf)}/mois</b></div>
       <div><span>Scénario dégradé</span><b>${montant(d.cashflow_stress)}/mois</b></div>
       <div><span>Rendement net prudent*</span><b>${fmtPct(d.rendement_net_prudent)}</b></div></div>
       <details><summary>Hypothèses, risque et prix d’équilibre</summary>
       <p>Prix d’équilibre simulé : <b>${fmtEuros(d.prix_equilibre)}</b> ; couverture de la dette : ${d.couverture_dette ?? "—"}× (1× = revenus nets égaux au crédit).
       Scénario dégradé : loyer −10 %, deux mois sans loyer par an ; effort d’épargne : ${fmtEuros(d.effort_annuel_stress)}/an.</p>
       <small>Référence fixe : ${d.apport_pct} % d’apport, ${d.duree_ans} ans à ${d.taux_pct} %, frais d’achat 8 %, plus honoraires séparés renseignés.
       Provisions : vacance ${d.vacance_pct} % et charges ${d.charges_pct} % du loyer ; ${ech(taxeFonciereTexte(a))}, déduite.
       Avant impôt, assurance emprunteur et travaux exceptionnels.
       *Net des provisions, avant financement et impôt. ${d.loyer_estime ? "Loyer estimé" : "Loyer annoncé"}, à justifier.
       Hypothèses de prudence, à remplacer par les montants réels ; ce prix n’est pas une estimation de valeur.</small></details>`}
    <details><summary>Origine des chiffres et points de vigilance</summary>
      ${diagnostic.transaction ? `<p><b>Nature de l’offre :</b> ${ech(diagnostic.transaction.motif)}${diagnostic.transaction.extrait ? ` — ${ech(diagnostic.transaction.origine)} : « ${ech(diagnostic.transaction.extrait)} »` : ""}</p>` : ""}
      ${diagnostic.alertes.map(e => `<p class="alerte-donnee ${e.niveau}">${ech(e.texte)}</p>`).join("")}
      <p>Fiche : ${a.etat_detail === "lu" ? "lue le " + fmtDate(a.date_detail_vue) : a.etat_detail === "retiree" ? "retirée ou introuvable" : a.etat_detail === "refuse" ? "accès refusé par le site" : a.etat_detail === "temporaire" ? "temporairement indisponible" : a.etat_detail === "pauvre" ? "contenu insuffisant" : "pas de lecture complète tracée"}.</p>
      ${preuves ? `<table class="preuves-table"><thead><tr><th>Repère</th><th>Valeur déclarée</th><th>Origine et date</th></tr></thead><tbody>${preuves}</tbody></table>` : "<p>Valeurs issues du stock historique : provenance détaillée non enregistrée avant cette mise à jour.</p>"}
      <small>Une donnée structurée ou annoncée ne constitue pas un document vérifié.</small></details>
    <details><summary>Les questions à poser avant d’avancer (${d.questions.length})</summary>
      <ul>${d.questions.map(q => `<li>${ech(q)}</li>`).join("")}</ul></details>
  </div>`;
}

function disponibiliteTexte(a) {
  return a.etat_detail === "retiree" ? "Fiche retirée ou introuvable" : `Non revue depuis ${a.jours_sans_vue} jours : disponibilité à confirmer`;
}

function cashflowAuPrix(a, prix) {
  return cashflowMensuel({...a, prix});
}

function prixCashflowHtml(a, prix, libelle) {
  const cf = cashflowAuPrix(a, prix);
  return `<div class="offre-prix-cashflow" data-prix-propose="${prix}">
    <div><span>${libelle}</span><b>${fmtEuros(prix)}</b></div>
    <div><span>Cash-flow prudent à ce prix</span><b data-cashflow-prix>${cf == null ? "Non calculable" : `${cf >= 0 ? "+" : "−"}${fmtEuros(Math.abs(cf))}/mois`}</b></div>
  </div>`;
}

function relocationHtml(a) {
  const r = a.decision?.relocation || a.negociation?.relocation;
  const niveau = r?.niveau || "a_verifier";
  const libelle = {favorable:"indices de rue favorables", vigilance:"points de vigilance", a_verifier:"à vérifier"}[niveau];
  return `<details class="relocation-annonce ${niveau}"><summary>Relocation : ${libelle}</summary>
    ${r?.favorables?.length ? `<ul>${r.favorables.map(t=>`<li>${ech(t)}</li>`).join("")}</ul>` : ""}
    ${r?.vigilances?.length ? `<ul>${r.vigilances.map(t=>`<li>${ech(t)}</li>`).join("")}</ul>` : ""}
    <p>À confirmer : ${ech((r?.a_confirmer || ["Adresse exacte, passage, activités autorisées et loyer de relocation"]).join(" ; "))}.</p>
    <small>Les recensements de commerces et de locaux vacants peuvent être incomplets. Ces indices ne prouvent ni la demande locative, ni le délai pour trouver un locataire.</small>
  </details>`;
}

function prixCibleHtml(a) {
  const n = a.negociation;
  if (n?.prix_plafond == null) {
    if (n?.prix_seuil_financier != null) {
      return `<div class="offre-cible financiere-seule">
        <div class="offre-entete"><strong>Prix à obtenir · seuil financier du modèle</strong>
          <button type="button" class="btn-outil" data-sim="${ech(a.id)}" data-sim-prix="${n.prix_seuil_financier}">Tester ce prix</button></div>
        ${prixCashflowHtml(a, n.prix_seuil_financier, "Prix maximum du modèle")}
        <p><b>Critères pépite non réunis.</b> Score ${n.score_seuil_financier}/100 simulés à ce prix (actuel : ${a.score ?? "—"}/100).</p>
        <p class="offre-note">Cash-flow avec votre financement : ${finTxt()}. Vacance, charges et taxe ${n.taxe_estimee ? "provisionnée" : "annoncée"} déduites · avant impôt et assurance. Ce prix ne valide ni le loyer, ni l’emplacement, ni l’accord du vendeur.</p>
      </div>`;
    }
    const raison = n?.raisons?.[0] || "Loyer, charges et disponibilité à confirmer.";
    return `<p class="offre-indisponible">Prix d’achat cible à déterminer : ${ech(raison)}</p>`;
  }
  const cf = cashflowAuPrix(a, n.prix_plafond);
  const signe = v => v == null ? "non calculable" : `${v >= 0 ? "+" : "−"}${fmtEuros(Math.abs(v))}/mois`;
  const vigilance = (a.decision?.relocation || n.relocation)?.niveau === "vigilance";
  const objectif = n.objectif_cashflow ?? D.analyse.negociation?.cashflow_cible_mensuel ?? 100;
  const adapte = cf != null && cf >= objectif;
  return `<div class="offre-cible">
    <div class="offre-entete"><strong>Prix à tenter en négociation</strong>
      <button type="button" data-offre="${ech(a.id)}">Étudier la proposition</button></div>
    ${prixCashflowHtml(a, n.prix_ouverture ?? n.prix_plafond, "Proposition de départ")}
    <p class="offre-plafond">Plafond du modèle : <b>${fmtEuros(n.prix_plafond)} maximum</b> → <b>${signe(cf)}</b> à ce prix.</p>
    <p class="offre-note">Cash-flows avec votre financement : ${finTxt()}. Vacance, charges et taxe ${n.taxe_estimee ? "provisionnée" : "annoncée"} déduites · avant impôt, assurance et travaux exceptionnels.</p>
    <details><summary>Objectif et score au plafond</summary><p>Objectif : +${fmtEuros(objectif)}/mois · <b>${n.score_cible}/100 simulés</b> (actuel : ${a.score ?? "—"}/100)${n.remise_pct > 0 ? ` · baisse de ${fmtPct(n.remise_pct)} à obtenir au plafond` : " · au prix affiché"}. Le prix de départ ménage une marge de discussion sous le plafond du modèle ; l’accord du vendeur reste à obtenir.</p></details>
    ${!adapte ? `<p class="alerte-donnee fort">Avec votre financement à ce prix : ${signe(cf)}. Ce plafond ne suffit pas à votre objectif ; ajustez le prix ou le financement dans le simulateur.</p>` : ""}
    ${vigilance ? '<p class="alerte-donnee fort">Emplacement à valider : une baisse de prix ne résout pas les risques de relocation.</p>' : ""}
  </div>`;
}

function carteHtml(a, options) {
  const cf = cashflowMensuel(a);
  const suspect = (a.flags || []).includes("rendement_anormalement_eleve");
  const prixSuspect = (a.flags || []).includes("prix_m2_anormalement_bas") || a.decision?.diagnostic?.bloquant;
  const badges = [];
  badges.push(`<span class="badge badge-type">${a.decision?.diagnostic?.occupation === "a_confirmer" ? "Occupation à confirmer" : a.type_murs === "murs_occupes" ? "Murs occupés" : "Murs libres"}</span>`);
  if (a.decision?.diagnostic?.transaction && a.decision.diagnostic.transaction.nature !== "murs")
    badges[0] = '<span class="badge badge-alerte">Vente des murs à confirmer</span>';
  if ((a.decote_pct ?? 0) >= 15 && !suspect && !prixSuspect) {
    // La confiance de la décote dépend de sa source : des ventes réelles DVF
    // valent bien plus qu'un référentiel écrit à la main — un écart qu'on
    // voyait déjà dans la jauge dépliée (marche-source), mais pas sur ce
    // badge compact, le seul visible en scannant vite toute la liste.
    const dvf = (a.benchmark_source || "").includes("DVF");
    const titre = dvf
      ? `Prix affiché ${Math.round(a.decote_pct)} % sous le prix/m² MÉDIAN du marché local — ${a.benchmark_source}. Une vraie décote… ou un défaut caché : lisez la ligne d'explication du prix.`
      : `Prix affiché ${Math.round(a.decote_pct)} % sous un référentiel interne écrit à la main (pas assez de ventes réelles DVF dans cette commune) — moins fiable qu'un historique de ventes. Une vraie décote… ou un défaut caché : lisez la ligne d'explication du prix.`;
    badges.push(`<span class="badge badge-decote${dvf ? "" : " badge-decote-estime"}" title="${titre}">−${Math.round(a.decote_pct)}% vs marché${dvf ? "" : " (est.)"}</span>`);
  }
  if (a.est_nouvelle) badges.push(`<span class="badge badge-nouveau">${IC.etincelle} nouveau</span>`);
  if (a.peut_etre_retiree)
    badges.push(`<span class="badge badge-alerte">${IC.alerte} ${disponibiliteTexte(a)}</span>`);
  if (suspect)
    badges.push(`<span class="badge badge-alerte">${IC.alerte} rendement à vérifier</span>`);
  if (prixSuspect)
    badges.push(`<span class="badge badge-alerte" title="Prix affiché sous le seuil plausible pour ce secteur (€/m²) — probablement une incohérence entre le prix et la surface indiqués par l'annonce (parfois la surface d'un ensemble plus grand que le lot vendu), pas une vraie affaire. Score plafonné et décote masquée en attendant vérification.">${IC.alerte} prix/m² incohérent — à vérifier</span>`);
  if ((a.flags || []).includes("localisation_incoherente"))
    badges.push(`<span class="badge badge-alerte" title="Le nom de ville (banlieue) et le code postal (parisien) se contredisent — c'est souvent le code postal de l'AGENCE, pas du bien. L'emplacement a été noté d'après la ville, plus fiable ; vérifiez l'adresse réelle avant toute démarche.">${IC.alerte} localisation à vérifier</span>`);
  if ((a.flags || []).includes("rendement_sous_objectif"))
    badges.push(`<span class="badge badge-type" title="Rendement brut sous votre objectif de ${D.analyse.rendement_cible_pct} % : quel que soit le reste du dossier, ce bien ne peut pas entrer au haut du panier — les points d'emplacement ne paient pas un crédit. Il reste visible ici, et une négociation du prix peut changer la donne.">rendement sous objectif</span>`);
  if ((a.flags || []).includes("texte_partiel_alerte"))
    badges.push(`<span class="badge badge-alerte" title="Cette annonce vient d'une alerte email, qui n'en livre qu'un extrait : un titre générique et quelques lignes. Le filtre anti-fonds-de-commerce — le piège n°1 de ce marché — n'a donc presque rien à lire ici, et un fonds peut passer pour des murs. Cas réel rencontré : une « Vente Boucherie, Charcuterie » notée 88 était un fonds, la mention ne figurant que sur la page de l'annonce. Son score est plafonné juste sous le seuil « pépite » tant que vous n'avez pas ouvert l'annonce. Ouvrez le lien : si le texte parle de murs, c'est un vrai dossier.">texte partiel — ouvrez l'annonce</span>`);
  if ((a.flags || []).includes("pepite_sur_loyer_estime"))
    badges.push(`<span class="badge badge-type" title="Le score de ce bien reposait sur un loyer ESTIMÉ à partir d'une moyenne de zone (ou d'un loyer annoncé par le vendeur sur des murs libres) — jamais un bail signé. C'est assez solide pour bien le classer, pas pour déclencher une alerte « pépite » : son score est donc plafonné juste sous ce seuil. Faites confirmer le loyer réellement praticable, et ce bien peut redevenir un dossier de tête.">score plafonné · loyer à confirmer</span>`);
  if (cf != null && cf >= 0 && !suspect) {
    const reel = a.loyer_mensuel != null && !a.loyer_estime;
    badges.push(`<span class="badge badge-autofinance" title="${reel
      ? `Avec votre financement (${finTxt()}), le loyer annoncé couvrirait le crédit, les provisions de vacance et charges et la taxe foncière. ${taxeFonciereTexte(a)}. Avant impôt et assurance ; pièces à vérifier.`
      : `Au loyer estimé, le scénario prudent serait à l'équilibre (${finTxt()}). Revenu et charges à confirmer.`}">${IC.etincelle} ${reel ? "équilibre prudent" : "équilibre estimé"}</span>`);
  }
  // Contrepartie honnête du badge ci-dessus. Le score juge le BIEN (rendement
  // 37 pts, emplacement 25, prix vs marché 18 — le financement n'en pèse que
  // 5, à un profil de RÉFÉRENCE fixe pour rester comparable d'une annonce à
  // l'autre). Le cash-flow, lui, dépend de VOTRE profil. Un bien peut donc
  // être excellent et vous coûter quand même de l'argent chaque mois : c'était
  // affiché sans être expliqué, et ça se lisait comme une contradiction.
  else if (cf != null && cf < 0)
    badges.push(`<span class="badge badge-alerte" title="Le score note le BIEN — ce qu'il rapporte (37 pts), où il est (25 pts), son prix face au marché (18 pts). Le financement n'y pèse que 5 points, calculé à un profil de RÉFÉRENCE identique pour toutes les annonces, sans quoi le score ne serait plus comparable de l'une à l'autre. Ce montant-ci, lui, est calculé avec VOTRE profil (${finTxt()}) : un bien très bien noté peut donc vous coûter de l'argent chaque mois. Plus d'apport, une durée plus longue ou un prix négocié le ramènent à l'équilibre.">${fmtEuros(Math.abs(cf))}/mois à sortir</span>`);
  // Emplacement mesuré RUE PAR RUE (Base Adresse Nationale + densité de
  // commerces OpenStreetMap à 150 m) — un signal au-delà du simple classement
  // administratif, pour repérer une rue vraiment isolée dans un bon secteur.
  if (a.rue_categorie === "peu_commercante")
    badges.push(`<span class="badge badge-alerte">${IC.alerte} rue peu commerçante${fiabiliteRueHtml(a)}</span>`);
  else if (a.rue_categorie === "tres_commercante")
    badges.push(`<span class="badge badge-rue-plus">${IC.loupe} rue commerçante mesurée${fiabiliteRueHtml(a)}</span>`);
  if (a.rue_nb_vacants != null && a.rue_nb_vacants >= 3)
    badges.push(`<span class="badge badge-alerte">${IC.alerte} vacance commerciale proche${fiabiliteVacanceHtml(a)}</span>`);
  if (metroHtml(a)) badges.push(metroHtml(a));
  if (a.dpe_classe === "F" || a.dpe_classe === "G")
    badges.push(`<span class="badge badge-alerte" title="Classe énergie ${a.dpe_classe} annoncée. Les interdictions de location F/G visent les logements, PAS les baux commerciaux — mais une passoire se paie quand même : factures du locataire (sa capacité à payer le loyer), décote croissante à la revente, banques plus frileuses. Un devis d'isolation/chauffage avant l'offre transforme ce défaut en argument de négociation.">${IC.alerte} passoire énergétique (DPE ${a.dpe_classe})</span>`);
  else if (a.dpe_classe === "A" || a.dpe_classe === "B")
    badges.push(`<span class="badge badge-rue-plus" title="Classe énergie ${a.dpe_classe} annoncée : charges faibles pour le locataire, bien mieux armé face aux futures exigences réglementaires et aux critères des banques.">${IC.etincelle} DPE ${a.dpe_classe}</span>`);
  if ((a.flags || []).includes("dette_copropriete"))
    badges.push(`<span class="badge badge-alerte" title="L'annonce mentionne des dettes ou une procédure de copropriété. Cela peut se négocier (le prix en tient parfois déjà compte), mais exigez le pré-état daté et le montant exact AVANT toute offre — un acheteur hérite de la quote-part de dette au prorata de sa surface.">${IC.alerte} dettes de copropriété</span>`);

  // Historique de prix : un vendeur qui baisse son prix dans le temps est un
  // signal de négociation précieux, pas seulement une donnée de plus.
  const hist = a.historique_prix || [];
  if (hist.length >= 2) {
    const premier = hist[0].prix, dernier = hist[hist.length - 1].prix;
    if (dernier < premier) {
      const baisse = Math.round((1 - dernier / premier) * 100);
      badges.push(`<span class="badge badge-rue-plus" title="Prix baissé de ${fmtEuros(premier)} à ${fmtEuros(dernier)} (−${baisse} %) depuis le ${fmtDate(hist[0].date)} — ${hist.length - 1} changement(s) observé(s). Un vendeur qui baisse son prix dans le temps est prêt à négocier : bon point d'appui pour une offre.">${IC.etincelle} prix baissé −${baisse} %</span>`);
    } else if (dernier > premier) {
      const hausse = Math.round((dernier / premier - 1) * 100);
      badges.push(`<span class="badge badge-type" title="Prix relevé de ${fmtEuros(premier)} à ${fmtEuros(dernier)} depuis le ${fmtDate(hist[0].date)}.">prix relevé +${hausse} %</span>`);
    }
  }

  // Carrousel : toutes les photos connues du bien
  const photos = (a.images && a.images.length) ? a.images : (a.image_url ? [a.image_url] : []);
  const img = photos.length
    ? `<img src="${ech(photos[0])}" alt="" loading="lazy" referrerpolicy="no-referrer"
         onerror="this.closest('.carte-img').innerHTML=IC.boutique">` +
      (photos.length > 1
        ? `<button type="button" class="car-btn prec" data-car="-1" title="photo précédente">‹</button>
           <button type="button" class="car-btn suiv" data-car="1" title="photo suivante">›</button>
           <span class="car-compteur">1/${photos.length}</span>`
        : "")
    : IC.boutique;

  const liens = (a.urls_multiples || []).map((u, i) =>
    ` · <a href="${ech(u)}" target="_blank" rel="noopener">aussi vu ici (${i + 2})</a>`).join("");

  // Faits DÉTECTÉS dans le texte de l'annonce (sourcés, jamais supposés)
  const FAITS = {
    bail_recent: ["Bail récent (annonce)", "plus"],
    taxe_fonciere_locataire: ["Taxe foncière au locataire (annonce)", "plus"],
    enseigne_nationale: ["Enseigne nationale (annonce)", "plus"],
    travaux: ["Travaux signalés (annonce)", "moins"],
    bail_longue_duree_restante: ["Bail loin de toute échéance (annonce)", "plus"],
    echeance_bail_proche: ["Échéance de bail proche (annonce)", "moins"],
  };
  const etiquettesExtra = [bailEcheanceHtml(a), emplacementNumeroHtml(a), taxeFonciereHtml(a)].filter(Boolean);
  const etiquettes = (a.caracteristiques || []).map(c =>
    `<span class="etiquette">${ech(c)}</span>`)
    .concat((a.bonus_detectes || []).filter(n => FAITS[n]).map(n =>
      `<span class="etiquette etiquette-${FAITS[n][1]}">${FAITS[n][0]}</span>`))
    .concat(etiquettesExtra)
    .join("");

  const loyer = a.loyer_mensuel ?? a.loyer_mensuel_estime;
  const estimeSansBail = (a.loyer_mensuel == null && a.loyer_mensuel_estime != null) || a.loyer_estime;
  const est = estimeSansBail ? ` <small>est.</small>` : "";
  const loyerInfo = loyer == null ? "" :
    ` <span class="info-i" title="${ech(explicationLoyer(a, loyer))}">i</span>`;
  const rdtBrutInfo = a.rendement_brut_pct == null ? "" :
    ` <span class="info-i" title="${ech(explicationRendement(a, "brut"))}">i</span>`;
  const rdtActeInfo = a.rendement_acte_en_main_pct == null ? "" :
    ` <span class="info-i" title="${ech(explicationRendement(a, "acte"))}">i</span>`;
  const cfHtml = cf == null ? "—" :
    `<span style="color:${cf >= 0 ? "var(--vert-texte)" : "var(--alerte-texte)"}">${cf >= 0 ? "+" : "−"}${fmtEuros(Math.abs(cf))}/mois</span>` +
    (suspect ? `<span title="Calculé sur le loyer PROMIS par le vendeur — un tel niveau est
      presque toujours irréaliste : à prouver par un bail avant d'y croire."> ⚠</span>` : "") +
    `<span class="info-i" data-sim="${ech(a.id)}"
      title="Scénario prudent avec votre profil : ${finTxt()}. Loyer moins crédit, vacance et charges provisionnées. ${ech(taxeFonciereTexte(a))}, déduite. Avant impôt et assurance. Cliquez pour simuler.">i</span>`;
  const fiscal = rendementNetImpot(a);
  const fiscalHtml = fiscal == null ? "" : fmtPct(fiscal.pct) +
    ` <span class="info-i" title="Estimation grossière pour COMPARER deux régimes, pas un calcul fiscal officiel — ` +
    `${profilFiscal.regime === "ir" ? "ignore les charges déductibles réelles (travaux, intérêts d'emprunt…)" : "ignore l'amortissement comptable"}. ` +
    `À confirmer avec votre expert-comptable. Réglable dans « Filtres & réglages ».">i</span>`;
  // Trois niveaux de lecture : les deux chiffres qui DÉCIDENT (rendement,
  // cash-flow), ceux qui situent le bien (prix, surface, loyer), puis le
  // détail qu'on ne consulte qu'une fois intéressé.
  const metriques = [
    ["Prix", fmtEuros(a.prix), ""],
    ["Surface", a.surface_m2 == null ? "—" : new Intl.NumberFormat("fr-FR").format(a.surface_m2) + " m²", ""],
    ["Loyer/mois", loyer == null ? "—" : fmtEuros(loyer) + est + loyerInfo, ""],
    ["Rdt brut", fmtPct(a.rendement_brut_pct) + (a.rendement_brut_pct != null ? est : "") + rdtBrutInfo, "cle"],
    ["Prudent · mon profil", cf == null ? "—" :
      `${cf >= 0 ? "+" : "−"}${fmtEuros(Math.abs(cf))}/mois`, "cle"],
    ["Trajet", a.temps_trajet_min == null ? "—" : "≈ " + a.temps_trajet_min + " min", ""],
  ].map(([l, v, rang]) =>
    `<div class="metrique${rang ? " metrique--" + rang : ""}"><div class="libelle">${l}</div><div class="valeur">${v}</div></div>`).join("");

  const tampon = options.medaille != null
    ? `<div><span class="tampon">${TAMPONS[options.medaille]}</span></div>` : "";
  const pepite = estPepite(a);
  const prioriteContact = contactPrioritaire(a);
  const exceptions = options.exceptions || [];
  const dansComp = comparaison.includes(a.id);

  // Un badge discret suffit : le motif de l'exception reste lisible sans
  // ouvrir l'analyse, sans rajouter de bandeau au-dessus des annonces.
  return `<article class="carte${options.prio ? " prio" : ""}${options.medaille === 0 ? " podium-1" : ""}${pepite ? " rang-s" : ""}"
      style="animation-delay:${(options.index || 0) * 45}ms">
    ${boutonMasquerHtml(a.id)}
    <div class="carte-img" data-id="${ech(a.id)}" data-idx="0">${img}</div>
    <div>
      <div class="carte-titre"><a href="${ech(a.url)}" target="_blank" rel="noopener">${ech(a.titre)}</a>
        </div>
      <div class="carte-lieu">${ech(a.ville)}${a.code_postal ? " (" + ech(a.code_postal) + ")" : ""}
        <span class="badges">${pepite ? '<span class="badge badge-pepite" title="Signal économique fondé sur les données de l’annonce. Bail, charges et disponibilité à vérifier.">Pépite à étudier</span>' : estPotentiel(a) ? '<span class="badge badge-pepite">Potentiel à négocier</span>' : ""}${badges[0] || ""}${a.decision?.diagnostic?.bloquant ? '<span class="badge badge-alerte">Chiffres à vérifier</span>' : ""}</span></div>
      ${exceptions.length ? `<div class="exception-recherche">Hors de vos préférences : ${exceptions.map(ech).join(" · ")}</div>` : ""}
      <div class="metriques">${metriques}</div>
      ${prixCibleHtml(a)}
      ${relocationHtml(a)}
      <details class="analyse-annonce"${prioriteContact ? " open" : ""}><summary>${prioriteContact ? "Contact prioritaire · analyse et vérifications" : "Voir l’analyse et les informations à vérifier"} <span aria-hidden="true">⌄</span></summary>
      <div class="analyse-contenu">
      <p class="provenance-annonce">${ech(a.source || "source non renseignée")} · détectée le ${fmtDate(a.date_premiere_vue)}${joursMarcheHtml(a.date_premiere_vue)}${liens}</p>
      <div class="badges">${badges.slice(1).join("")}</div>
      ${etiquettes ? `<div class="etiquettes">${etiquettes}</div>` : ""}
      <p>Rendement acte en main : ${fmtPct(a.rendement_acte_en_main_pct)}${rdtActeInfo}${fiscal ? ` · ${fiscal.libelle} : ${fiscalHtml}` : ""}.</p>
      <p>${apportEstNul() ? "Cash-flow crédit 100 %" : `Cash-flow (${apportLibelle()})`} : ${cfHtml}.</p>
      ${decisionHtml(a)}
      ${a.negociation?.prix_plafond == null ? `<p class="offre-note">Prix cible pépite : ${ech((a.negociation?.raisons || ["Données à compléter."]).join(" "))}</p>` : ""}
      ${evolutionPrixHtml(a)}
      ${a.decision?.diagnostic?.bloquant ? "" : jaugeMarcheHtml(a)}
      ${a.decision?.diagnostic?.bloquant ? "" : enClairHtml(a)}
      ${pepite ? explicationPepiteHtml(a) : ""}
      ${faitsClesHtml(a)}
      ${questionsReponsesHtml(a)}
      ${pourquoiHtml(a)}
      </div></details>
    </div>
    <div class="carte-score">
      <div class="score ${classeScore(a.score)}">${a.score ?? "—"}</div>
      <div class="score-libelle">actuel /100</div>
      <button type="button" class="btn-outil btn-outil--primaire" data-contact="${ech(a.id)}"
        title="Génère un message personnalisé à copier-coller pour contacter le vendeur : visite, offre, documents manquants.">${IC.enveloppe} Contacter</button>
      <button type="button" class="btn-outil" data-sim="${ech(a.id)}">${IC.calc} Financer</button>
      <details class="outils-annonce"><summary>Plus d’actions</summary>
      <button type="button" class="btn-outil" data-reponse-vendeur="${ech(a.id)}">Analyser une réponse vendeur</button>
      <button type="button" class="btn-comp${dansComp ? " actif" : ""}" data-id="${ech(a.id)}">
        ${IC.balance} ${dansComp ? "Comparé" : "Comparer"}</button>
      <button type="button" class="btn-outil" data-check="${ech(a.id)}">${IC.coche} ${nbChecklist(a)}</button>
      <button type="button" class="btn-outil${a.critique_ia ? " a-critique" : ""}" data-critique="${ech(a.id)}"
        title="${a.critique_ia ? "Critique honnête générée par une IA (Claude Haiku) : ce qui pourrait clocher, au-delà du score." : "Critique IA : pas encore générée pour ce bien."}">${IC.esprit} Critique IA</button>
      ${a.dossier ? `<a class="btn-outil" href="${ech(a.dossier)}" download
        title="Classeur Excel pré-rempli à présenter au banquier : plan de financement, cash-flow, ratios (DSCR, LTV), tableau d'amortissement — toutes les hypothèses restent modifiables.">${IC.banque} Dossier banque</a>` : ""}
      <select class="suivi-select${suivi[a.id] ? " actif" : ""}" data-suivi="${ech(a.id)}"
        title="Où en êtes-vous sur cette annonce ? Le statut la fait apparaître dans l'onglet « Mon suivi » (mémorisé sur cet appareil).">
        <option value="">Suivi…</option>
        ${SUIVI_STATUTS.map(([v, l]) =>
          `<option value="${v}"${(suivi[a.id] || {}).statut === v ? " selected" : ""}>${l}</option>`).join("")}
      </select>
      </details>
    </div>
  </article>`;
}

function ligneCompacteHtml(a) {
  const cls = classeScore(a.score);
  const fonds = {vert: "var(--vert-fond)", orange: "var(--orange-fond)", gris: "var(--gris-fond)"}[cls];
  const encres = {vert: "var(--vert-texte)", orange: "var(--orange-texte)", gris: "var(--gris-texte)"}[cls];
  // Ligne compacte dépliable : la carte complète (mêmes infos qu'« à étudier »)
  // n'est construite qu'à l'ouverture, la page reste légère.
  return `<details class="ligne-depliable" data-id="${ech(a.id)}">
    <summary><div class="ligne-compacte">
      <span class="chevron">▸</span>
      <span class="mini-score" style="background:${fonds};color:${encres}">${a.score ?? "—"}</span>
      <span class="t">${ech(a.titre)}</span>
      <span class="d">${ech(a.ville)} · ${fmtEuros(a.prix)} · rdt ${fmtPct(a.rendement_brut_pct)}${a.peut_etre_retiree ? ` · <span style="color:var(--alerte-texte)">${disponibiliteTexte(a)}</span>` : ""}</span>
    </div></summary>
    <div class="corps-depliable"></div>
  </details>`;
}

const ENCHERE_MAXIMA = {emplacement: 30, gabarit: 20, depart: 15, dossier: 15,
                        proximite: 10, preparation: 10};
const ENCHERE_LIBELLES = {emplacement: "Emplacement", gabarit: "Gabarit vs budget",
  depart: "Départ sous plafond", dossier: "Dossier lisible",
  proximite: "Trajet domicile", preparation: "Préparation"};

function explicationsEnchere(e) {
  const jours = e.date_vente
    ? Math.max(0, Math.ceil((new Date(e.date_vente) - Date.now()) / 86400000)) : null;
  return {
    emplacement: "Où est le local ? Même logique que les annonces classiques : une bonne rue garde ses commerçants. Paris = 30 pts, communes qui montent = 24, petite couronne = 18, centre-ville de grande couronne = 12, ailleurs = 6.",
    gabarit: "Ce que le bien VAUT vraiment (pas la mise à prix, qui est toujours basse) rentre-t-il dans votre budget de 420 000 € ? Oui = 20 pts. S'il vaut beaucoup plus, des enchérisseurs plus riches vous le prendront — ce n'est pas votre combat.",
    depart: "L'écart entre le prix de départ et VOTRE limite (le plafond de raison). Grand écart = 15 pts : vous pouvez suivre les enchères longtemps tout en restant gagnant. Petit écart = la moindre surenchère vous éjecte.",
    dossier: "Ce qu'on sait du bien avant d'y aller : surface connue (+6), estimation officielle du commissaire (+5), ville précisée (+4). Moins on en sait, plus on achète à l'aveugle.",
    proximite: "Le temps de trajet estimé depuis chez vous, rue Francoeur (18e) : moins de 20 min = 10 pts, 20-40 = 6, 40-60 = 3.",
    preparation: (e.date_vente
      ? `La vente a lieu le ${new Date(e.date_vente).toLocaleDateString("fr-FR")}${jours != null ? ` (dans ${jours} jour${jours > 1 ? "s" : ""})` : ""}. `
      : "Date de vente inconnue. ")
      + "Il faut le temps de trouver un avocat, visiter le local et voir votre banque : 10 jours ou plus = 10 pts, 5 à 9 jours = 5, moins = 2 (c'est ce qui explique une note basse ici : le calendrier est trop court, pas le bien).",
  };
}

function pourquoiEnchereHtml(e) {
  const d = e.detail_score || {};
  const exp = explicationsEnchere(e);
  const lignes = Object.entries(ENCHERE_MAXIMA).map(([cle, max]) => {
    const v = d[cle] ?? 0;
    return `<div class="jauge"><span>${ENCHERE_LIBELLES[cle]}
        <span class="info-i" data-exp="${ech(exp[cle] || "")}">i</span></span>
      <div class="piste"><div data-l="${Math.max(0, Math.min(100, v / max * 100))}"></div></div>
      <span class="val">${v}/${max}</span></div>`;
  });
  return `<div class="pourquoi"><div class="titre-bloc">Pourquoi ce score enchère</div>${lignes.join("")}</div>`;
}

function jaugeEnchereHtml(e) {
  if (!e.prix_m2_mise_a_prix || !e.marche_prix_m2_bas) return "";
  const bas = e.marche_prix_m2_bas, haut = e.marche_prix_m2_haut;
  const med = (bas + haut) / 2, v = e.prix_m2_mise_a_prix;
  const min = Math.min(bas, v) * 0.85, max = Math.max(haut, v) * 1.1;
  const pos = x => Math.max(0, Math.min(100, (x - min) / (max - min) * 100));
  return `<div class="marche">
    <div><span class="marche-legende-bien">●</span> mise à prix : <b>${fmtEuros(v)}/m²</b> — le marché vaut ${fmtEuros(bas)} à ${fmtEuros(haut)}/m²</div>
    <div class="marche-piste">
      <div class="ligne"></div>
      <div class="bande-marche" style="left:${pos(bas)}%;width:${pos(haut) - pos(bas)}%"></div>
      <div class="mediane" style="left:${pos(med)}%" title="médiane locale ${fmtEuros(med)}/m²"></div>
      <div class="bien" style="left:calc(${pos(v)}% - 7px)" title="mise à prix : ${fmtEuros(v)}/m²"></div>
    </div>
    <div class="marche-echelle"><span>${fmtEuros(bas)}/m²</span><span>médiane ${fmtEuros(med)}</span><span>${fmtEuros(haut)}/m²</span></div>
    ${e.prix_max_conseille ? `<div class="lecture">Valeur de marché du bien ≈ ${fmtEuros(e.valeur_marche_basse)} – ${fmtEuros(e.valeur_marche_haute)}.
      Votre plafond d'enchère = <b>${fmtEuros(e.prix_max_conseille)}</b> (le bas de cette fourchette) —
      le prix final dépend de la salle : fixez votre limite avant d'y aller, et tenez-la.</div>` : ""}
  </div>`;
}

function enchereHtml(e, index) {
  const dateVente = e.date_vente
    ? new Date(e.date_vente).toLocaleDateString("fr-FR", {day: "numeric", month: "long"})
    : "date à confirmer";
  const img = e.image_url
    ? `<img src="${ech(e.image_url)}" alt="" loading="lazy" referrerpolicy="no-referrer"
         onerror="this.parentElement.innerHTML=IC.boutique">`
    : IC.boutique;
  const forte = e.haut_panier;
  const sticker = forte
    ? `<span class="sticker sticker-marteau" title="Occasion : bien dans le gabarit, départ loin sous le plafond">${IC.marteau}</span>` : "";
  const badges = [
    `<span class="badge badge-type">${IC.marteau} Enchère · ${ech(e.type_vente)}</span>`,
    `<span class="badge badge-nouveau">${IC.horloge} vente le ${dateVente}</span>`,
  ];
  if (e.rue_categorie === "peu_commercante")
    badges.push(`<span class="badge badge-alerte">${IC.alerte} rue peu commerçante${fiabiliteRueHtml(e)}</span>`);
  else if (e.rue_categorie === "tres_commercante")
    badges.push(`<span class="badge badge-rue-plus">${IC.loupe} rue commerçante mesurée${fiabiliteRueHtml(e)}</span>`);
  if (e.rue_nb_vacants != null && e.rue_nb_vacants >= 3)
    badges.push(`<span class="badge badge-alerte">${IC.alerte} vacance commerciale proche${fiabiliteVacanceHtml(e)}</span>`);
  if (metroHtml(e)) badges.push(metroHtml(e));
  const badgesHtml = badges.join("");
  const metriques = [
    ["Mise à prix", fmtEuros(e.mise_a_prix)],
    ["Surface", e.surface_m2 ? e.surface_m2 + " m²" : "—"],
    ["Mise à prix/m²", e.prix_m2_mise_a_prix ? fmtEuros(e.prix_m2_mise_a_prix) : "—"],
    ["Plafond d'enchère", e.prix_max_conseille ? fmtEuros(e.prix_max_conseille) : "—"],
    ["Estimation", e.estimation_basse ? `${fmtEuros(e.estimation_basse)}–${fmtEuros(e.estimation_haute)}` : "—"],
  ].map(([l, v]) =>
    `<div class="metrique"><div class="libelle">${l}</div><div class="valeur">${v}</div></div>`).join("");
  return `<article class="carte${forte ? " prio podium-1" : ""}" style="animation-delay:${index * 45}ms">
    ${boutonMasquerHtml(e.id)}
    ${sticker}
    <div class="carte-img">${img}</div>
    <div>
      ${forte ? '<div><span class="tampon">Occasion à la barre</span></div>' : ""}
      <div class="carte-titre"><a href="${ech(e.url)}" target="_blank" rel="noopener">${ech(e.titre)}</a>
        <span class="badges">${badgesHtml}</span></div>
      <div class="carte-lieu">${ech(e.ville || "")}${e.ville ? " · " : ""}département ${ech(e.departement)}${e.criteres ? " · " + ech(e.criteres) : ""}</div>
      <div class="metriques">${metriques}</div>
      ${jaugeEnchereHtml(e)}
    </div>
    ${pourquoiEnchereHtml(e)}
    <div class="carte-score">
      <div class="score or">${e.score_enchere ?? "—"}</div>
      <div class="score-libelle">enchère /100</div>
    </div>
  </article>`;
}

function filtres() {
  return {
    texte: document.getElementById("f-texte").value,
    signal: document.getElementById("f-signal").value,
    surface: document.getElementById("f-surface").value,
    pepites: document.getElementById("f-pepites").checked,
    trajet: document.getElementById("f-trajet").value,
    tri: document.getElementById("f-tri").value,
    archives: document.getElementById("f-archives").checked,
    type: document.getElementById("f-type").value,
    dep: [...document.querySelectorAll("#f-dep-liste input:checked")].map(c => c.value),
    rdt: document.getElementById("f-rdt").value,
    score: document.getElementById("f-score").value,
    nouv: document.getElementById("f-nouv").checked,
    cf: document.getElementById("f-cf").checked,
  };
}

function estPepite(a) {
  return a.pepite === true && !a.peut_etre_retiree && !a.decision?.diagnostic?.bloquant;
}

function contactPrioritaire(a) {
  // Même signal pour l'ouverture de la fiche et le conseil de contact.
  // Une simulation de négociation ne suffit pas ; une démarche déjà engagée
  // n'a plus besoin d'une invitation au premier contact.
  const statut = (suivi[a.id] || {}).statut;
  return estPepite(a) && estOpportunitePrioritaire(a) && a.est_nouvelle === true && !estAbandonnee(a.id)
    && (!statut || statut === "suivie")
    && !(a.flags || []).includes("rendement_anormalement_eleve");
}

function estPotentiel(a) {
  return a.negociation?.selection === true && (a.negociation.cashflow_cible ?? 0)
      >= (a.negociation.objectif_cashflow ?? D.analyse.negociation?.cashflow_cible_mensuel ?? 100)
    && (a.decision?.relocation || a.negociation.relocation)?.niveau !== "vigilance"
    && !a.peut_etre_retiree && !a.decision?.diagnostic?.bloquant;
}

function estOpportunitePrioritaire(a) {
  if (a.decision?.relocation?.niveau === "vigilance") return false;
  const objectif = a.negociation?.objectif_cashflow ?? D.analyse.negociation?.cashflow_cible_mensuel ?? 100;
  if (estPepite(a)) return (cashflowMensuel(a) ?? 0) >= objectif;
  return estPotentiel(a) && (cashflowAuPrix(a, a.negociation.prix_plafond) ?? 0) >= objectif;
}

function ecartsPreferences(a, f) {
  const ecarts = [];
  if (f.surface && !(a.surface_m2 > 0 && a.surface_m2 < Number(f.surface)))
    ecarts.push(`${a.surface_m2 == null ? "surface inconnue" : new Intl.NumberFormat("fr-FR").format(a.surface_m2) + " m²"} (souhait : < ${f.surface} m²)`);
  if (f.trajet && !(a.temps_trajet_min != null && a.temps_trajet_min <= Number(f.trajet)))
    ecarts.push(`${a.temps_trajet_min == null ? "trajet inconnu" : "≈ " + a.temps_trajet_min + " min"} (souhait : ${f.trajet} min max)`);
  return ecarts;
}

function appliquer(a, f) {
  const texte = (f.texte || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const contenu = `${a.titre} ${a.ville} ${a.code_postal} ${a.rue_voie || ""} ${a.id}`.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  if (texte && !contenu.includes(texte)) return false;
  if (f.signal === "baisses") {
    const h = a.historique_prix || [];
    if (h.length < 2 || h[h.length-1].prix >= h[0].prix) return false;
  }
  if (f.signal === "completer" && (a.decision?.documentation ?? 0) >= 80) return false;
  if (f.signal === "coherent" && a.decision?.diagnostic?.bloquant) return false;
  if (f.signal === "prudent" && !(a.decision?.cashflow_prudent != null && a.decision.cashflow_prudent >= 0)) return false;
  if (f.signal === "negociation" && !estPotentiel(a)) return false;
  if (!f.archives && a.peut_etre_retiree) return false;
  const exception = f.pepites && (estPepite(a) || estPotentiel(a)) && !estAbandonnee(a.id);
  if (!exception && ecartsPreferences(a, f).length) return false;
  if (f.type !== "tous" && a.type_murs !== f.type) return false;
  // secteurs cochés : union — le bien passe s'il est dans L'UN d'eux
  if (f.dep.length && !f.dep.some(v =>
      v === "18e" ? a.code_postal === "75018" : a.departement === v)) return false;
  if (f.rdt !== "" && (a.rendement_brut_pct == null || a.rendement_brut_pct < parseFloat(f.rdt))) return false;
  if (f.score !== "" && (a.score == null || a.score < parseFloat(f.score))) return false;
  if (f.nouv && !a.est_nouvelle) return false;
  // Cash-flow : filtré à VOTRE profil, pas au financement de référence du
  // score — c'est le seul chiffre qui décrit ce que le bien coûte VOUS.
  if (f.cf) { const c = cashflowMensuel(a); if (c == null || c < 0) return false; }
  return true;
}

function majResumeSecteurs(f) {
  const libelles = f.dep.map(v => v === "18e" ? "Paris 18e" : v);
  document.getElementById("f-dep-resume").textContent =
    !libelles.length ? "Tous" : libelles.length <= 2 ? libelles.join(" + ")
    : `${libelles.length} secteurs`;
}

function rendre() {
  const f = filtres();
  localStorage.setItem(CLE_FILTRES, JSON.stringify(f));
  majResumeSecteurs(f);
  const visibles = D.retenues.filter(a => appliquer(a, f));
  const tris = {
    recherche: (a, b) => (b.score ?? -1) - (a.score ?? -1)
      || (b.recherche?.score || 0) - (a.recherche?.score || 0),
    score: (a, b) => (b.score || 0) - (a.score || 0),
    prix: (a, b) => (a.prix ?? Infinity) - (b.prix ?? Infinity),
    trajet: (a, b) => (a.temps_trajet_min ?? Infinity) - (b.temps_trajet_min ?? Infinity),
    recent: (a, b) => b.date_derniere_vue.localeCompare(a.date_derniere_vue),
  };
  visibles.sort(tris[f.tri] || tris.recherche);
  const resume = [];
  if (f.surface) resume.push(`< ${f.surface} m²`);
  if (f.trajet) resume.push(`${f.trajet} min max`);
  if (f.pepites && (f.surface || f.trajet)) resume.push("+ pépites et potentiels");
  document.getElementById("resume-filtres").textContent = resume.join(" · ");
  // Une annonce écartée à la main OU plus revue en ligne depuis longtemps
  // (probablement vendue/retirée) descend dans le reste du tableau de chasse.
  const relegue = a => estAbandonnee(a.id) || a.peut_etre_retiree;
  const incoherente = a => !!a.decision?.diagnostic?.bloquant;
  const verifier = visibles.filter(a => incoherente(a) && !relegue(a));
  // Une opportunité négociée peut remonter, avec prix, score simulé et
  // cash-flow affichés. L'objectif doit aussi fonctionner au profil personnel.
  const prioritaire = a => f.tri === "recherche" && estOpportunitePrioritaire(a) && !relegue(a) && !incoherente(a);
  const prio = visibles.filter(prioritaire);
  const etudier = visibles.filter(a =>
    ((a.score ?? 0) >= D.seuils.affichage || estPotentiel(a)) && !prioritaire(a) && !relegue(a) && !incoherente(a));
  const reste = visibles.filter(a => ((a.score ?? 0) < D.seuils.affichage && !incoherente(a) && !estPotentiel(a)) || relegue(a));

  const podium = [...prio, ...etudier].slice(0, 3).map(a => a.id);
  const opts = a => ({
    prio: prioritaire(a),
    medaille: podium.indexOf(a.id) >= 0 ? podium.indexOf(a.id) : null,
    exceptions: f.pepites && (estPepite(a) || estPotentiel(a)) ? ecartsPreferences(a, f) : [],
  });

  let index = 0;
  // Les enchères ont leur propre score d'intérêt : elles sont présentées
  // après le classement des annonces classiques, sous un intitulé distinct.
  const occasions = (D.encheres || []).filter(e => e.haut_panier && !estAbandonnee(e.id)
    && (!f.surface || (e.surface_m2 > 0 && e.surface_m2 < Number(f.surface)))
    && (!f.trajet || (e.temps_trajet_min != null && e.temps_trajet_min <= Number(f.trajet))));
  const titreSelection = f.signal === "negociation" ? "Potentiels à négocier" : "Les meilleures annonces";
  document.getElementById("bloc-prio").innerHTML =
    prio.length
      ? `<h2 class="section">${titreSelection}</h2>` +
        prio.map(a => carteHtml(a, {...opts(a), index: index++})).join("")
      : "";

  document.getElementById("bloc-etudier").innerHTML =
    `<h2 class="section">${prio.length ? "À étudier aussi" : titreSelection}</h2>` +
    (etudier.length ? etudier.map(a => carteHtml(a, {...opts(a), index: index++})).join("")
      : '<div class="note-vide">Rien dans cette tranche avec ces filtres.</div>') +
    (occasions.length ? '<h2 class="section">Occasions aux enchères <span class="nb">score d’intérêt distinct</span></h2>' +
      occasions.map((e, i) => enchereHtml(e, index + i)).join("") : "");

  const bloc = document.getElementById("bloc-reste");
  bloc.querySelector("summary").textContent =
    `Le reste du tableau de chasse (${reste.length}) — score sous ${D.seuils.affichage}`;
  document.getElementById("reste-liste").innerHTML = reste.map(ligneCompacteHtml).join("");
  document.getElementById("bloc-verifier").style.display = verifier.length ? "" : "none";
  document.querySelector("#bloc-verifier > summary").textContent = `${verifier.length} dossier(s) à confirmer : nature de la vente ou chiffres — hors recommandations`;
  document.getElementById("verifier-liste").innerHTML = verifier.map(ligneCompacteHtml).join("");

  document.getElementById("compteur").textContent =
    `${visibles.length} / ${D.retenues.length} annonces`;

  requestAnimationFrame(() => {
    document.querySelectorAll(".piste div[data-l]").forEach(el => { el.style.width = el.dataset.l + "%"; });
  });
  majPlateau();
  rendreEncheres();
}

function rendreEncheres() {
  const s = D.stats;
  const pannes = Object.entries(D.sante).filter(([,x]) => x.statut !== "ok");
  const partielles = Object.entries(D.sante).filter(([,x]) => x.statut === "ok" &&
    (x.annonces === 0 || (x.avertissements || []).some(t => !t.startsWith("budget de redirection :"))));
  const heuresDepuisCollecte = (Date.now() - new Date(D.derniere_execution).getTime()) / 3600000;
  document.getElementById("qualite-veille-resume").textContent =
    `Tournée complète : ${new Date(D.derniere_execution).toLocaleString("fr-FR", {timeZone:"Europe/Paris"})} · ` +
    `${pannes.length} source(s) en échec, ${partielles.length} à contrôler` +
    (heuresDepuisCollecte > 24 ? " · données de plus de 24 h" : "");
  document.getElementById("qualite-veille-detail").innerHTML =
    `<p>La collecte peut être partielle. Une annonce non revue n’est pas nécessairement vendue.
    La date de génération du site ne remplace pas la date de collecte.</p>` +
    [...pannes, ...partielles].map(([nom,x]) => `<p><b>${ech(nom)}</b> : ${ech(x.message || (x.avertissements || []).join(" ; ") || "Aucune annonce collectée ; absence d’offre ou source à vérifier.")}</p>`).join("");
  if (D.collecte_ciblee) {
    const c = D.collecte_ciblee, d = c.details || {};
    document.getElementById("qualite-veille-resume").textContent += ` · passe ciblée ${new Date(c.date).toLocaleDateString("fr-FR", {timeZone:"Europe/Paris"})} ${new Date(c.date).toLocaleTimeString("fr-FR", {timeZone:"Europe/Paris",hour:"2-digit",minute:"2-digit"})}`;
    document.getElementById("qualite-veille-detail").innerHTML +=
      `<p><b>Passe ciblée complémentaire : ${fmtDate(c.date)}</b> · ${c.nouvelles} nouvelle(s) fiche(s).</p>` +
      Object.entries(c.sources || {}).map(([nom,x]) => `<p>${ech(nom)} : ${x.statut === "ok" ? x.annonces + " annonces collectées (couverture partielle)" : ech(x.message)}</p>`).join("") +
      `<p>${d.refusees || 0} accès refusés pendant cette passe. Les résultats ont ensuite fait l’objet d’un contrôle de qualité.</p>`;
  }
  if (D.qualite_donnees) {
    const q = D.qualite_donnees;
    document.getElementById("qualite-veille-detail").innerHTML +=
      `<p><b>Qualité du stock :</b> ${q.fiches_tracees} fiches complètes identifiées et tracées ; ${q.listes_ecartees} redirections vers des listes écartées.</p>` +
      (q.nettoyage ? `<p>Nettoyage historique : ${q.nettoyage.fiches_nettoyees} fiches corrigées, ${q.nettoyage.loyers_retires_ou_corriges} loyers retirés ou rectifiés. Les annonces sources restent des déclarations, pas des pièces vérifiées.</p>` : "");
  }
  // Les meilleures occasions sont en haut de page ; le reste est REPLIÉ par
  // défaut (pas du top = pas d'espace), mêmes cartes une fois ouvert. Une
  // occasion masquée manuellement (croix) redescend ici comme les autres.
  const encheres = (D.encheres || []).filter(e => !e.haut_panier || estAbandonnee(e.id));
  const nbFortes = (D.encheres || []).filter(e => e.haut_panier && !estAbandonnee(e.id)).length;
  const blocEncheres = document.getElementById("bloc-encheres");
  if ((D.encheres || []).length || s.encheres_ecartees) {
    blocEncheres.style.display = "";
    blocEncheres.querySelector("summary").textContent =
      `Sous le marteau — ${encheres.length} autre${encheres.length > 1 ? "s" : ""} vente${encheres.length > 1 ? "s" : ""} aux enchères en IdF` +
      (nbFortes ? ` (${nbFortes} occasion${nbFortes > 1 ? "s" : ""} déjà en haut de page)` : "") +
      (s.encheres_ecartees ? ` · ${s.encheres_ecartees} écartée${s.encheres_ecartees > 1 ? "s" : ""} : mise à prix déjà au-dessus du plafond de raison` : "");
    document.getElementById("encheres-liste").innerHTML =
      encheres.map((e, i) => enchereHtml(e, i)).join("") +
      `<div class="note-encheres">Score enchère = intérêt du dossier, PAS une promesse de marge :
       emplacement /30 + gabarit vs budget /20 + départ sous plafond /15 + dossier lisible /15
       + trajet /10 + préparation /10. Le prix d'adjudication est imprévisible (1× à 6× la mise à
       prix selon la salle) — nous ne le prédisons pas ; votre limite = le plafond d'enchère affiché.
       Une mise à prix déjà au-dessus de ce plafond est écartée d'office.
       Enchérir en salle exige un avocat et une consignation (~10 %).</div>`;
  } else {
    blocEncheres.style.display = "none";
  }
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
      return `<span class="${top ? "meilleur" : ""}">${b.score} /100</span>`;
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
    ["Trajet domicile", b => b.temps_trajet_min == null ? "—" : `≈ ${b.temps_trajet_min} min`],
    ["Type", b => b.type_murs === "murs_occupes" ? "Murs occupés" : "Murs libres"],
    ["Atouts", b => (b.caracteristiques || []).join(" · ") || "—"],
    ["", b => `<button type="button" class="btn-comp" data-id="${ech(b.id)}">Retirer</button>`],
  ];
  document.getElementById("comp-table").innerHTML = "<table>" + lignes.map(([titre, fn]) =>
    `<tr><th>${titre}</th>${biens.map(b => `<td>${fn(b)}</td>`).join("")}</tr>`).join("") + "</table>";
  document.getElementById("comparateur-fond").style.display = "block";
}

/* ---- Simulateur de financement ---- */
function mensualite(capital, tauxPct, ans) {
  const t = tauxPct / 100 / 12, n = ans * 12;
  return t ? capital * t / (1 - Math.pow(1 + t, -n)) : capital / n;
}

// Le simulateur s'ouvre sur EXACTEMENT le même calcul que la métrique
// cash-flow de la carte : le PROFIL de l'utilisateur (apport, taux, durée).
let simId = null;
let simEtat = {prix: 0, apport: profil.apport, apportMode: profil.apportMode,
               apportEuros: profil.apportEuros, taux: profil.taux, duree: profil.duree};

function ouvrirSimulateur(id, prix = null) {
  const a = D.retenues.find(x => x.id === id);
  if (!a || a.prix == null) return;
  simId = id;
  const e = exploitation(a);
  simEtat = {prix: prix ?? a.prix, apport: profil.apport,
             apportMode: profil.apportMode, apportEuros: profil.apportEuros,
             taux: profil.taux, duree: profil.duree, loyer:e.loyer,
             taxe:e.taxe, taxeEstimee:e.taxeEstimee, vacance:e.vacance, charges:e.charges};
  rendreSimulateur();
  document.getElementById("outil-fond").style.display = "block";
}

function rendreSimulateur() {
  const a = D.retenues.find(x => x.id === simId);
  const e = exploitation(a, simEtat), loyer = e.loyer;
  const hypothesesOuvertes = document.getElementById("sim-hypotheses")?.open;
  const cout = simEtat.prix * 1.08 + (a.honoraires || 0);
  const apportEuros = simEtat.apportMode === "euros"
    ? Math.max(0, Math.min(simEtat.apportEuros, cout))
    : cout * simEtat.apport / 100;
  const emprunt = Math.max(0, cout - apportEuros);
  const m = emprunt > 0 ? mensualite(emprunt, simEtat.taux, simEtat.duree) : 0;
  const cf = e.revenu == null ? null : Math.round(e.revenu - m);
  const stress = e.stress == null ? null : Math.round(e.stress - m);
  const interets = Math.round(m * simEtat.duree * 12 - emprunt);
  const coc = (loyer != null && apportEuros > 0)
    ? ((e.revenu - m) * 12 / apportEuros * 100) : null;

  // Grille de scénarios : le triangle apport × durée
  const apports = [10, 20, 30], durees = [15, 20, 25];
  let meilleurCf = -Infinity;
  const cellules = durees.map(d => apports.map(ap => {
    const e2 = cout * (1 - ap / 100);
    const cf2 = e.revenu == null ? null : Math.round(e.revenu - mensualite(e2, simEtat.taux, d));
    if (cf2 != null && cf2 > meilleurCf) meilleurCf = cf2;
    return cf2;
  }));
  const grille = loyer == null ? "" : `
    <p style="margin:14px 0 4px;font-weight:600">Trésorerie prudente selon apport et durée
      <span style="color:var(--encre-3);font-weight:400">(taux ${simEtat.taux} %)</span></p>
    <table class="sim-grille"><tr><th></th>${apports.map(ap => `<th>apport ${ap} %</th>`).join("")}</tr>
    ${durees.map((d, i) => `<tr><th>${d} ans</th>${cellules[i].map(v =>
      `<td class="${v === meilleurCf ? "top" : ""}">${v >= 0 ? "+" : "−"}${fmtEuros(Math.abs(v))}</td>`).join("")}</tr>`).join("")}
    </table>
    <p style="font-size:13px;color:var(--encre-2);margin-top:8px">La règle du jeu :
    plus d'apport ou plus de durée améliore le cash-flow, mais plus d'apport dilue le rendement
    de vos fonds propres et plus de durée gonfle les intérêts versés. Le meilleur choix dépend
    de votre objectif — retraite = privilégier un cash-flow positif sans épuiser l'épargne.</p>`;

  document.getElementById("outil-contenu").innerHTML = `
    <h3>${IC.calc} Financer — ${ech(a.titre)}</h3>
    <div class="sim-champs">
      <label>Prix négocié (€)<input type="number" step="any" min="1" value="${simEtat.prix}" data-sim-champ="prix"></label>
      ${simEtat.apportMode === "euros"
        ? `<label>Apport (€) — 0 = crédit 100 %<input type="number" step="any" min="0" value="${simEtat.apportEuros}" data-sim-champ="apportEuros"></label>`
        : `<label>Apport (%) — 0 = crédit 100 %<input type="number" step="any" min="0" max="100" value="${simEtat.apport}" data-sim-champ="apport"></label>`}
      <label>Taux (%)<input type="number" step="any" min="0" max="20" value="${simEtat.taux}" data-sim-champ="taux"></label>
      <label>Durée (ans)<input type="number" step="1" min="5" max="27" value="${simEtat.duree}" data-sim-champ="duree"></label>
    </div>
    <details id="sim-hypotheses"${hypothesesOuvertes ? " open" : ""}>
      <summary>Ajuster les revenus et charges</summary>
      <div class="sim-champs">
        <label>Loyer mensuel HT/HC (€)<input type="number" step="any" min="0" value="${simEtat.loyer ?? ""}" data-sim-champ="loyer"></label>
        <label>Taxe foncière annuelle (€)<input type="number" step="any" min="0" value="${simEtat.taxe ?? ""}" data-sim-champ="taxe"></label>
        <label>Vacance (% du loyer)<input type="number" step="any" min="0" max="99" value="${simEtat.vacance}" data-sim-champ="vacance"></label>
        <label>Charges à votre charge (%)<input type="number" step="any" min="0" max="99" value="${simEtat.charges}" data-sim-champ="charges"></label>
      </div>
      <small>Charges : provision pour entretien, gestion et charges non récupérables, hors taxe foncière. Vos essais modifient cette simulation uniquement ; les données et le score de l’annonce restent identiques.</small>
    </details>
    <p class="offre-note">${loyer == null ? "Revenu manquant : renseignez-le pour calculer. " : a.loyer_estime ? "Revenu estimé, à confirmer par une mise en location. " : "Loyer déclaré, à justifier par le bail et les quittances. "}${e.taxe == null ? "Taxe foncière à renseigner." : e.taxeEstimee ? "Taxe inconnue : provision de " + fmtEuros(e.taxe) + "/an, remplaçable ci-dessus." : "Taxe retenue : " + fmtEuros(e.taxe) + "/an."}</p>
    ${a.decision?.diagnostic?.bloquant ? '<p class="alerte-donnee fort">Simulation exploratoire : résolvez les alertes sur les données avant de retenir ce résultat.</p>' : ""}
    <div class="sim-bilan">
      <div class="metrique"><div class="libelle">Chaque mois · prudent</div><div class="valeur" style="color:${cf >= 0 ? "var(--vert-texte)" : "var(--alerte-texte)"}">${cf == null ? "—" : (cf >= 0 ? "+" : "−") + fmtEuros(Math.abs(cf))}</div></div>
      <div class="metrique"><div class="libelle">Scénario dégradé · par mois</div><div class="valeur">${stress == null ? "—" : (stress >= 0 ? "+" : "−") + fmtEuros(Math.abs(stress))}</div></div>
    </div>
    <details><summary>Coût, apport et crédit · ${fmtEuros(Math.round(m))}/mois de mensualité</summary>
    <div class="sim-resultats">
      <div class="metrique"><div class="libelle">Coût acte en main</div><div class="valeur">${fmtEuros(Math.round(cout))}</div></div>
      <div class="metrique"><div class="libelle">Apport</div><div class="valeur">${fmtEuros(apportEuros)}</div></div>
      <div class="metrique"><div class="libelle">Emprunt</div><div class="valeur">${fmtEuros(Math.round(emprunt))}</div></div>
      <div class="metrique"><div class="libelle">Mensualité</div><div class="valeur">${fmtEuros(Math.round(m))}</div></div>
      <div class="metrique"><div class="libelle">Rdt des fonds propres</div><div class="valeur">${coc == null ? "—" : fmtPct(coc)}</div></div>
      <div class="metrique"><div class="libelle">Intérêts totaux</div><div class="valeur">${fmtEuros(interets)}</div></div>
    </div></details>
    ${grille}
    <p style="font-size:12px;color:var(--encre-3);margin-top:10px">Calcul : coût acte en main = prix × 1,08
    (hypothèse de frais), plus honoraires séparés renseignés ; trésorerie = loyer − crédit − vacance (${e.vacance} %) − charges (${e.charges} %) − taxe (${fmtEuros(e.taxe)}/an).
    Scénario dégradé : loyer −10 %, au moins deux mois de vacance par an, mêmes charges en pourcentage et même taxe.
    Avant impôt, assurance emprunteur et travaux exceptionnels.
    Le taux par défaut est une moyenne de marché à ajuster avec votre banque — aucune donnée
    bancaire en direct ici, par honnêteté.</p>`;
}

/* ---- Checklist par annonce (persistée) ---- */
const CHECKLIST = [
  {g: "Le bail", items: [
    {id: "bail_date", t: "Bail 3/6/9 lu : date, échéance triennale, loyer à jour",
      auto: a => (a.bonus_detectes || []).includes("echeance_bail_proche") ? "⚠ échéance proche signalée dans l'annonce"
        : (a.bonus_detectes || []).includes("bail_longue_duree_restante") ? "bail loin de toute échéance signalé"
        : (a.bonus_detectes || []).includes("bail_recent") ? "bail récent signalé" : null},
    {id: "bail_606", t: "Répartition légale des grosses réparations et refacturation de la taxe foncière vérifiées",
      auto: a => (a.bonus_detectes || []).includes("taxe_fonciere_locataire") ? "signalé dans l'annonce" : null},
    {id: "bail_destination", t: "Destination du bail large (« tous commerces » idéalement)",
      auto: a => (a.caracteristiques || []).includes("Toutes activités") ? "« toutes activités » signalé" : null},
    {id: "bail_depot", t: "Dépôt de garantie et garanties personnelles vérifiés"},
  ]},
  {g: "Le locataire", items: [
    {id: "loc_place", t: "Un locataire est en place et paie",
      auto: a => a.type_murs === "murs_occupes" ? "murs vendus occupés" : null},
    {id: "loc_kbis", t: "Kbis + 3 derniers bilans obtenus et lus"},
    {id: "loc_ratio", t: "Loyer ≤ 10 % du chiffre d'affaires du locataire"},
    {id: "loc_quittances", t: "12 mois de quittances sans incident"},
  ]},
  {g: "L'immeuble et le local", items: [
    {id: "imm_ag", t: "3 derniers PV d'AG lus (ravalement, toiture votés ?)"},
    {id: "imm_visite", t: "Local visité (sols, vitrine, électricité, humidité)"},
    {id: "imm_travaux", t: "Pas de gros travaux à prévoir", negatif: true,
      auto: a => (a.bonus_detectes || []).includes("travaux") ? "travaux signalés dans l'annonce" : null},
  ]},
  {g: "La rue et les chiffres", items: [
    {id: "rue_flux", t: "Flux vérifié sur place (mardi 15 h ET samedi 11 h)"},
    {id: "rue_rideaux", t: "Moins de 2 rideaux baissés sur 10 dans la rue"},
    {id: "chiffre_aem", t: "Rendement acte en main recalculé soi-même",
      auto: a => a.rendement_acte_en_main_pct != null ? `calculé ici : ${fmtPct(a.rendement_acte_en_main_pct)}` : null},
    {id: "nego_ecrit", t: "Offre écrite, conditionnée au prêt et à la lecture du bail"},
  ]},
];

function etatChecklists() {
  try { return JSON.parse(localStorage.getItem("veille-checklists") || "{}"); }
  catch (e) { return {}; }
}

function nbChecklist(a) {
  const coches = new Set(etatChecklists()[a.id] || []);
  let total = 0, faits = 0;
  for (const groupe of CHECKLIST) for (const item of groupe.items) {
    total++;
    const auto = item.auto && item.auto(a);
    if (coches.has(item.id) || (auto && !item.negatif)) faits++;
  }
  return `${faits}/${total}`;
}

let chkId = null;
function ouvrirChecklist(id) {
  chkId = id;
  rendreChecklist();
  document.getElementById("outil-fond").style.display = "block";
}

function rendreChecklist() {
  const a = D.retenues.find(x => x.id === chkId);
  if (!a) return;
  const coches = new Set(etatChecklists()[chkId] || []);
  const groupes = CHECKLIST.map(groupe => `<div class="check-groupe"><h4>${groupe.g}</h4>` +
    groupe.items.map(item => {
      const auto = item.auto && item.auto(a);
      const cochee = coches.has(item.id) || (auto && !item.negatif);
      const badge = auto
        ? `<span class="auto${item.negatif ? " negatif" : ""}">${item.negatif ? "⚠ " : "✓ "}${ech(auto)}</span>` : "";
      return `<label class="check-item"><input type="checkbox" data-chk-item="${item.id}"
        ${cochee ? "checked" : ""}> <span>${item.t}</span> ${badge}</label>`;
    }).join("") + "</div>").join("");
  document.getElementById("outil-contenu").innerHTML = `
    <h3>${IC.coche} Checklist — ${ech(a.titre)}</h3>
    <p style="font-size:13px;color:var(--encre-2)">Les points « ✓ signalé » viennent du texte de
    l'annonce (à confirmer sur pièces) ; cochez le reste au fil de vos vérifications — c'est
    enregistré sur cet appareil.</p>
    ${groupes}`;
}

document.addEventListener("change", ev => {
  const champ = ev.target.closest("[data-sim-champ]");
  if (champ) {
    // `|| ancienneValeur` serait un piège ici : 0 est falsy, or « 0 » est une
    // saisie LÉGITIME et explicitement proposée (« 0 = crédit 100 % ») — elle
    // revenait silencieusement à l'ancienne valeur. Seul un champ vide ou
    // illisible (NaN) doit être ignoré.
    champ.setCustomValidity("");
    const v = champ.valueAsNumber, cle = champ.dataset.simChamp;
    if (!Number.isFinite(v) || !champ.reportValidity()) return;
    if ((cle === "vacance" && v + simEtat.charges >= 100) ||
        (cle === "charges" && v + simEtat.vacance >= 100)) {
      champ.setCustomValidity("La vacance et les charges doivent totaliser moins de 100 % du loyer.");
      champ.reportValidity(); return;
    }
    simEtat[cle] = v;
    if (cle === "taxe") simEtat.taxeEstimee = false;
    rendreSimulateur();
    return;
  }
  const caseChk = ev.target.closest("[data-chk-item]");
  if (caseChk && chkId) {
    const tout = etatChecklists();
    const liste = new Set(tout[chkId] || []);
    caseChk.checked ? liste.add(caseChk.dataset.chkItem) : liste.delete(caseChk.dataset.chkItem);
    tout[chkId] = [...liste];
    localStorage.setItem("veille-checklists", JSON.stringify(tout));
  }
});

// Suivi : changement de statut depuis n'importe quelle carte, notes dans l'onglet
document.addEventListener("change", ev => {
  const sel = ev.target.closest?.("[data-suivi]");
  if (sel) majSuivi(sel.dataset.suivi, sel.value);
});
document.addEventListener("input", ev => {
  const note = ev.target.closest?.("[data-note]");
  if (!note) return;
  const s = suivi[note.dataset.note];
  if (!s) return;
  s.note = note.value;
  localStorage.setItem(CLE_SUIVI, JSON.stringify(suivi));
});

// Dépliage d'une ligne compacte : on construit la carte complète à la volée
document.addEventListener("toggle", ev => {
  const bloc = ev.target.closest?.("details.ligne-depliable");
  if (!bloc || !bloc.open) return;
  const corps = bloc.querySelector(".corps-depliable");
  if (corps.childElementCount) return;
  const a = D.retenues.find(x => x.id === bloc.dataset.id);
  if (!a) return;
  corps.innerHTML = carteHtml(a, {prio: false, medaille: null, index: 0});
  requestAnimationFrame(() => {
    corps.querySelectorAll(".piste div[data-l]").forEach(el => { el.style.width = el.dataset.l + "%"; });
  });
}, true);

function defilerCarrousel(boite, direction) {
  const a = D.retenues.find(x => x.id === boite.dataset.id);
  const photos = (a && a.images && a.images.length > 1) ? a.images : null;
  if (!photos) return;
  const i = ((parseInt(boite.dataset.idx || "0", 10) + direction)
    % photos.length + photos.length) % photos.length;
  boite.dataset.idx = i;
  const image = boite.querySelector("img");
  if (image) image.src = photos[i];
  const compteur = boite.querySelector(".car-compteur");
  if (compteur) compteur.textContent = `${i + 1}/${photos.length}`;
}

// Balayage du doigt (et de la souris) sur la photo pour faire défiler
let glisseX = null, glisseBoite = null;
document.addEventListener("touchstart", ev => {
  const boite = ev.target.closest(".carte-img");
  if (boite && boite.dataset.id) { glisseX = ev.touches[0].clientX; glisseBoite = boite; }
}, {passive: true});
document.addEventListener("touchend", ev => {
  if (glisseBoite && glisseX != null) {
    const dx = ev.changedTouches[0].clientX - glisseX;
    if (Math.abs(dx) > 35) defilerCarrousel(glisseBoite, dx < 0 ? 1 : -1);
  }
  glisseX = glisseBoite = null;
}, {passive: true});
document.addEventListener("mousedown", ev => {
  const boite = ev.target.closest(".carte-img");
  if (boite && boite.dataset.id && !ev.target.closest(".car-btn")) {
    glisseX = ev.clientX; glisseBoite = boite;
  }
});
document.addEventListener("mouseup", ev => {
  if (glisseBoite && glisseX != null) {
    const dx = ev.clientX - glisseX;
    if (Math.abs(dx) > 35) defilerCarrousel(glisseBoite, dx < 0 ? 1 : -1);
  }
  glisseX = glisseBoite = null;
});

document.addEventListener("click", ev => {
  const modeContact = ev.target.closest("[data-contact-mode]");
  if (modeContact) {
    const a = D.retenues.find(x => x.id === modeContact.dataset.contactId);
    if (!a) return;
    const champ = document.getElementById("contact-texte");
    const mode = modeContact.dataset.contactMode;
    champ.value = texteContact(a, mode);
    champ.dataset.mode = mode;
    const dossier = brouillonsContact[a.id] ||= {textes:{}};
    dossier.mode = mode;
    enregistrerBrouillons();
    document.querySelectorAll("[data-contact-mode]").forEach(b => {
      b.classList.toggle("actif", b === modeContact);
      b.setAttribute("aria-pressed", String(b === modeContact));
    });
    return;
  }
  if (ev.target.closest("#contact-modele")) {
    const champ = document.getElementById("contact-texte");
    const a = D.retenues.find(x => x.id === champ.dataset.contactId), mode = champ.dataset.mode;
    if (!a) return;
    if (brouillonsContact[a.id]?.textes) delete brouillonsContact[a.id].textes[mode];
    champ.value = texteContact(a, mode);
    const ok = enregistrerBrouillons();
    document.getElementById("contact-brouillon").textContent = ok ? "Modèle rétabli pour cette étape." : "Modèle rétabli en mémoire ; le stockage local est indisponible.";
    return;
  }
  // Carrousel photo
  const car = ev.target.closest(".car-btn");
  if (car) {
    defilerCarrousel(car.closest(".carte-img"), parseInt(car.dataset.car, 10));
    return;
  }
  // Encart d'explication d'un critère de score
  const inf = ev.target.closest(".info-i[data-exp]");
  if (inf) {
    const jauge = inf.closest(".jauge");
    const suivant = jauge.nextElementSibling;
    if (suivant && suivant.classList.contains("exp-ligne")) suivant.remove();
    else jauge.insertAdjacentHTML("afterend", `<div class="exp-ligne">${inf.dataset.exp}</div>`);
    return;
  }
  const masquer = ev.target.closest("[data-masquer]");
  if (masquer) { basculerMasquage(masquer.dataset.masquer); return; }
  const btn = ev.target.closest(".btn-comp");
  if (btn) {
    basculerComparaison(btn.dataset.id);
    if (document.getElementById("comparateur-fond").style.display === "block") ouvrirComparateur();
    return;
  }
  const sim = ev.target.closest("[data-sim]");
  if (sim) { ouvrirSimulateur(sim.dataset.sim, sim.dataset.simPrix == null ? null : Number(sim.dataset.simPrix)); return; }
  const chk = ev.target.closest("[data-check]");
  if (chk) { ouvrirChecklist(chk.dataset.check); return; }
  const contact = ev.target.closest("[data-contact]");
  if (contact) { ouvrirContact(contact.dataset.contact); return; }
  const offre = ev.target.closest("[data-offre]");
  if (offre) { ouvrirProposition(offre.dataset.offre); return; }
  const critique = ev.target.closest("[data-critique]");
  if (critique) { ouvrirCritique(critique.dataset.critique); return; }
  if (ev.target.closest("#contact-copier")) {
    const champ = document.getElementById("contact-texte");
    const confirmer = () => {
      const ok = document.getElementById("contact-copie-ok");
      if (ok) { ok.style.display = "inline"; setTimeout(() => { ok.style.display = "none"; }, 2500); }
    };
    const repli = () => { champ.select(); document.execCommand("copy"); confirmer(); };
    if (navigator.clipboard && navigator.clipboard.writeText)
      navigator.clipboard.writeText(champ.value).then(confirmer).catch(repli);
    else repli();
    return;
  }
  if (ev.target.id === "comp-ouvrir") ouvrirComparateur();
  if (ev.target.id === "comp-vider") { comparaison = []; localStorage.setItem(CLE_COMP, "[]"); rendre(); }
  if (ev.target.id === "comp-fermer" || ev.target.id === "comparateur-fond")
    document.getElementById("comparateur-fond").style.display = "none";
  if (ev.target.id === "outil-fermer" || ev.target.id === "outil-fond") {
    document.getElementById("outil-fond").style.display = "none";
    rendre();  // rafraîchit les compteurs de checklist sur les cartes
  }
});
document.addEventListener("input", ev => {
  if (ev.target.id !== "contact-texte") return;
  const champ = ev.target, id = champ.dataset.contactId, mode = champ.dataset.mode;
  if (!id || !mode) return;
  const dossier = brouillonsContact[id] ||= {textes:{}};
  dossier.textes[mode] = champ.value;
  dossier.mode = mode;
  const ok = enregistrerBrouillons();
  document.getElementById("contact-brouillon").textContent = ok
    ? "Brouillon enregistré sur cet appareil." : "Brouillon conservé en mémoire ; le stockage local est indisponible.";
});

/* ---- Onglet « Le marché » : le paysage derrière les annonces ----
   Graphiques SVG maison (page autonome oblige), petit-multiple par indicateur
   (une unité = un axe, jamais de double axe), crosshair + infobulle, périodes
   partagées, et vue tableau par graphique (canal de secours du contraste). */
const CLE_ONGLET = "veille-murs-onglet";
let periodeMarche = "2015";
const GRAPHS_MARCHE = [];  // reconstruits à chaque changement de période

function xDecimal(p) {
  const [a, r] = p.split("-");
  return r[0] === "Q" ? +a + ((+r.slice(1)) * 3 - 1.5) / 12 : +a + (+r - 0.5) / 12;
}
const MOIS_COURTS = ["janv.", "févr.", "mars", "avr.", "mai", "juin",
                     "juil.", "août", "sept.", "oct.", "nov.", "déc."];
function fmtPeriode(p) {
  const [a, r] = p.split("-");
  return r[0] === "Q" ? `T${r.slice(1)} ${a}` : `${MOIS_COURTS[+r - 1]} ${a}`;
}
function fmtValeurMarche(v, unite) {
  if (unite.startsWith("%")) return v.toLocaleString("fr-FR", {minimumFractionDigits: 2, maximumFractionDigits: 2}) + " %";
  if (unite.startsWith("indice")) return v.toLocaleString("fr-FR", {maximumFractionDigits: 1});
  return Math.round(v).toLocaleString("fr-FR");
}

function variationAnnuelle(points, unite) {
  // dernier point vs celui d'il y a ~1 an (12 pas mensuels ou 4 trimestriels)
  if (points.length < 5) return null;
  const pas = points[points.length - 1][0].includes("Q") ? 4 : 12;
  if (points.length <= pas) return null;
  const [na, va] = points[points.length - 1 - pas], [nb, vb] = points[points.length - 1];
  if (unite.startsWith("%"))  // un taux se compare en points, pas en pourcentage de lui-même
    return {texte: `${vb >= va ? "+" : "−"}${Math.abs(vb - va).toLocaleString("fr-FR", {maximumFractionDigits: 2})} pt sur 1 an`, hausse: vb >= va};
  const pct = (vb / va - 1) * 100;
  return {texte: `${pct >= 0 ? "+" : "−"}${Math.abs(pct).toLocaleString("fr-FR", {maximumFractionDigits: 1})} % sur 1 an`, hausse: pct >= 0};
}

function pasJoli(brut) {
  const p = Math.pow(10, Math.floor(Math.log10(brut)));
  const m = brut / p;
  return (m >= 5 ? 10 : m >= 2 ? 5 : m >= 1 ? 2 : 1) * p;
}

function graphLigne(carte, definition) {
  // definition : {series: [{nom, css, points}], unite}
  const limite = periodeMarche === "2015" ? 0
    : Math.max(...definition.series.flatMap(s => s.points.map(p => xDecimal(p[0])))) - (+periodeMarche);
  const series = definition.series
    .map(s => ({...s, pts: s.points.filter(p => xDecimal(p[0]) >= limite)}))
    .filter(s => s.pts.length >= 2);
  const zone = carte.querySelector(".zone-graph");
  if (!series.length) { zone.innerHTML = "<p class='lecture'>Pas assez de points sur cette période.</p>"; return; }

  const L = 640, H = 240, g = 54, d = 10, h = 10, b = 24;
  const xs = series.flatMap(s => s.pts.map(p => xDecimal(p[0])));
  const ys = series.flatMap(s => s.pts.map(p => p[1]));
  const x0 = Math.min(...xs), x1 = Math.max(...xs);
  let y0 = Math.min(...ys), y1 = Math.max(...ys);
  if (y1 - y0 < 1e-9) { y0 -= 1; y1 += 1; }
  const pas = pasJoli((y1 - y0) / 4);
  y0 = Math.floor(y0 / pas) * pas; y1 = Math.ceil(y1 / pas) * pas;
  const X = v => g + (v - x0) / (x1 - x0) * (L - g - d);
  const Y = v => h + (1 - (v - y0) / (y1 - y0)) * (H - h - b);

  let svg = "";
  for (let t = y0; t <= y1 + 1e-9; t += pas) {
    svg += `<line x1="${g}" y1="${Y(t)}" x2="${L - d}" y2="${Y(t)}" style="stroke:var(--filet)" stroke-width="1"/>` +
      `<text x="${g - 6}" y="${Y(t) + 3.5}" text-anchor="end" style="fill:var(--encre-3);font:10.5px system-ui" >${fmtValeurMarche(t, definition.unite)}</text>`;
  }
  const pasAnnees = (x1 - x0) > 6 ? 2 : 1;
  for (let an = Math.ceil(x0); an <= x1; an += pasAnnees) {
    svg += `<text x="${X(an)}" y="${H - 7}" text-anchor="middle" style="fill:var(--encre-3);font:10.5px system-ui">${an}</text>`;
  }
  const etiquetesY = [];  // étiquettes de fin déjà posées : jamais empilées
  for (const s of series) {
    const chemin = s.pts.map((p, i) => `${i ? "L" : "M"}${X(xDecimal(p[0])).toFixed(1)} ${Y(p[1]).toFixed(1)}`).join(" ");
    const fin = s.pts[s.pts.length - 1];
    svg += `<path d="${chemin}" fill="none" style="stroke:var(${s.css})" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>` +
      `<circle cx="${X(xDecimal(fin[0]))}" cy="${Y(fin[1])}" r="4" style="fill:var(${s.css});stroke:var(--surface)" stroke-width="2"/>`;
    // Étiquette directe de fin (texte en encre, jamais couleur de série) —
    // seulement si elle ne chevauche pas une étiquette déjà posée : quand les
    // lignes convergent, la légende + l'infobulle prennent le relais.
    const yEtiquette = Y(fin[1]) - 8;
    if (series.length > 1 && !etiquetesY.some(y => Math.abs(y - yEtiquette) < 15)) {
      svg += `<text x="${X(xDecimal(fin[0])) - 8}" y="${yEtiquette}" text-anchor="end" style="fill:var(--encre-2);font:600 10.5px system-ui">${ech(s.nom)}</text>`;
      etiquetesY.push(yEtiquette);
    }
  }
  svg += `<line class="croix" x1="-9" y1="${h}" x2="-9" y2="${H - b}" style="stroke:var(--encre-3)" stroke-width="1" opacity="0"/>`;
  zone.innerHTML = `<svg viewBox="0 0 ${L} ${H}" tabindex="0" role="img" aria-label="${ech(definition.aria || "")}">${svg}</svg>`;

  // Couche d'interaction : le crosshair trouve la période la plus proche,
  // l'infobulle liste TOUTES les séries à cette période.
  const el = zone.querySelector("svg");
  const croix = el.querySelector(".croix");
  const ref = series[0].pts;
  let idx = ref.length - 1;
  const montrer = (evt) => {
    const boite = el.getBoundingClientRect();
    if (evt && evt.clientX != null) {
      const xr = (evt.clientX - boite.left) / boite.width * L;
      let meilleur = 0, ecart = 1e9;
      ref.forEach((p, i) => {
        const e = Math.abs(X(xDecimal(p[0])) - xr);
        if (e < ecart) { ecart = e; meilleur = i; }
      });
      idx = meilleur;
    }
    const p = ref[idx];
    croix.setAttribute("x1", X(xDecimal(p[0]))); croix.setAttribute("x2", X(xDecimal(p[0])));
    croix.setAttribute("opacity", ".55");
    const tip = infobulleMarche();
    tip.innerHTML = "";
    const quand = document.createElement("div"); quand.className = "qt";
    quand.textContent = fmtPeriode(p[0]); tip.appendChild(quand);
    for (const s of series) {
      const pt = s.pts[Math.min(idx, s.pts.length - 1)];
      const ligne = document.createElement("div"); ligne.className = "vl";
      const cle = document.createElement("span"); cle.className = "cle";
      cle.style.borderTop = `2.5px solid var(${s.css})`; cle.style.width = "14px";
      const val = document.createElement("b"); val.textContent = fmtValeurMarche(pt[1], definition.unite);
      const nom = document.createElement("span"); nom.textContent = series.length > 1 ? s.nom : definition.unite;
      ligne.append(cle, val, nom); tip.appendChild(ligne);
    }
    tip.style.display = "block";
    const px = evt && evt.clientX != null ? evt.clientX : boite.left + X(xDecimal(p[0])) / L * boite.width;
    const py = evt && evt.clientY != null ? evt.clientY : boite.top + 30;
    tip.style.left = Math.min(px + 14, window.innerWidth - tip.offsetWidth - 8) + "px";
    tip.style.top = (py + 14) + "px";
  };
  const cacher = () => { croix.setAttribute("opacity", "0"); infobulleMarche().style.display = "none"; };
  el.addEventListener("pointermove", montrer);
  el.addEventListener("pointerleave", cacher);
  el.addEventListener("focus", () => montrer(null));
  el.addEventListener("blur", cacher);
  el.addEventListener("keydown", (e) => {
    if (e.key === "ArrowLeft") { idx = Math.max(0, idx - 1); montrer(null); e.preventDefault(); }
    if (e.key === "ArrowRight") { idx = Math.min(ref.length - 1, idx + 1); montrer(null); e.preventDefault(); }
  });
}

let _infobulleMarche = null;
function infobulleMarche() {
  if (!_infobulleMarche) {
    _infobulleMarche = document.createElement("div");
    _infobulleMarche.className = "graph-tooltip";
    document.body.appendChild(_infobulleMarche);
  }
  return _infobulleMarche;
}

function definitionsMarche() {
  const S = D.marche.series;
  const defs = [];
  const simple = (cle, titre) => {
    const s = S[cle];
    if (s && s.points.length) defs.push({
      id: cle, titre: titre || s.libelle, lecture: s.lecture, unite: s.unite,
      sources: [{texte: s.source, url: s.url}],
      series: [{nom: s.libelle, css: "--g1", points: s.points}],
    });
  };
  simple("ilc");
  simple("logements_idf");
  simple("oat");
  simple("climat_commerce");
  simple("cout_construction");
  const dTous = S.defaillances_idf, dCom = S.defaillances_commerce_idf, dResto = S.defaillances_resto_idf;
  const dSeries = [
    dTous && dTous.points.length && {nom: "Tous secteurs", css: "--g1", points: dTous.points},
    dCom && dCom.points.length && {nom: "Commerce", css: "--g2", points: dCom.points},
    dResto && dResto.points.length && {nom: "Hébergement-restauration", css: "--g3", points: dResto.points},
  ].filter(Boolean);
  if (dSeries.length) defs.push({
    id: "defaillances", titre: "Défaillances d'entreprises en Île-de-France",
    lecture: "Jugements d'ouverture (redressements, liquidations…) cumulés sur 12 mois glissants. " +
      "La santé réelle des locataires du secteur : plus elle se dégrade, plus le risque d'impayé et de vacance monte.",
    unite: "défaillances, cumul 12 mois",
    sources: [dTous, dCom, dResto].filter(Boolean).map(s => ({texte: s.source, url: s.url})),
    series: dSeries,
  });
  return defs;
}

function construireMarche() {
  const grille = document.getElementById("marche-grille");
  if (grille.childElementCount) return;  // déjà construit
  document.getElementById("marche-intro").textContent =
    "Le paysage derrière les annonces : loyers commerciaux, cycle immobilier francilien, taux et " +
    "défaillances d'entreprises. Données actualisées le " +
    new Date(D.marche.maj).toLocaleDateString("fr-FR", {day: "numeric", month: "long", year: "numeric"}) + ".";
  const periodes = document.getElementById("marche-periodes");
  periodes.innerHTML = "";
  for (const [val, libelle] of [["2015", "Depuis 2015"], ["5", "5 ans"], ["2", "2 ans"]]) {
    const btn = document.createElement("button");
    btn.type = "button"; btn.textContent = libelle; btn.dataset.periode = val;
    if (val === periodeMarche) btn.className = "actif";
    btn.addEventListener("click", () => {
      periodeMarche = val;
      periodes.querySelectorAll("button").forEach(x => x.classList.toggle("actif", x === btn));
      GRAPHS_MARCHE.forEach(([carte, definition]) => graphLigne(carte, definition));
    });
    periodes.appendChild(btn);
  }
  for (const definition of definitionsMarche()) {
    const carte = document.createElement("article");
    carte.className = "carte-graph";
    const variation = variationAnnuelle(definition.series[0].points, definition.unite);
    const legende = definition.series.length > 1
      ? `<div class="graph-legende">${definition.series.map(s =>
          `<span><span class="cle" style="border-top-color:var(${s.css})"></span>${ech(s.nom)}</span>`).join("")}</div>`
      : "";
    carte.innerHTML = `
      <h3>${ech(definition.titre)}${variation ? `<span class="delta-an ${variation.hausse ? "hausse" : "baisse"}">${variation.texte}</span>` : ""}</h3>
      <p class="lecture">${ech(definition.lecture || "")}</p>
      ${legende}
      <div class="zone-graph"></div>
      <details class="voir-valeurs"><summary>Voir les valeurs ▸</summary><div class="table-valeurs"></div></details>
      <div class="source-graph">${definition.sources.map(s =>
        `<a href="${ech(s.url)}" target="_blank" rel="noopener">${ech(s.texte)} ↗</a>`).join(" · ")}</div>`;
    grille.appendChild(carte);
    definition.aria = `${definition.titre} — graphique en lignes, valeurs détaillées dans le tableau ci-dessous`;
    graphLigne(carte, definition);
    GRAPHS_MARCHE.push([carte, definition]);
    // Vue tableau (toutes les valeurs restent accessibles sans survol)
    const table = carte.querySelector(".table-valeurs");
    const lignes = definition.series[0].points.map((p, i) =>
      `<tr><td>${fmtPeriode(p[0])}</td>${definition.series.map(s =>
        `<td>${s.points[i] ? fmtValeurMarche(s.points[i][1], definition.unite) : "—"}</td>`).join("")}</tr>`);
    table.innerHTML = `<table><thead><tr><th>Période</th>${definition.series.map(s =>
      `<th>${ech(definition.series.length > 1 ? s.nom : definition.unite)}</th>`).join("")}</tr></thead>` +
      `<tbody>${lignes.reverse().join("")}</tbody></table>`;
  }
}

__REPONSES_VENDEUR__

function basculerVue(vue) {
  for (const v of ["chasse", "suivi", "marche", "reponses"])
    document.getElementById("vue-" + v).style.display = v === vue ? "" : "none";
  document.querySelectorAll("#onglets .onglet").forEach(b =>
    b.classList.toggle("actif", b.dataset.vue === vue));
  localStorage.setItem(CLE_ONGLET, vue);
  if (vue === "marche") construireMarche();
  if (vue === "suivi") rendreSuivi();
  if (vue === "reponses") rendreReponses();
}

/* ---- Onglet « Mon suivi » : le carnet de chasse ----
   Statut + notes par annonce, en localStorage uniquement (rien ne quitte
   l'appareil). Un instantané (titre, lien, ville, prix) est conservé au moment
   du marquage : si l'annonce disparaît des retenues (vendue, exclue), la ligne
   survit dans le suivi au lieu de s'évaporer — on n'oublie pas une piste. */
const SUIVI_STATUTS = [
  ["suivie", "Je la suis"],
  ["contactee", "Contactée"],
  ["visite_prevue", "Visite prévue"],
  ["visitee", "Visitée"],
  ["offre_faite", "Offre faite"],
  ["abandonnee", "Abandonnée"],
];
const SUIVI_LIBELLES = Object.fromEntries(SUIVI_STATUTS);

function majCompteurSuivi() {
  const n = Object.values(suivi).filter(s => s.statut !== "abandonnee").length;
  document.getElementById("suivi-compteur").textContent = n ? `(${n})` : "";
}

function majSuivi(id, statut) {
  if (!statut) {
    delete suivi[id];
  } else {
    const a = D.retenues.find(x => x.id === id);
    const s = suivi[id] || {};
    s.statut = statut;
    s.maj = new Date().toISOString();
    if (a) s.instantane = {titre: a.titre, url: a.url, ville: a.ville, prix: a.prix};
    suivi[id] = s;
  }
  localStorage.setItem(CLE_SUIVI, JSON.stringify(suivi));
  majCompteurSuivi();
  rendre();  // le statut influe sur le classement (« abandonnée » = reléguée)
  if (document.getElementById("vue-suivi").style.display !== "none") rendreSuivi();
}

function rendreSuivi() {
  const conteneur = document.getElementById("suivi-contenu");
  const ids = Object.keys(suivi);
  if (!ids.length) {
    conteneur.innerHTML = `<div class="note-vide">Rien en suivi pour l'instant.
      Dans l'onglet « La chasse », choisissez un statut (« Je la suis », « Contactée »…)
      sur une carte : elle apparaîtra ici, avec vos notes.</div>`;
    return;
  }
  let html = "";
  for (const [statut, libelle] of SUIVI_STATUTS) {
    const lot = ids.filter(id => suivi[id].statut === statut)
      .sort((x, y) => (suivi[y].maj || "").localeCompare(suivi[x].maj || ""));
    if (!lot.length) continue;
    html += `<h2 class="section">${libelle} <span class="nb">${lot.length}</span></h2>`;
    for (const id of lot) {
      const s = suivi[id];
      const a = D.retenues.find(x => x.id === id);
      const inst = s.instantane || {};
      const alerte = a && a.peut_etre_retiree
        ? ` · <span class="suivi-alerte">${disponibiliteTexte(a)}</span>`
        : (!a && inst.titre
          ? ` · <span class="suivi-alerte">n'apparaît plus dans les annonces retenues (vendue, retirée ou exclue)</span>` : "");
      const entete = a
        ? ligneCompacteHtml(a)
        : `<div class="ligne-compacte"><span class="mini-score" style="background:var(--gris-fond);color:var(--gris-texte)">—</span>
             <span class="t"><a href="${ech(inst.url || "#")}" target="_blank" rel="noopener">${ech(inst.titre || "Annonce disparue")}</a></span>
             <span class="d">${ech(inst.ville || "")}${inst.prix ? " · " + fmtEuros(inst.prix) : ""}</span></div>`;
      html += `<div class="suivi-item">
        ${entete}
        <div class="suivi-meta">${SUIVI_LIBELLES[s.statut]} depuis le ${fmtDate(s.maj)}${alerte}</div>
        <textarea class="suivi-note" data-note="${ech(id)}" rows="2"
          placeholder="Vos notes : interlocuteur, ressenti de visite, points à vérifier… (mémorisées sur cet appareil)">${ech(s.note || "")}</textarea>
      </div>`;
    }
  }
  conteneur.innerHTML = html;
}

function initialiser() {
  // Filtres ouverts d'office sur grand écran, repliés sur mobile
  document.getElementById("volet-filtres").open = false;

  // Onglets. « Le marché » n'apparaît que si ses séries ont pu être collectées.
  const nav = document.getElementById("onglets");
  const aMarche = D.marche && D.marche.series
    && Object.values(D.marche.series).some(s => s.points.length);
  if (!aMarche) nav.querySelector('[data-vue="marche"]').style.display = "none";
  nav.querySelectorAll(".onglet").forEach(b =>
    b.addEventListener("click", () => basculerVue(b.dataset.vue)));
  majCompteurSuivi();
  const vueDemandee = location.hash === "#marche" ? "marche"
    : location.hash === "#suivi" ? "suivi" : location.hash === "#reponses" ? "reponses" : localStorage.getItem(CLE_ONGLET);
  if (vueDemandee === "marche" && aMarche) basculerVue("marche");
  else if (vueDemandee === "suivi") basculerVue("suivi");
  else if (vueDemandee === "reponses") basculerVue("reponses");

  const s = D.stats;
  // Les pépites ne sont pas un sous-ensemble des nouvelles (une pépite peut
  // avoir plusieurs jours) : deux phrases distinctes, jamais un « dont »
  // trompeur. Et une pépite annoncée doit être TROUVABLE : le lien lève les
  // filtres/masquages qui pourraient la cacher et défile jusqu'à elle.
  document.getElementById("hud").innerHTML =
    `<div class="hud-texte">Ces dernières 48 h : <b>${s.nouvelles}</b> nouvelle${s.nouvelles > 1 ? "s" : ""} annonce${s.nouvelles > 1 ? "s" : ""}.<br>` +
    `${s.pepites ? `<b>${s.pepites}</b> pépite${s.pepites > 1 ? "s" : ""} au tableau — <a href="#" id="hud-pepite">la voir →</a><br>` : ""}` +
    `<b>${s.analysees}</b> annonces passées au crible sur 7 jours.` +
    `<span class="maj">Dernière tournée : ${new Date(D.derniere_execution).toLocaleString("fr-FR", {day: "numeric", month: "long", hour: "2-digit", minute: "2-digit"})}</span></div>` +
    `<div class="hud-action"><a class="btn-veille" id="hud-veille" href="https://github.com/GeorgesD75/veille-murs-commerciaux/actions/workflows/veille.yml" target="_blank" rel="noopener noreferrer" title="Ouvre GitHub Actions pour lancer la veille à la main">▶ Lancer la veille</a></div>`;
  const lienPepite = document.getElementById("hud-pepite");
  if (lienPepite) lienPepite.addEventListener("click", ev => {
    ev.preventDefault();
    basculerVue("chasse");
    // Lève tout ce qui peut cacher la pépite : filtres actifs et masquage manuel.
    document.getElementById("f-surface").value = "";
    document.getElementById("f-trajet").value = "";
    document.getElementById("f-archives").checked = true;
    document.getElementById("f-cf").checked = false;
    document.getElementById("f-texte").value = "";
    document.getElementById("f-signal").value = "tous";
    document.getElementById("f-type").value = "tous";
    document.querySelectorAll("#f-dep-liste input:checked").forEach(c => { c.checked = false; });
    document.getElementById("f-rdt").value = "";
    document.getElementById("f-score").value = "";
    document.getElementById("f-nouv").checked = false;
    const idsPepites = D.retenues.filter(estPepite).map(a => a.id);
    masquees = masquees.filter(id => !idsPepites.includes(id));
    localStorage.setItem(CLE_MASQUEES, JSON.stringify(masquees));
    rendre();
    const carte = document.querySelector(".carte.rang-s");
    if (carte) carte.scrollIntoView({behavior: "smooth", block: "start"});
  });
  document.getElementById("pied-maj").textContent =
    new Date(D.derniere_execution).toLocaleString("fr-FR");

  // Le taux « Mon taux (%) » démarre sur le taux de MARCHÉ du jour (pas une
  // valeur figée) : OAT France (Eurostat) + marge pro, actualisé à chaque
  // tournée. Transparence sur la source, sinon le repli de config.yaml.
  document.getElementById("taux-marche-note").textContent = D.taux_marche
    ? ` Taux de départ actualisé : ${D.taux_marche.taux_pct} % (OAT France ${D.taux_marche.mois_reference} : ${D.taux_marche.oat_pct} % + marge pro ${D.taux_marche.marge_pct} pt) — pas une offre bancaire réelle, à confirmer auprès de vos établissements.`
    : " Taux de départ : valeur par défaut (le taux de marché n'a pas pu être récupéré à la dernière tournée).";

  const NOMS_DEP = {"75": "Paris", "77": "Seine-et-Marne", "78": "Yvelines",
    "91": "Essonne", "92": "Hauts-de-Seine", "93": "Seine-Saint-Denis",
    "94": "Val-de-Marne", "95": "Val-d'Oise"};
  const deps = [...new Set(D.retenues.map(a => a.departement).filter(Boolean))].sort();
  const listeDep = document.getElementById("f-dep-liste");
  for (const d of deps) listeDep.insertAdjacentHTML("beforeend",
    `<label><input type="checkbox" value="${d}"> ${NOMS_DEP[d] || d} (${d})</label>`);
  // clic hors de la liste : on referme le menu déroulant
  document.addEventListener("click", e => {
    const boite = document.getElementById("f-dep-boite");
    if (boite.open && !boite.contains(e.target)) boite.open = false;
  });

  rendreEncheres();

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
    `Barème /100 : rendement ${D.maxima.rendement} + emplacement ${D.maxima.emplacement} ` +
    `+ prix vs marché ${D.maxima.prix_m2_vs_benchmark} + financement ${D.maxima.financement} ` +
    `+ fiscalité ${D.maxima.fiscalite} + trajet ${D.maxima.proximite} + quartier 18e ${D.maxima.quartier} ` +
    `+ bonus/malus (−3 à +5, plafonné à 100). Score ≥ ${D.seuils.pepite} : pépite (email immédiat). ` +
    `Score ≥ ${D.seuils.vert} : haut du panier. Sous ${D.seuils.orange} : le reste du marché. ` +
    `Un rendement > 10 % est plafonné ` +
    `sous ${D.seuils.affichage} (piège probable) jusqu'à vérification. ` +
    `« est. » = loyer estimé ou promis, non prouvé par un bail. ` +
    `Le score enchère est un score d'intérêt distinct (voir sa note de section).`;

  try {
    const memo = JSON.parse(localStorage.getItem(CLE_FILTRES) || "{}");
    document.getElementById("f-texte").value = memo.texte || "";
    document.getElementById("f-signal").value = memo.signal || "tous";
    document.getElementById("f-surface").value = memo.surface ?? D.recherche.surface_max_m2;
    document.getElementById("f-pepites").checked = memo.pepites !== false;
    document.getElementById("f-trajet").value = memo.trajet ?? "";
    document.getElementById("f-tri").value = memo.tri || "recherche";
    document.getElementById("f-archives").checked = !!memo.archives;
    if (memo.type) document.getElementById("f-type").value = memo.type;
    // ancien format : dep était une chaîne unique ("tous" / "18e" / "93")
    const depMemo = Array.isArray(memo.dep) ? memo.dep
      : (memo.dep && memo.dep !== "tous" ? [memo.dep] : []);
    for (const case_ of listeDep.querySelectorAll("input"))
      case_.checked = depMemo.includes(case_.value);
    // `if (memo.rdt)` ignorait la valeur « 0 », falsy en JS : un filtre réglé
    // à 0 ne revenait jamais. On teste la PRÉSENCE, pas la vérité.
    if (memo.rdt != null && memo.rdt !== "") document.getElementById("f-rdt").value = memo.rdt;
    if (memo.score != null && memo.score !== "") document.getElementById("f-score").value = memo.score;
    document.getElementById("f-nouv").checked = !!memo.nouv;
    document.getElementById("f-cf").checked = !!memo.cf;
  } catch (e) { /* filtres mémorisés illisibles : on repart à zéro */ }

  for (const id of ["f-type", "f-rdt", "f-score", "f-nouv", "f-cf", "f-surface", "f-pepites", "f-trajet", "f-tri", "f-archives", "f-texte", "f-signal"])
    document.getElementById(id).addEventListener("input", rendre);
  listeDep.addEventListener("input", rendre);

  // Profil de financement : chaque changement recalcule tout le site.
  // L'apport a deux unités : le champ #p-apport pilote `apport` (%) ou
  // `apportEuros` (€) selon le mode — bornes et pas de saisie s'adaptent.
  const BORNES = {apport: [0, 90], apportEuros: [0, 100000000], taux: [0.1, 10], duree: [5, 30]};
  const champApport = document.getElementById("p-apport");
  const champApportMode = document.getElementById("p-apport-mode");
  const cleApport = () => (profil.apportMode === "euros" ? "apportEuros" : "apport");
  function rafraichirChampApport() {
    const euros = profil.apportMode === "euros";
    champApportMode.value = profil.apportMode;
    champApport.step = euros ? 1000 : 5;
    champApport.max = euros ? "" : 90;
    champApport.value = profil[cleApport()];
  }
  rafraichirChampApport();
  champApportMode.addEventListener("change", () => {
    profil.apportMode = champApportMode.value === "euros" ? "euros" : "pct";
    rafraichirChampApport();
    localStorage.setItem(CLE_PROFIL, JSON.stringify(profil));
    rendre();
  });
  champApport.addEventListener("input", () => {
    const v = parseFloat(champApport.value);
    if (isNaN(v)) return;                       // champ vidé : on garde l'ancien
    const [min, max] = BORNES[cleApport()];
    profil[cleApport()] = Math.max(min, Math.min(max, v));
    localStorage.setItem(CLE_PROFIL, JSON.stringify(profil));
    rendre();
  });
  for (const [id, cle] of [["p-taux", "taux"], ["p-duree", "duree"]]) {
    const champ = document.getElementById(id);
    champ.value = profil[cle];
    champ.addEventListener("input", () => {
      const v = parseFloat(champ.value);
      if (isNaN(v)) return;                     // champ vidé : on garde l'ancien
      const [min, max] = BORNES[cle];
      profil[cle] = Math.max(min, Math.min(max, v));
      localStorage.setItem(CLE_PROFIL, JSON.stringify(profil));
      rendre();
    });
  }
  document.getElementById("p-reset").addEventListener("click", () => {
    profil = {...PROFIL_DEFAUT};
    localStorage.removeItem(CLE_PROFIL);
    rafraichirChampApport();
    for (const [id, cle] of [["p-taux", "taux"], ["p-duree", "duree"]])
      document.getElementById(id).value = profil[cle];
    rendre();
  });

  // Profil fiscal : "non renseigné" par défaut, jamais deviné.
  document.getElementById("p-regime").value = profilFiscal.regime;
  document.getElementById("p-regime").addEventListener("change", ev => {
    profilFiscal.regime = ev.target.value;
    localStorage.setItem(CLE_FISCAL, JSON.stringify(profilFiscal));
    rendre();
  });
  document.getElementById("p-tmi").value = profilFiscal.tmi;
  document.getElementById("p-tmi").addEventListener("change", ev => {
    profilFiscal.tmi = parseInt(ev.target.value, 10);
    localStorage.setItem(CLE_FISCAL, JSON.stringify(profilFiscal));
    rendre();
  });
  document.getElementById("p-fiscal-reset").addEventListener("click", () => {
    profilFiscal = {...PROFIL_FISCAL_DEFAUT};
    localStorage.removeItem(CLE_FISCAL);
    document.getElementById("p-regime").value = profilFiscal.regime;
    document.getElementById("p-tmi").value = profilFiscal.tmi;
    rendre();
  });
  document.getElementById("f-reset").addEventListener("click", () => {
    document.getElementById("f-texte").value = "";
    document.getElementById("f-signal").value = "tous";
    localStorage.removeItem(CLE_FILTRES);
    document.getElementById("f-surface").value = "";
    document.getElementById("f-pepites").checked = true;
    document.getElementById("f-trajet").value = "";
    document.getElementById("f-tri").value = "recherche";
    document.getElementById("f-archives").checked = false;
    document.getElementById("f-cf").checked = false;
    document.getElementById("f-texte").value = "";
    document.getElementById("f-signal").value = "tous";
    document.getElementById("f-type").value = "tous";
    for (const case_ of listeDep.querySelectorAll("input")) case_.checked = false;
    document.getElementById("f-rdt").value = "";
    document.getElementById("f-score").value = "";
    document.getElementById("f-nouv").checked = false;
    rendre();
  });
  rendre();

  // Lien direct depuis un email (pépite ou récap) : #annonce=<id> lève les
  // filtres/masquages qui pourraient la cacher et défile jusqu'à la carte ;
  // #annonce=<id>&action=contactee marque aussi « Contactée » dans Mon suivi
  // en un clic — pas besoin de rouvrir le menu, l'essentiel est de gagner du
  // temps entre « pépite détectée » et « vous au téléphone avec l'agence ».
  if (location.hash.startsWith("#annonce=")) {
    const parametres = new URLSearchParams(location.hash.slice(1));
    const idCible = parametres.get("annonce");
    if (idCible) {
      document.getElementById("f-surface").value = "";
    document.getElementById("f-trajet").value = "";
    document.getElementById("f-archives").checked = true;
    document.getElementById("f-cf").checked = false;
    document.getElementById("f-texte").value = "";
    document.getElementById("f-signal").value = "tous";
    document.getElementById("f-type").value = "tous";
      document.querySelectorAll("#f-dep-liste input:checked").forEach(c => { c.checked = false; });
      document.getElementById("f-rdt").value = "";
      document.getElementById("f-score").value = "";
      document.getElementById("f-nouv").checked = false;
      const i = masquees.indexOf(idCible);
      if (i >= 0) masquees.splice(i, 1);
      localStorage.setItem(CLE_MASQUEES, JSON.stringify(masquees));
      if (parametres.get("action") === "contactee") majSuivi(idCible, "contactee");  // re-rend déjà
      else rendre();
      const cible = document.querySelector(`.carte-img[data-id="${CSS.escape(idCible)}"]`)?.closest(".carte");
      if (cible) {
        cible.scrollIntoView({behavior: "smooth", block: "center"});
        cible.classList.add("carte-ciblee");
        setTimeout(() => cible.classList.remove("carte-ciblee"), 2600);
      }
    }
  }
}
initialiser();
</script>
</body>
</html>
"""
