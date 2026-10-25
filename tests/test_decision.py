from copy import deepcopy
from datetime import datetime

import pytest

from pipeline.config import Config
from pipeline.decision import analyser_decision, priorite_recherche
from pipeline.comparables import LoyersComparables
from pipeline.scoring import scorer
from tests.fabriques import faire_annonce


def test_priorite_petite_surface_proche_sans_favoriser_un_grand_bien(config):
    petit = faire_annonce(surface_m2=30, temps_trajet_min=15, score=60)
    grand = faire_annonce(surface_m2=100, temps_trajet_min=50, score=90)
    assert priorite_recherche(petit, config)["score"] > priorite_recherche(grand, config)["score"]
    assert petit.score == 60  # l'adéquation n'altère pas la qualité économique


@pytest.mark.parametrize("surface,attendu", [(39.9, True), (40, False), (None, False), (0, False)])
def test_surface_strictement_sous_quarante(config, surface, attendu):
    assert priorite_recherche(faire_annonce(surface_m2=surface), config)["petite_surface"] == attendu


def test_scenario_prudent_et_prix_equilibre_coherents(config):
    a = faire_annonce(loyer_mensuel=1500, taxe_fonciere_annuelle=1200)
    d = analyser_decision(a, config)
    assert d["cashflow_prudent"] < 1500
    assert d["prix_equilibre"] > 0
    a.prix = d["prix_equilibre"]
    assert abs(analyser_decision(a, config)["cashflow_prudent"]) <= 1
    assert d["documentation"] < 100


def test_sans_loyer_pas_de_rentabilite_inventee(config):
    d = analyser_decision(faire_annonce(loyer_mensuel=None), config)
    assert d["cashflow_prudent"] is None and d["prix_equilibre"] is None
    assert any("Bail signé" in q for q in d["questions"])


def test_taux_zero_et_taxe_fonciere_dans_score_financement(config):
    cfg = Config(deepcopy(config.donnees))
    cfg.donnees["analyse"]["financement"]["taux_pct"] = 0
    sans_taxe = faire_annonce(loyer_mensuel=2500)
    taxe = faire_annonce(loyer_mensuel=2500, taxe_fonciere_annuelle=30000)
    scorer(sans_taxe, cfg)
    scorer(taxe, cfg)
    assert sans_taxe.detail_score["financement"] == 5
    assert taxe.detail_score["financement"] == 0
    assert analyser_decision(sans_taxe, cfg)["prix_equilibre"] > 0


def test_comparables_excluent_anciens_estimes_et_surfaces_incomparables():
    now = datetime.fromisoformat("2026-10-25T12:00:00+01:00")
    commun = dict(date_derniere_vue=now.isoformat(), surface_m2=30)
    annonces = [faire_annonce(id="a", **commun), faire_annonce(id="b", **commun),
                faire_annonce(id="estime", loyer_estime=True, **commun),
                faire_annonce(id="ancien", date_derniere_vue="2026-01-01T12:00:00+01:00"),
                faire_annonce(id="grand", surface_m2=500, date_derniere_vue=now.isoformat())]
    c = LoyersComparables.depuis(annonces, maintenant=now)
    assert c.pour("93500", 30)[1] == 2
    assert c.pour("93500", 500) is None
