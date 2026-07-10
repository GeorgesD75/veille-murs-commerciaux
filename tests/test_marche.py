"""Contexte de marché : garde-fou mensuel, parsing SDMX, panne sans perte."""
from __future__ import annotations

import json

import pytest

from pipeline import marche
from pipeline.marche import _cle_periode, actualiser_marche

XML_INSEE = """<message>
<Series IDBANK="001532540" FREQ="T" TITLE_FR="ILC">
<Obs TIME_PERIOD="2015-Q2" OBS_VALUE="108.38" OBS_STATUS="A"/>
<Obs TIME_PERIOD="2015-Q1" OBS_VALUE="108.32" OBS_STATUS="A"/>
<Obs TIME_PERIOD="2015-Q3" OBS_VALUE="." OBS_STATUS="M"/>
</Series>
<Series IDBANK="010567079" FREQ="T" TITLE_FR="Logements IdF">
<Obs TIME_PERIOD="2015-Q1" OBS_VALUE="100.0" OBS_STATUS="A"/>
</Series>
</message>"""

JSON_EUROSTAT = {
    "value": {"0": 0.67, "1": 0.60},
    "dimension": {"time": {"category": {"index": {"2015-01": 0, "2015-02": 1}}}},
}


class ReponseFactice:
    def __init__(self, texte="", payload=None):
        self.text = texte
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _get_factice(monkeypatch, insee_ok=True, eurostat_ok=True):
    appels = []

    def get(url, params=None, headers=None, timeout=None):
        appels.append(url)
        if "insee" in url:
            if not insee_ok:
                raise RuntimeError("INSEE en panne")
            return ReponseFactice(texte=XML_INSEE)
        if not eurostat_ok:
            raise RuntimeError("Eurostat en panne")
        return ReponseFactice(payload=JSON_EUROSTAT)

    monkeypatch.setattr(marche.requests, "get", get)
    return appels


def test_cle_periode_trie_chronologiquement():
    # (les formats mois/trimestre ne se mélangent jamais au sein d'une série)
    assert sorted(["2016-Q1", "2015-Q4", "2015-Q1"], key=_cle_periode) == \
        ["2015-Q1", "2015-Q4", "2016-Q1"]
    assert sorted(["2015-12", "2015-01", "2015-02"], key=_cle_periode) == \
        ["2015-01", "2015-02", "2015-12"]


def test_collecte_parse_trie_et_ignore_les_valeurs_manquantes(tmp_path, monkeypatch):
    _get_factice(monkeypatch)
    contenu = actualiser_marche(tmp_path / "marche.json")
    ilc = contenu["series"]["ilc"]
    # tri chronologique malgré l'ordre inverse de l'API, valeur « . » ignorée
    assert ilc["points"] == [["2015-Q1", 108.32], ["2015-Q2", 108.38]]
    assert "insee.fr" in ilc["url"]
    assert contenu["series"]["oat"]["points"] == [["2015-01", 0.67], ["2015-02", 0.6]]
    assert (tmp_path / "marche.json").exists()


def test_fichier_frais_ne_reinterroge_pas_les_api(tmp_path, monkeypatch):
    appels = _get_factice(monkeypatch)
    chemin = tmp_path / "marche.json"
    actualiser_marche(chemin)
    nb_premiere = len(appels)
    resultat = actualiser_marche(chemin)  # < 27 jours : lecture seule
    assert len(appels) == nb_premiere
    assert resultat["series"]["ilc"]["points"]


def test_fichier_perime_est_recollecte(tmp_path, monkeypatch):
    appels = _get_factice(monkeypatch)
    chemin = tmp_path / "marche.json"
    perime = {"maj": "2026-01-01T00:00:00+01:00", "series": {}}
    chemin.write_text(json.dumps(perime), encoding="utf-8")
    actualiser_marche(chemin)
    assert appels  # les API ont bien été réinterrogées


def test_panne_api_conserve_les_points_precedents(tmp_path, monkeypatch):
    chemin = tmp_path / "marche.json"
    ancien = {
        "maj": "2026-01-01T00:00:00+01:00",
        "series": {
            "ilc": {"points": [["2015-Q1", 108.32]]},
            "oat": {"points": [["2015-01", 0.67]]},
        },
    }
    chemin.write_text(json.dumps(ancien), encoding="utf-8")
    _get_factice(monkeypatch, insee_ok=False, eurostat_ok=False)
    contenu = actualiser_marche(chemin)
    # panne totale : l'historique précédent est conservé, jamais écrasé par du vide
    assert contenu["series"]["ilc"]["points"] == [["2015-Q1", 108.32]]
    assert contenu["series"]["oat"]["points"] == [["2015-01", 0.67]]


def test_panne_totale_sans_fichier_rend_none(tmp_path, monkeypatch):
    _get_factice(monkeypatch, insee_ok=False, eurostat_ok=False)
    assert actualiser_marche(tmp_path / "marche.json") is None
    assert not (tmp_path / "marche.json").exists()


@pytest.mark.parametrize("periode,attendu", [("2015-Q1", (2015, 3)), ("2026-11", (2026, 11))])
def test_cle_periode_formats(periode, attendu):
    assert _cle_periode(periode) == attendu
