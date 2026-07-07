"""Précision des temps de trajet Paris : par arrondissement, pas une valeur unique."""
from __future__ import annotations

from pathlib import Path

from pipeline.geo import Trajets, arrondissement_paris

RACINE = Path(__file__).parent.parent


def _trajets() -> Trajets:
    return Trajets.charger(RACINE / "data" / "trajets.json")


class TestArrondissementParis:
    def test_depuis_code_postal(self):
        assert arrondissement_paris("Paris", "75015") == 15
        assert arrondissement_paris("Paris", "75001") == 1

    def test_depuis_texte_avec_suffixe_e(self):
        assert arrondissement_paris("Paris 18e") == 18
        assert arrondissement_paris("Paris 5e") == 5

    def test_depuis_texte_avec_1er(self):
        assert arrondissement_paris("Paris 1er") == 1

    def test_depuis_texte_sans_suffixe(self):
        assert arrondissement_paris("Paris 5") == 5

    def test_depuis_texte_eme(self):
        assert arrondissement_paris("Paris 5ème") == 5

    def test_code_postal_complet_dans_le_texte_ville(self):
        assert arrondissement_paris("Paris 75018") == 18

    def test_paris_seul_sans_numero_est_indetermine(self):
        assert arrondissement_paris("Paris") is None

    def test_hors_paris_indetermine(self):
        assert arrondissement_paris("Montreuil", "93100") is None


class TestTempsDepuisParis18:
    def test_15e_est_beaucoup_plus_loin_que_18e(self):
        """Régression du bug signalé : « ≈ 15 min » affiché pour un local du
        15e (en réalité 40-50 min selon l'utilisateur, départ Château Rouge
        ligne 4 / Lamarck-Caulaincourt ligne 12)."""
        trajets = _trajets()
        temps_18e = trajets.temps_depuis_paris18("Paris 18e", "75", "75018")
        temps_15e = trajets.temps_depuis_paris18("Paris 15e", "75", "75015")
        assert temps_15e >= 40
        assert temps_15e > temps_18e + 20

    def test_arrondissement_lu_depuis_le_code_postal(self):
        trajets = _trajets()
        assert trajets.temps_depuis_paris18("Paris", "75", "75009") == trajets.arrondissements_paris["9"]

    def test_arrondissement_lu_depuis_le_texte_ville_sans_code_postal(self):
        # cas encheres.py : pas de code postal, seulement un texte de ville
        trajets = _trajets()
        assert trajets.temps_depuis_paris18("Paris 12e", "75") == trajets.arrondissements_paris["12"]

    def test_paris_sans_arrondissement_retombe_sur_le_defaut(self):
        trajets = _trajets()
        assert trajets.temps_depuis_paris18("Paris", "75") == trajets.communes["paris"]

    def test_hors_paris_inchange(self):
        trajets = _trajets()
        assert trajets.temps_depuis_paris18("Pantin", "93") == trajets.communes["pantin"]
