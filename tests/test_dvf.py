"""Ventes réelles DVF : regroupement par mutation, filtres, cache, seuil."""
from __future__ import annotations

import json

from pipeline.dvf import VentesDvf, actualiser_dvf, extraire_prix_m2
from pipeline.enrichissement import Benchmarks, enrichir
from tests.fabriques import faire_annonce

ENTETE = ("id_mutation,date_mutation,nature_mutation,valeur_fonciere,"
          "type_local,surface_reelle_bati,code_postal")


def _csv(*lignes: str) -> str:
    return ENTETE + "\n" + "\n".join(lignes) + "\n"


class TestExtrairePrixM2:
    def test_vente_simple(self):
        csv = _csv('m1,2024-03-01,Vente,300000,Local industriel. commercial ou assimilé,50,75018')
        assert extraire_prix_m2(csv) == [6000]

    def test_mutation_multilots_la_valeur_est_celle_de_la_mutation_entiere(self):
        # 2 lignes, MÊME mutation : la valeur foncière (300 000) est répétée sur
        # chaque ligne — le prix/m² correct est 300000/(40+20), pas 300000/40.
        csv = _csv(
            'm1,2024-03-01,Vente,300000,Local industriel. commercial ou assimilé,40,75018',
            'm1,2024-03-01,Vente,300000,Local industriel. commercial ou assimilé,20,75018',
        )
        assert extraire_prix_m2(csv) == [5000]

    def test_mutation_melant_habitation_ecartee(self):
        # Boutique + appartement vendus ensemble : impossible d'isoler le prix
        # du local — la mutation entière est écartée.
        csv = _csv(
            'm1,2024-03-01,Vente,800000,Local industriel. commercial ou assimilé,50,75018',
            'm1,2024-03-01,Vente,800000,Appartement,60,75018',
        )
        assert extraire_prix_m2(csv) == []

    def test_dependance_toleree(self):
        csv = _csv(
            'm1,2024-03-01,Vente,240000,Local industriel. commercial ou assimilé,40,75018',
            'm1,2024-03-01,Vente,240000,Dépendance,8,75018',
        )
        assert extraire_prix_m2(csv) == [6000]

    def test_filtres_de_vraisemblance(self):
        csv = _csv(
            # vente symbolique (1 €), micro-surface, prix/m² délirant : écartées
            'm1,2024-01-01,Vente,1,Local industriel. commercial ou assimilé,50,75018',
            'm2,2024-01-01,Vente,200000,Local industriel. commercial ou assimilé,4,75018',
            'm3,2024-01-01,Vente,9000000,Local industriel. commercial ou assimilé,50,75018',
            # échange (pas une vente)
            'm4,2024-01-01,Echange,300000,Local industriel. commercial ou assimilé,50,75018',
            # la seule valable
            'm5,2024-01-01,Vente,150000,Local industriel. commercial ou assimilé,30,75018',
        )
        assert extraire_prix_m2(csv) == [5000]


class TestVentesDvf:
    def _dvf(self, nb: int) -> VentesDvf:
        return VentesDvf({
            "insee_par_cp": {"75018": "75118"},
            "communes": {"75118": {"nb": nb, "p25": 4000, "p50": 5000, "p75": 6500,
                                   "periode": "2023-2025"}},
        }, ventes_minimum=6)

    def test_secteur_avec_assez_de_ventes(self):
        ventes = self._dvf(nb=25).pour("75018")
        assert ventes.prix_m2_median == 5000
        assert ventes.nb == 25

    def test_trop_peu_de_ventes_rend_none(self):
        assert self._dvf(nb=5).pour("75018") is None

    def test_commune_inconnue_rend_none(self):
        assert self._dvf(nb=25).pour("93100") is None


class TestEnrichirAvecDvf:
    def test_les_ventes_reelles_priment_sur_le_referentiel(self, benchmarks):
        a = faire_annonce(prix=250_000.0, surface_m2=50.0, code_postal="75018",
                          departement="75")  # 5 000 €/m²
        dvf = TestVentesDvf()._dvf(nb=25)
        enrichir(a, benchmarks, seuil_decote_pct=20, dvf=dvf)
        assert a.marche_prix_m2_bas == 4000    # P25 des ventes, pas le référentiel
        assert a.marche_prix_m2_haut == 6500
        assert a.decote_pct == 0.0             # pile la médiane DVF (5 000)
        assert "ventes réelles" in a.benchmark_source and "DVF" in a.benchmark_source

    def test_sans_ventes_le_referentiel_reste_le_filet(self, benchmarks):
        a = faire_annonce(prix=250_000.0, surface_m2=50.0, code_postal="93100",
                          departement="93")
        dvf = TestVentesDvf()._dvf(nb=25)  # ne connaît que le 75018
        enrichir(a, benchmarks, seuil_decote_pct=20, dvf=dvf)
        assert a.benchmark_source == "référentiel interne"
        assert a.marche_prix_m2_bas is not None


class TestActualiserDvf:
    def test_inactif_rend_none(self, tmp_path):
        assert actualiser_dvf(tmp_path / "dvf.json", ["75018"], {"actif": False}) is None

    def test_commune_fraiche_pas_de_nouvel_appel(self, tmp_path, monkeypatch):
        from pipeline.normalisation import maintenant_iso
        chemin = tmp_path / "dvf.json"
        chemin.write_text(json.dumps({
            "maj": maintenant_iso(),
            "insee_par_cp": {"75018": "75118"},
            "communes": {"75118": {"maj": maintenant_iso(), "annees": [2023, 2024, 2025],
                                   "nb": 30, "p25": 4000, "p50": 5000, "p75": 6500,
                                   "periode": "2023-2025"}},
        }), encoding="utf-8")
        appels = []
        monkeypatch.setattr("pipeline.dvf.requests.Session.get",
                            lambda self, *a, **k: appels.append(a) or (_ for _ in ()).throw(RuntimeError("ne doit pas appeler")))
        dvf = actualiser_dvf(chemin, ["75018"], {"actif": True, "ventes_minimum": 6,
                                                 "annees": [2023, 2024, 2025]})
        assert appels == []
        assert dvf.pour("75018").prix_m2_median == 5000
