"""Un bon prix ne prouve pas que le local sera simple à relouer."""
from copy import deepcopy

import pytest

from pipeline.contact import messages_contact
from pipeline.decision import analyser_decision, analyser_relocation, est_pepite
from pipeline.financement import hypotheses_exploitation
from pipeline.notifications import notifier
from tests.fabriques import faire_annonce


@pytest.mark.parametrize("valeurs,niveau", [
    ({"ville": "Paris", "code_postal": "75018"}, "a_verifier"),
    ({"rue_distance_metro_m": 50}, "a_verifier"),
    ({"emplacement_numero": "1"}, "a_verifier"),
    ({"rue_categorie": "commercante", "rue_nb_vacants": 0}, "favorable"),
    ({"rue_categorie": "tres_commercante", "rue_nb_vacants": 3}, "vigilance"),
    ({"rue_categorie": "peu_commercante"}, "vigilance"),
    ({"emplacement_numero": "3"}, "vigilance"),
    ({"bonus_detectes": ["echeance_bail_proche"]}, "vigilance"),
])
def test_diagnostic_local_sans_deduire_la_demande_de_la_commune(valeurs, niveau):
    r = analyser_relocation(faire_annonce(**valeurs))
    assert r["niveau"] == niveau
    assert len(r["a_confirmer"]) == 4
    if niveau == "vigilance":
        assert r["vigilances"]


def test_cashflow_nul_ou_negatif_ne_suffit_pas_pour_une_pepite(config):
    cfg = deepcopy(config)
    cfg.donnees["analyse"]["financement"]["taux_pct"] = 0
    cfg.donnees["analyse"]["negociation"]["cashflow_cible_mensuel"] = 0
    a = faire_annonce(titre="Murs occupés", score=85, loyer_mensuel=1700)
    revenu = hypotheses_exploitation(a, cfg)["revenu_prudent"]
    a.prix = revenu * 240 / .8 / 1.08
    assert analyser_decision(a, cfg)["cashflow_prudent"] == 0
    assert not est_pepite(a, cfg)
    a.prix -= 1000
    assert est_pepite(a, cfg)
    a.prix += 2000
    assert not est_pepite(a, cfg)


def test_pas_alerte_pepite_si_relocation_risquee_ou_cashflow_negatif(config, monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.delenv("EMAIL_TO", raising=False)
    risque = faire_annonce(id="risque", score=90, loyer_mensuel=2300, rue_categorie="peu_commercante")
    deficit = faire_annonce(id="deficit", score=90, loyer_mensuel=1000)
    assert notifier({a.id: a for a in [risque, deficit]}, [], {}, config)["pepites"] == 0


def test_contact_demande_les_contraintes_de_relocation():
    messages = messages_contact(faire_annonce())
    assert "activités sont autorisées" in messages["court"]
    assert "délai de relocation" in messages["court"]
    assert "restrictions du bail" in messages["dossier"]
