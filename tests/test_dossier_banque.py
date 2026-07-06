"""Dossiers banquier Excel : contenu, formules vivantes, cycle de vie."""
from __future__ import annotations

from openpyxl import load_workbook

from dashboard.dossier_banque import generer_dossier, generer_dossiers
from pipeline.modeles import TypeMurs
from tests.fabriques import faire_annonce


def _annonce_complete(**surcharges):
    defauts = dict(
        score=68,
        detail_score={"rendement": 30, "emplacement": 20},
        decote_pct=12.0,
        marche_prix_m2_bas=2000.0,
        marche_prix_m2_haut=3200.0,
    )
    defauts.update(surcharges)
    return faire_annonce(**defauts)


class TestClasseur:
    def test_contenu_et_formules(self, config, tmp_path):
        cible = tmp_path / "dossier.xlsx"
        generer_dossier(_annonce_complete(), config, cible)
        wb = load_workbook(cible)
        assert wb.sheetnames == ["Synthèse", "Amortissement", "Annonce"]

        syn = wb["Synthèse"]
        assert "Dossier de financement" in syn["A1"].value
        assert syn["B9"].value == 250_000            # prix affiché
        assert syn["B11"].value == 1_700             # loyer du bail
        assert syn["B15"].value == 250_000           # hypothèse prix négocié
        # formules vivantes : le banquier peut changer taux/apport/durée
        assert syn["B28"].value.startswith("=IFERROR(-PMT(")
        assert syn["B44"].value.startswith("=IFERROR(B36/B29")   # DSCR
        assert "EN CLAIR" in syn["A49"].value
        assert "s'autofinance" in syn["A49"].value   # 1 700 €/mois sur 250 k€

        amort = wb["Amortissement"]
        assert amort["B2"].value == "=IF(A2<=$G$1,'Synthèse'!$B$27,\"\")"

        annonce = wb["Annonce"]
        assert annonce["B2"].hyperlink.target == "https://exemple.fr/1"

    def test_loyer_estime_marque_honnetement(self, config, tmp_path):
        a = _annonce_complete(
            type_murs=TypeMurs.MURS_LIBRES, loyer_mensuel=None,
            loyer_mensuel_estime=1_500.0, loyer_estime=True,
        )
        generer_dossier(a, config, tmp_path / "d.xlsx")
        syn = load_workbook(tmp_path / "d.xlsx")["Synthèse"]
        assert syn["B11"].value == 1_500
        assert "ESTIM" in (syn["C11"].value or "")   # note « ESTIMATION … »
        assert "ESTIMÉ" in syn["A49"].value          # verdict transparent

    def test_avertissement_rendement_suspect(self, config, tmp_path):
        a = _annonce_complete(flags=["rendement_anormalement_eleve"])
        generer_dossier(a, config, tmp_path / "d.xlsx")
        syn = load_workbook(tmp_path / "d.xlsx")["Synthèse"]
        assert "AVERTISSEMENT" in syn["A52"].value


class TestCycleDeVie:
    def test_seuil_exclusions_et_nettoyage(self, config, tmp_path):
        dossier = tmp_path / "dossiers"
        dossier.mkdir()
        (dossier / "dossier-fantome-deadbeef.xlsx").write_bytes(b"obsolete")

        annonces = {
            "ok": _annonce_complete(id="ok1234567890abcd", score=68),
            "faible": _annonce_complete(id="fa1234567890abcd", score=40),
            "exclue": _annonce_complete(id="ex1234567890abcd", score=90, exclue=True),
            "sans_prix": _annonce_complete(id="sp1234567890abcd", score=90, prix=None),
        }
        resultats = generer_dossiers(annonces, config, dossier)

        assert set(resultats) == {"ok1234567890abcd"}
        assert resultats["ok1234567890abcd"] == "dossier-pantin-ok123456.xlsx"
        restants = {f.name for f in dossier.glob("*.xlsx")}
        assert restants == {"dossier-pantin-ok123456.xlsx"}  # le fantôme est purgé
