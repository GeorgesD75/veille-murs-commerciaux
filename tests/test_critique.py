"""Critique IA (Claude Haiku) : jamais de vrai appel réseau, jamais bloquant."""
from __future__ import annotations

from pipeline.config import Config
from pipeline.critique import generer_critique, generer_critiques
from tests.fabriques import faire_annonce


def _config_critique(seuil_score=60, max_par_run=15) -> Config:
    """Config minimale et JETABLE (la fixture `config` est partagée, scope session)."""
    return Config({"analyse": {"critique_ia": {
        "seuil_score": seuil_score, "max_par_run": max_par_run,
    }}})


class _BlocTexte:
    type = "text"

    def __init__(self, texte: str) -> None:
        self.text = texte


class _Reponse:
    def __init__(self, texte: str, stop_reason: str = "end_turn") -> None:
        self.content = [_BlocTexte(texte)]
        self.stop_reason = stop_reason


class _Messages:
    def __init__(self, reponse=None, erreur=None) -> None:
        self.reponse = reponse
        self.erreur = erreur
        self.appels: list[dict] = []

    def create(self, **kwargs):
        self.appels.append(kwargs)
        if self.erreur:
            raise self.erreur
        return self.reponse


class ClientFactice:
    def __init__(self, reponse=None, erreur=None) -> None:
        self.messages = _Messages(reponse, erreur)


class TestGenererCritique:
    def test_texte_renvoye_et_prompt_contient_les_faits_cles(self):
        client = ClientFactice(reponse=_Reponse("Cette annonce mérite prudence : loyer non prouvé."))
        a = faire_annonce(score=70, rendement_brut_pct=8.5, decote_pct=15.0)
        resultat = generer_critique(a, client=client)
        assert resultat == "Cette annonce mérite prudence : loyer non prouvé."
        prompt = client.messages.appels[0]["messages"][0]["content"]
        assert "Rendement brut : 8.5 %" in prompt
        assert "Score déjà calculé par l'outil : 70/100" in prompt
        assert client.messages.appels[0]["model"] == "claude-haiku-4-5"
        # ni effort ni thinking : non supportés sur Haiku 4.5
        assert "output_config" not in client.messages.appels[0]
        assert "thinking" not in client.messages.appels[0]

    def test_refusal_renvoie_none(self):
        client = ClientFactice(reponse=_Reponse("", stop_reason="refusal"))
        resultat = generer_critique(faire_annonce(), client=client)
        assert resultat is None

    def test_erreur_api_ne_leve_pas(self):
        import anthropic
        erreur = anthropic.APIConnectionError(request=None)
        client = ClientFactice(erreur=erreur)
        assert generer_critique(faire_annonce(), client=client) is None

    def test_sans_cle_api_ni_client_renvoie_none(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        assert generer_critique(faire_annonce()) is None


class TestGenererCritiques:
    def test_plafond_et_priorite_par_score(self, monkeypatch):
        appels = []
        monkeypatch.setattr(
            "pipeline.critique.generer_critique",
            lambda a, client=None: appels.append(a.id) or f"critique de {a.id}",
        )
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-cle")
        annonces = {
            "a": faire_annonce(id="a", score=10),
            "b": faire_annonce(id="b", score=90),
            "c": faire_annonce(id="c", score=50),
        }
        generer_critiques(annonces, _config_critique(seuil_score=0, max_par_run=2))
        assert appels == ["b", "c"]  # meilleurs scores d'abord
        assert annonces["a"].critique_ia is None  # laissée de côté ce run-ci

    def test_sous_le_seuil_de_score_ignoree(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-cle")
        appele = []
        monkeypatch.setattr(
            "pipeline.critique.generer_critique",
            lambda a, client=None: appele.append(1) or "x",
        )
        annonces = {"a": faire_annonce(id="a", score=40)}
        generer_critiques(annonces, _config_critique(seuil_score=60))
        assert appele == []
        assert annonces["a"].critique_ia is None

    def test_deja_critiquee_pas_regeneree(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-cle")
        appele = []
        monkeypatch.setattr(
            "pipeline.critique.generer_critique",
            lambda a, client=None: appele.append(1) or "nouvelle critique",
        )
        a = faire_annonce(score=90, critique_ia="critique existante")
        generer_critiques({"a": a}, _config_critique())
        assert appele == []
        assert a.critique_ia == "critique existante"

    def test_annonce_exclue_ignoree(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-cle")
        a = faire_annonce(score=99, exclue=True)
        generer_critiques({"a": a}, _config_critique())
        assert a.critique_ia is None

    def test_sans_cle_api_aucun_appel(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        a = faire_annonce(score=90)
        generer_critiques({"a": a}, _config_critique())
        assert a.critique_ia is None

    def test_max_par_run_zero_desactive(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-cle")
        a = faire_annonce(score=90)
        generer_critiques({"a": a}, _config_critique(max_par_run=0))
        assert a.critique_ia is None


def test_critique_perimee_apres_forte_baisse_de_prix():
    from pipeline.critique import _critique_perimee
    from tests.fabriques import faire_annonce
    a = faire_annonce(prix=300_000.0)
    a.critique_ia = "Ancienne critique."
    a.critique_ia_prix = 400_000.0   # écrite quand le bien valait 400 k€ : -25 %
    assert _critique_perimee(a) is True
    a.critique_ia_prix = 310_000.0   # -3 % : on ne régénère pas pour si peu
    assert _critique_perimee(a) is False
    a.critique_ia_prix = None        # critique d'avant cette fonctionnalité
    assert _critique_perimee(a) is False
