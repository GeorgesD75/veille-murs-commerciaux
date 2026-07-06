"""Loyers comparables : estimation à partir de baux réels voisins, pas d'une moyenne de zone."""
from __future__ import annotations

from pipeline.comparables import LoyersComparables
from pipeline.enrichissement import enrichir
from pipeline.modeles import TypeMurs
from tests.fabriques import faire_annonce

SEUIL_DECOTE = 20


class TestLoyersComparables:
    def test_ignore_les_loyers_estimes_et_les_murs_libres(self):
        occupe_reel = faire_annonce(
            id="a", type_murs=TypeMurs.MURS_OCCUPES, loyer_mensuel=2_000.0, surface_m2=100.0,
            code_postal="75011",
        )
        libre = faire_annonce(
            id="b", type_murs=TypeMurs.MURS_LIBRES, loyer_mensuel=5_000.0, surface_m2=100.0,
            code_postal="75011",
        )
        comp = LoyersComparables.depuis([occupe_reel, libre])
        # un seul bail réel dans ce code postal : sous le minimum (2), pas assez solide
        assert comp.pour("75011") is None

    def test_median_et_nombre_avec_assez_de_comparables(self):
        annonces = [
            faire_annonce(id="a", type_murs=TypeMurs.MURS_OCCUPES,
                          loyer_mensuel=1_000.0, surface_m2=50.0, code_postal="75011"),  # 240/m²/an
            faire_annonce(id="b", type_murs=TypeMurs.MURS_OCCUPES,
                          loyer_mensuel=2_000.0, surface_m2=100.0, code_postal="75011"),  # 240/m²/an
            faire_annonce(id="c", type_murs=TypeMurs.MURS_OCCUPES,
                          loyer_mensuel=10_000.0, surface_m2=50.0, code_postal="75011"),  # 2400/m²/an (outlier)
        ]
        comp = LoyersComparables.depuis(annonces)
        loyer_m2, nb = comp.pour("75011")
        assert nb == 3
        assert loyer_m2 == 240.0  # la médiane ignore l'outlier, contrairement à une moyenne

    def test_code_postal_different_ignore(self):
        annonces = [
            faire_annonce(id="a", type_murs=TypeMurs.MURS_OCCUPES,
                          loyer_mensuel=1_000.0, surface_m2=50.0, code_postal="75011"),
            faire_annonce(id="b", type_murs=TypeMurs.MURS_OCCUPES,
                          loyer_mensuel=1_000.0, surface_m2=50.0, code_postal="75012"),
        ]
        comp = LoyersComparables.depuis(annonces)
        assert comp.pour("75011") is None  # un seul comparable dans le 75011


class TestEnrichirAvecComparables:
    def test_priorite_aux_comparables_sur_le_benchmark(self, benchmarks):
        # Benchmark 95100 : 140 €/m²/an (test_enrichissement.py). Des comparables
        # réels à 300 €/m²/an doivent l'emporter, avec la confiance affichée.
        voisins = [
            faire_annonce(id="v1", type_murs=TypeMurs.MURS_OCCUPES, loyer_mensuel=1_500.0,
                          surface_m2=60.0, code_postal="95100"),   # 300 €/m²/an
            faire_annonce(id="v2", type_murs=TypeMurs.MURS_OCCUPES, loyer_mensuel=1_500.0,
                          surface_m2=60.0, code_postal="95100"),
        ]
        comparables = LoyersComparables.depuis(voisins)
        cible = faire_annonce(
            id="cible", type_murs=TypeMurs.MURS_LIBRES, loyer_mensuel=None,
            ville="Argenteuil", code_postal="95100", departement="95",
            prix=160_000.0, surface_m2=60.0,
        )
        enrichir(cible, benchmarks, SEUIL_DECOTE, comparables=comparables)
        assert cible.loyer_confiance == "comparables"
        assert cible.loyer_nb_comparables == 2
        assert cible.loyer_mensuel_estime == 1_500.0  # 300 * 60 / 12, pas le benchmark (700)

    def test_repli_sur_le_benchmark_sans_comparables_solides(self, benchmarks):
        cible = faire_annonce(
            type_murs=TypeMurs.MURS_LIBRES, loyer_mensuel=None,
            ville="Argenteuil", code_postal="95100", departement="95",
            prix=160_000.0, surface_m2=60.0,
        )
        enrichir(cible, benchmarks, SEUIL_DECOTE, comparables=LoyersComparables.depuis([]))
        assert cible.loyer_confiance == "benchmark"
        assert cible.loyer_nb_comparables is None
        assert cible.loyer_mensuel_estime == 700.0  # comportement historique, inchangé

    def test_sans_argument_comparables_repli_benchmark(self, benchmarks):
        # enrichir() sans le paramètre comparables (ancien appel) continue de
        # marcher : repli sur le benchmark de zone, confiance affichée en conséquence.
        cible = faire_annonce(
            type_murs=TypeMurs.MURS_LIBRES, loyer_mensuel=None,
            ville="Argenteuil", code_postal="95100", departement="95",
            prix=160_000.0, surface_m2=60.0,
        )
        enrichir(cible, benchmarks, SEUIL_DECOTE)
        assert cible.loyer_confiance == "benchmark"
        assert cible.loyer_mensuel_estime == 700.0

    def test_loyer_declare_par_vendeur_sans_confiance_particuliere(self, benchmarks):
        # Un loyer "potentiel" annoncé par le vendeur reste une promesse, même
        # si des comparables solides existent par ailleurs pour ce secteur.
        voisins = [
            faire_annonce(id="v1", type_murs=TypeMurs.MURS_OCCUPES, loyer_mensuel=1_500.0,
                          surface_m2=60.0, code_postal="75011"),
            faire_annonce(id="v2", type_murs=TypeMurs.MURS_OCCUPES, loyer_mensuel=1_500.0,
                          surface_m2=60.0, code_postal="75011"),
        ]
        comparables = LoyersComparables.depuis(voisins)
        cible = faire_annonce(
            type_murs=TypeMurs.MURS_LIBRES, loyer_mensuel=2_300.0,
            code_postal="75011", prix=290_000.0, surface_m2=58.0,
        )
        enrichir(cible, benchmarks, SEUIL_DECOTE, comparables=comparables)
        assert cible.loyer_confiance is None
        assert cible.loyer_estime is True
