"""Taux de marché (Eurostat OAT France) : jamais bloquant, jamais figé."""
from __future__ import annotations

import requests

from pipeline.taux_marche import taux_credit_estime, taux_obligataire_france


class FakeReponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


_PAYLOAD_EUROSTAT = {
    "value": {"0": 3.74},
    "dimension": {"time": {"category": {"index": {"2026-05": 0}}}},
}


class TestTauxObligataireFrance:
    def test_lecture_reussie(self, monkeypatch):
        monkeypatch.setattr(
            "pipeline.taux_marche.requests.get",
            lambda *a, **k: FakeReponse(_PAYLOAD_EUROSTAT),
        )
        assert taux_obligataire_france() == (3.74, "2026-05")

    def test_panne_reseau_renvoie_none(self, monkeypatch):
        def leve(*a, **k):
            raise requests.ConnectionError("indisponible")
        monkeypatch.setattr("pipeline.taux_marche.requests.get", leve)
        assert taux_obligataire_france() is None

    def test_reponse_mal_formee_renvoie_none(self, monkeypatch):
        monkeypatch.setattr(
            "pipeline.taux_marche.requests.get",
            lambda *a, **k: FakeReponse({"inattendu": True}),
        )
        assert taux_obligataire_france() is None

    def test_erreur_http_renvoie_none(self, monkeypatch):
        monkeypatch.setattr(
            "pipeline.taux_marche.requests.get",
            lambda *a, **k: FakeReponse({}, status=503),
        )
        assert taux_obligataire_france() is None


class TestTauxCreditEstime:
    def test_ajoute_la_marge(self, monkeypatch):
        monkeypatch.setattr(
            "pipeline.taux_marche.requests.get",
            lambda *a, **k: FakeReponse(_PAYLOAD_EUROSTAT),
        )
        resultat = taux_credit_estime(marge_pct=0.9)
        assert resultat == {
            "taux_pct": 4.64, "oat_pct": 3.74, "marge_pct": 0.9, "mois_reference": "2026-05",
        }

    def test_panne_renvoie_none(self, monkeypatch):
        monkeypatch.setattr(
            "pipeline.taux_marche.requests.get",
            lambda *a, **k: (_ for _ in ()).throw(requests.Timeout()),
        )
        assert taux_credit_estime(marge_pct=0.9) is None
