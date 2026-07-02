"""Génération du dashboard : préparation du payload et rendu HTML."""
from __future__ import annotations

from datetime import datetime

from dashboard.generer import generer_dashboard, generer_html, preparer_payload
from tests.fabriques import faire_annonce

MAINTENANT = datetime.fromisoformat("2026-07-03T08:00:00+02:00")


def _annonces_exemple():
    recente = faire_annonce(
        id="aaa", titre="Murs occupés récents",
        date_premiere_vue="2026-07-02T07:00:00+02:00",
        date_derniere_vue="2026-07-03T07:00:00+02:00",
    )
    recente.score = 85
    ancienne = faire_annonce(
        id="bbb", titre="Murs occupés anciens",
        date_premiere_vue="2026-06-01T07:00:00+02:00",
        date_derniere_vue="2026-07-03T07:00:00+02:00",
    )
    ancienne.score = 60
    exclue_fraiche = faire_annonce(
        id="ccc", titre="Fonds de commerce piège",
        date_derniere_vue="2026-07-01T07:00:00+02:00",
    )
    exclue_fraiche.exclue = True
    exclue_fraiche.raison_exclusion = "mot-clé éliminatoire « fonds de commerce »"
    exclue_vieille = faire_annonce(
        id="ddd", titre="Vieille exclue",
        date_derniere_vue="2026-06-01T07:00:00+02:00",
    )
    exclue_vieille.exclue = True
    exclue_vieille.raison_exclusion = "prix hors budget"
    return {a.id: a for a in [ancienne, recente, exclue_fraiche, exclue_vieille]}


def test_payload_trie_par_score_decroissant(config):
    payload = preparer_payload(_annonces_exemple(), {}, config, MAINTENANT)
    scores = [a["score"] for a in payload["retenues"]]
    assert scores == [85, 60]


def test_badge_nouveaute_sous_48h(config):
    payload = preparer_payload(_annonces_exemple(), {}, config, MAINTENANT)
    par_id = {a["id"]: a for a in payload["retenues"]}
    assert par_id["aaa"]["est_nouvelle"] is True
    assert par_id["bbb"]["est_nouvelle"] is False
    assert payload["stats"]["nouvelles"] == 1


def test_exclues_limitees_a_sept_jours(config):
    payload = preparer_payload(_annonces_exemple(), {}, config, MAINTENANT)
    titres = [e["titre"] for e in payload["exclues_recentes"]]
    assert titres == ["Fonds de commerce piège"]
    assert payload["exclues_recentes"][0]["raison"].startswith("mot-clé")


def test_html_autonome_et_non_reference(config):
    payload = preparer_payload(
        _annonces_exemple(),
        {"derniere_execution": "2026-07-03T07:00:00+02:00",
         "sante_sources": {"pointdevente": {"statut": "ok", "annonces": 20}}},
        config,
        MAINTENANT,
    )
    html = generer_html(payload)
    assert '<meta name="robots" content="noindex, nofollow">' in html
    assert "Murs occupés récents" in html
    assert "pointdevente" in html
    assert "</script>" in html  # gabarit intact
    # Les données embarquées ne peuvent pas fermer la balise script
    assert "fonds de commerce »</" not in html


def test_generation_fichiers(config, tmp_path):
    cible = generer_dashboard(_annonces_exemple(), {}, config, tmp_path, MAINTENANT)
    assert cible.read_text(encoding="utf-8").startswith("<!doctype html>")
    assert (tmp_path / "robots.txt").read_text(encoding="utf-8") == "User-agent: *\nDisallow: /\n"
    assert (tmp_path / ".nojekyll").exists()
