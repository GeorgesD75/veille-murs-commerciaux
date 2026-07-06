"""integrer() : dédoublonnage même-source et historique de prix."""
from __future__ import annotations

from pipeline.modeles import Annonce, AnnonceBrute, TypeMurs
from run import integrer


def _brute(**surcharges) -> AnnonceBrute:
    base = dict(
        id_source="1", source="test", url="https://exemple.fr/1",
        titre="Murs occupés", ville="Pantin", code_postal="93500",
        type_murs=TypeMurs.MURS_OCCUPES, prix=250_000.0, surface_m2=100.0,
        loyer_mensuel=1_700.0,
    )
    base.update(surcharges)
    return AnnonceBrute(**base)


class TestHistoriquePrix:
    def test_premiere_collecte_pas_d_historique(self, config):
        annonces: dict[str, Annonce] = {}
        integrer([_brute()], annonces, config, "2026-07-01T07:00:00+02:00")
        a = next(iter(annonces.values()))
        assert a.historique_prix == []

    def test_prix_stable_pas_d_historique(self, config):
        annonces: dict[str, Annonce] = {}
        integrer([_brute(prix=250_000.0)], annonces, config, "2026-07-01T07:00:00+02:00")
        integrer([_brute(prix=250_000.0)], annonces, config, "2026-07-02T07:00:00+02:00")
        a = next(iter(annonces.values()))
        assert a.historique_prix == []

    def test_baisse_de_prix_horodate_le_depart_et_l_arrivee(self, config):
        annonces: dict[str, Annonce] = {}
        integrer([_brute(prix=250_000.0)], annonces, config, "2026-07-01T07:00:00+02:00")
        integrer([_brute(prix=230_000.0)], annonces, config, "2026-07-05T07:00:00+02:00")
        a = next(iter(annonces.values()))
        assert a.historique_prix == [
            {"date": "2026-07-01T07:00:00+02:00", "prix": 250_000.0},
            {"date": "2026-07-05T07:00:00+02:00", "prix": 230_000.0},
        ]
        assert a.prix == 230_000.0  # le prix courant suit toujours la dernière valeur

    def test_deuxieme_baisse_ajoute_une_seule_entree(self, config):
        annonces: dict[str, Annonce] = {}
        integrer([_brute(prix=250_000.0)], annonces, config, "2026-07-01T07:00:00+02:00")
        integrer([_brute(prix=230_000.0)], annonces, config, "2026-07-05T07:00:00+02:00")
        integrer([_brute(prix=210_000.0)], annonces, config, "2026-07-10T07:00:00+02:00")
        a = next(iter(annonces.values()))
        assert [h["prix"] for h in a.historique_prix] == [250_000.0, 230_000.0, 210_000.0]

    def test_hausse_de_prix_suivie_aussi(self, config):
        annonces: dict[str, Annonce] = {}
        integrer([_brute(prix=250_000.0)], annonces, config, "2026-07-01T07:00:00+02:00")
        integrer([_brute(prix=260_000.0)], annonces, config, "2026-07-05T07:00:00+02:00")
        a = next(iter(annonces.values()))
        assert [h["prix"] for h in a.historique_prix] == [250_000.0, 260_000.0]
