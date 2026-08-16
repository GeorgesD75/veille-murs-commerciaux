"""Historique de santé des sources : détection de panne silencieuse."""
from __future__ import annotations

import json

from pipeline.sante import charger, mettre_a_jour, sources_en_panne


def test_mettre_a_jour_ajoute_une_entree_par_jour(tmp_path):
    chemin = tmp_path / "sante_sources.json"
    sante = {"pointdevente": {"statut": "ok", "annonces": 30}}
    historique = mettre_a_jour(chemin, sante, "2026-08-12T07:00:00+02:00")
    assert historique["pointdevente"] == [
        {"jour": "2026-08-12", "statut": "ok", "annonces": 30, "message": None}
    ]
    assert json.loads(chemin.read_text(encoding="utf-8")) == historique


def test_deux_tournees_le_meme_jour_ne_comptent_que_pour_un_jour(tmp_path):
    chemin = tmp_path / "sante_sources.json"
    mettre_a_jour(chemin, {"imap": {"statut": "erreur", "message": "premier échec"}},
                  "2026-08-12T07:00:00+02:00")
    historique = mettre_a_jour(chemin, {"imap": {"statut": "erreur", "message": "second échec"}},
                                "2026-08-12T15:00:00+02:00")
    assert len(historique["imap"]) == 1
    assert historique["imap"][0]["message"] == "second échec"


def test_jours_retenus_borne_la_fenetre(tmp_path):
    chemin = tmp_path / "sante_sources.json"
    historique = {}
    for jour in ["2026-08-01", "2026-08-02", "2026-08-03", "2026-08-04"]:
        historique = mettre_a_jour(
            chemin, {"cessionpme": {"statut": "ok", "annonces": 0}}, f"{jour}T07:00:00+02:00",
            jours_retenus=2,
        )
    assert [e["jour"] for e in historique["cessionpme"]] == ["2026-08-03", "2026-08-04"]


def test_charger_fichier_absent_renvoie_vide(tmp_path):
    assert charger(tmp_path / "inexistant.json") == {}


class TestSourcesEnPanne:
    def _historique(self, jours: list[dict]) -> dict:
        return {"imap": jours}

    def test_erreur_n_jours_de_suite_declenche(self):
        historique = self._historique([
            {"jour": "2026-08-10", "statut": "erreur", "annonces": 0, "message": "AUTH"},
            {"jour": "2026-08-11", "statut": "erreur", "annonces": 0, "message": "AUTH"},
        ])
        pannes = sources_en_panne(historique, jours_consecutifs=2)
        assert len(pannes) == 1
        assert pannes[0]["source"] == "imap"
        assert pannes[0]["jours"] == 2
        assert pannes[0]["depuis"] == "2026-08-10"
        assert pannes[0]["dernier_message"] == "AUTH"

    def test_zero_annonce_compte_comme_panne_meme_statut_ok(self):
        historique = {"cessionpme": [
            {"jour": "2026-08-10", "statut": "ok", "annonces": 0, "message": None},
            {"jour": "2026-08-11", "statut": "ok", "annonces": 0, "message": None},
        ]}
        assert len(sources_en_panne(historique, jours_consecutifs=2)) == 1

    def test_un_seul_jour_ok_dans_la_fenetre_n_alerte_pas(self):
        historique = self._historique([
            {"jour": "2026-08-10", "statut": "erreur", "annonces": 0, "message": "AUTH"},
            {"jour": "2026-08-11", "statut": "ok", "annonces": 12, "message": None},
        ])
        assert sources_en_panne(historique, jours_consecutifs=2) == []

    def test_historique_trop_court_n_alerte_pas(self):
        historique = self._historique([
            {"jour": "2026-08-11", "statut": "erreur", "annonces": 0, "message": "AUTH"},
        ])
        assert sources_en_panne(historique, jours_consecutifs=2) == []

    def test_source_volume_sporadique_zero_annonce_n_alerte_pas(self):
        # encheres_publiques : une semaine sans enchère IdF dans le budget est
        # un résultat plausible, pas une panne (constaté le 2026-08-16).
        historique = {"encheres_publiques": [
            {"jour": "2026-08-15", "statut": "ok", "annonces": 0, "message": None},
            {"jour": "2026-08-16", "statut": "ok", "annonces": 0, "message": None},
        ]}
        assert sources_en_panne(
            historique, jours_consecutifs=2, sources_volume_sporadique={"encheres_publiques"}
        ) == []

    def test_source_volume_sporadique_reste_alertee_si_vraie_erreur(self):
        # L'exemption ne couvre que le « 0 annonce » — un statut d'erreur
        # explicite (identifiants, site en panne…) déclenche toujours.
        historique = {"encheres_publiques": [
            {"jour": "2026-08-15", "statut": "erreur", "annonces": 0, "message": "HTTP 500"},
            {"jour": "2026-08-16", "statut": "erreur", "annonces": 0, "message": "HTTP 500"},
        ]}
        pannes = sources_en_panne(
            historique, jours_consecutifs=2, sources_volume_sporadique={"encheres_publiques"}
        )
        assert len(pannes) == 1
