"""Les hypothèses manquantes ne doivent pas embellir un dossier."""
from copy import deepcopy

import pytest

from pipeline.decision import analyser_decision
from pipeline.financement import hypotheses_exploitation, mensualite_credit
from pipeline.scoring import scorer
from tests.fabriques import faire_annonce


@pytest.mark.parametrize("taxe,estimee,retenue", [
    (None, True, 1500), (0, False, 0), (2400, False, 2400),
    (-100, True, 1500), (float("nan"), True, 1500), (True, True, 1500),
])
def test_taxe_inconnue_provisionnee_sans_modifier_la_donnee(config, taxe, estimee, retenue):
    a = faire_annonce(loyer_mensuel=1500, taxe_fonciere_annuelle=taxe)
    e = hypotheses_exploitation(a, config)
    assert e["taxe_estimee"] is estimee
    assert e["taxe_annuelle_retenue"] == retenue
    assert e["revenu_prudent"] == pytest.approx(1500 * .82 - retenue / 12)
    assert a.taxe_fonciere_annuelle is taxe


def test_taxe_reelle_et_provision_identiques_donnent_les_memes_calculs(config):
    a = faire_annonce(loyer_mensuel=1700, prix=260000)
    connu = deepcopy(a)
    connu.taxe_fonciere_annuelle = a.loyer_mensuel
    avant = deepcopy(a.to_dict())
    inconnu_d = analyser_decision(a, config)
    connu_d = analyser_decision(connu, config)
    for champ in ["cashflow_prudent", "cashflow_stress", "prix_equilibre", "rendement_net_prudent"]:
        assert inconnu_d[champ] == connu_d[champ]
    assert a.to_dict() == avant
    scorer(a, config)
    scorer(connu, config)
    assert a.detail_score["financement"] == connu.detail_score["financement"]


def test_absence_de_loyer_ne_cree_pas_de_revenu_ni_de_taxe_fictive(config):
    e = hypotheses_exploitation(faire_annonce(loyer_mensuel=None), config)
    assert e["revenu_prudent"] is None and e["revenu_stress"] is None
    assert e["taxe_annuelle_retenue"] is None


def test_stress_reste_plus_defavorable_si_vacance_prudente_deja_forte(config):
    cfg = type(config)(deepcopy(config.donnees))
    cfg.donnees["recherche"]["vacance_prudente_pct"] = 40
    e = hypotheses_exploitation(faire_annonce(), cfg)
    assert e["revenu_stress"] < e["revenu_prudent"]


def test_coefficient_taux_zero_et_achat_comptant():
    assert mensualite_credit(240000, 0, 20) == 1000
    assert mensualite_credit(0, 4, 20) == 0


def test_score_financement_coherent_avec_tresorerie_de_reference(config):
    for prix in [200000, 260000, 340000]:
        a = faire_annonce(prix=prix)
        scorer(a, config)
        cf = analyser_decision(a, config)["cashflow_prudent"]
        attendu = 5 if cf >= 0 else 3 if cf >= -a.loyer_mensuel * .1 else 0
        assert a.detail_score["financement"] == attendu
