"""Enrichissement : rendements, prix/m², loyer estimé, position vs benchmark."""
from __future__ import annotations

from pipeline.enrichissement import enrichir
from pipeline.modeles import TypeMurs
from tests.fabriques import faire_annonce

SEUIL_DECOTE = 20


def test_rendement_brut_et_prix_m2(benchmarks):
    a = faire_annonce(prix=300_000.0, loyer_mensuel=2_000.0, surface_m2=100.0)
    enrichir(a, benchmarks, SEUIL_DECOTE)
    assert a.prix_m2 == 3_000
    assert a.rendement_brut_pct == 8.0  # 24 000 / 300 000
    # Prix à offrir pour viser 7 % brut : 24 000 / 0,07
    assert a.prix_cible_rendement == 342_857


def test_rendement_acte_en_main_sans_honoraires(benchmarks):
    a = faire_annonce(prix=300_000.0, loyer_mensuel=2_000.0)
    enrichir(a, benchmarks, SEUIL_DECOTE)
    assert a.rendement_acte_en_main_pct == 7.41  # 24 000 / (300 000 × 1,08)


def test_rendement_acte_en_main_avec_honoraires(benchmarks):
    a = faire_annonce(prix=300_000.0, loyer_mensuel=2_000.0, honoraires=10_000.0)
    enrichir(a, benchmarks, SEUIL_DECOTE)
    assert a.rendement_acte_en_main_pct == 7.19  # 24 000 / 334 000


def test_murs_libres_loyer_estime_au_benchmark(benchmarks):
    # Argenteuil (95) : loyer médian 140 €/m²/an -> 60 m² = 700 €/mois estimés.
    a = faire_annonce(
        type_murs=TypeMurs.MURS_LIBRES,
        loyer_mensuel=None,
        ville="Argenteuil",
        code_postal="95100",
        departement="95",
        prix=160_000.0,
        surface_m2=60.0,
    )
    enrichir(a, benchmarks, SEUIL_DECOTE)
    assert a.loyer_estime is True
    assert a.rendement_brut_pct == 5.25  # 8 400 / 160 000


def test_murs_libres_loyer_declare_reste_hypothetique(benchmarks):
    # Un « loyer » annoncé sur des murs LIBRES est une promesse du vendeur,
    # pas un bail : traité comme estimé (pénalité d'incertitude au scoring).
    from pipeline.modeles import TypeMurs

    a = faire_annonce(type_murs=TypeMurs.MURS_LIBRES, loyer_mensuel=2_300.0,
                      prix=290_000.0, surface_m2=58.0)
    enrichir(a, benchmarks, SEUIL_DECOTE)
    assert a.loyer_estime is True
    assert a.rendement_brut_pct == 9.52


def test_murs_occupes_sans_loyer_pas_de_rendement(benchmarks):
    # Pas d'estimation pour des murs annoncés occupés sans loyer : donnée manquante.
    a = faire_annonce(loyer_mensuel=None)
    enrichir(a, benchmarks, SEUIL_DECOTE)
    assert a.rendement_brut_pct is None
    assert a.loyer_estime is False


def test_position_benchmark_decote_forte(benchmarks):
    # Dépt 93 : fourchette [1500, 2800], médian 2150. 1 600 €/m² -> décote 25,6 %.
    a = faire_annonce(code_postal="93400", prix=160_000.0, surface_m2=100.0)
    enrichir(a, benchmarks, SEUIL_DECOTE)
    assert a.position_benchmark == "decote_forte"


def test_position_benchmark_surcote(benchmarks):
    a = faire_annonce(code_postal="93400", prix=300_000.0, surface_m2=100.0)  # 3 000 €/m²
    enrichir(a, benchmarks, SEUIL_DECOTE)
    assert a.position_benchmark == "surcote"


def test_decote_et_fourchette_marche_exposees(benchmarks):
    # Dépt 93 : fourchette [1500, 2800], médiane 2150 ; 1 600 €/m² -> décote 25,6 %
    a = faire_annonce(code_postal="93400", prix=160_000.0, surface_m2=100.0)
    enrichir(a, benchmarks, SEUIL_DECOTE)
    assert a.marche_prix_m2_bas == 1_500
    assert a.marche_prix_m2_haut == 2_800
    assert a.decote_pct == 25.6


def test_loyer_estime_expose_pour_affichage(benchmarks):
    from pipeline.modeles import TypeMurs

    a = faire_annonce(
        type_murs=TypeMurs.MURS_LIBRES, loyer_mensuel=None,
        code_postal="95100", departement="95", prix=160_000.0, surface_m2=60.0,
    )
    enrichir(a, benchmarks, SEUIL_DECOTE)
    assert a.loyer_mensuel is None          # la donnée source reste intacte
    assert a.loyer_mensuel_estime == 700.0  # affichable avec la mention « est. »


def test_caracteristiques_activite(benchmarks):
    a = faire_annonce(
        description=(
            "Murs loués. Restauration sans conduit possible · Terrasse. "
            "Toutes activités hors nuisances, local d'angle."
        )
    )
    enrichir(a, benchmarks, SEUIL_DECOTE)
    assert "Restauration légère possible (sans conduit)" in a.caracteristiques
    assert "Terrasse" in a.caracteristiques
    assert "Toutes activités" in a.caracteristiques
    assert "Emplacement d'angle" in a.caracteristiques


def test_position_benchmark_commune_prime_sur_departement(benchmarks):
    # 93500 (Pantin) a sa propre fourchette [1800, 3200] : 2 500 €/m² -> dans la fourchette.
    a = faire_annonce(code_postal="93500", prix=250_000.0, surface_m2=100.0)
    enrichir(a, benchmarks, SEUIL_DECOTE)
    assert a.position_benchmark == "dans_fourchette"
