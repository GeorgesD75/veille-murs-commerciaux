"""Collecteur d'enchères judiciaires/publiques (canal spécial, hors scoring)."""
from __future__ import annotations

from pathlib import Path

from sources.encheres import CollecteurEncheres

FIXTURES = Path(__file__).parent / "fixtures"


def _extraire():
    html = (FIXTURES / "encheres_publiques.html").read_text(encoding="utf-8")
    return CollecteurEncheres().extraire(html)


def test_seuls_les_lots_idf_a_venir_sont_gardes():
    lots = _extraire()
    # Le lot adjugé et le lot lyonnais sont ignorés
    assert [lot["id"] for lot in lots] == ["400001"]


def test_champs_du_lot():
    lot = _extraire()[0]
    assert lot["mise_a_prix"] == 50_000
    assert lot["surface_m2"] == 88.44
    assert lot["prix_m2_mise_a_prix"] == 565
    assert lot["departement"] == "75"
    assert lot["date_vente"] == "2026-07-09"
    assert lot["type_vente"] == "En salle"
    assert lot["url"].endswith("_400001")


def test_score_enchere(benchmarks, trajets, config):
    from datetime import date

    from sources.encheres import scorer_lots

    lots, nb_ecartes = scorer_lots(_extraire(), benchmarks, trajets, config,
                                   maintenant=date(2026, 7, 3))
    assert nb_ecartes == 0
    lot = lots[0]
    # Aucune prédiction du prix final : seulement des valeurs de marché sourcées
    assert "prix_probable" not in lot
    assert lot["valeur_marche_basse"] == 265_320   # 3 000 €/m² × 88,44
    assert lot["prix_max_conseille"] == 265_320
    # Emplacement Paris 30 ; gabarit 10 (médiane 420 090 € juste au-dessus du
    # budget max) ; départ 15 (mise à prix à 81 % sous le plafond) ;
    # dossier 6 (surface seule) ; trajet 10 ; vente J+6 -> 5
    assert lot["detail_score"] == {
        "emplacement": 30.0, "gabarit": 10.0, "depart": 15.0,
        "dossier": 6.0, "proximite": 10.0, "preparation": 5.0,
    }
    assert lot["score_enchere"] == 76
    assert lot["haut_panier"] is True


def test_mise_a_prix_au_dessus_du_plafond_ecartee(benchmarks, trajets, config):
    from datetime import date

    from sources.encheres import scorer_lots

    lots = _extraire()
    lots[0]["mise_a_prix"] = 300_000  # > plafond de raison 265 320 € : départ mort
    gardes, nb_ecartes = scorer_lots(lots, benchmarks, trajets, config,
                                     maintenant=date(2026, 7, 3))
    assert nb_ecartes == 1
    assert gardes == []


def test_lecture_prix_decote_travaux(benchmarks):
    from pipeline.enrichissement import enrichir
    from tests.fabriques import faire_annonce

    a = faire_annonce(
        description="Murs loués, prévoir des travaux de rafraîchissement.",
        prix=160_000.0, surface_m2=100.0,  # 1 600 €/m² dans le 93 : décote ~26 %
        code_postal="93400",
    )
    enrichir(a, benchmarks, 20)
    assert "travaux" in a.lecture_prix


def test_lecture_prix_decote_inexpliquee(benchmarks):
    from pipeline.enrichissement import enrichir
    from tests.fabriques import faire_annonce

    a = faire_annonce(
        description="Murs de boutique en excellent état.",
        prix=160_000.0, surface_m2=100.0, code_postal="93400",
    )
    enrichir(a, benchmarks, 20)
    assert "défaut caché" in a.lecture_prix


def test_lecture_prix_prime_petite_surface_paris(benchmarks):
    from pipeline.enrichissement import enrichir
    from tests.fabriques import faire_annonce

    a = faire_annonce(
        titre="Murs de boutique occupés", description="Murs loués.",
        ville="Paris 18e", code_postal="75018", departement="75",
        prix=195_000.0, surface_m2=14.0,  # ~13 900 €/m² : nettement au-dessus
    )
    enrichir(a, benchmarks, 20)
    assert "petites surfaces" in a.lecture_prix
