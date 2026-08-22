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


# --- Classe énergie (DPE) : volet E de l'ESG, détection stricte ---


def test_dpe_detecte_dans_le_texte(benchmarks):
    from pipeline.enrichissement import dpe_depuis_texte
    assert dpe_depuis_texte("Local commercial, DPE : G, travaux à prévoir") == "G"
    assert dpe_depuis_texte("Classe énergie B, refait à neuf") == "B"
    assert dpe_depuis_texte("Étiquette énergétique : c") == "C"
    assert dpe_depuis_texte("DPE classe F") == "F"


def test_dpe_jamais_devine(benchmarks):
    from pipeline.enrichissement import dpe_depuis_texte
    assert dpe_depuis_texte("DPE gratuit sur demande") is None      # « g » de gratuit
    assert dpe_depuis_texte("DPE en cours de réalisation") is None  # « e » de en
    assert dpe_depuis_texte("Beau local, classe affaires") is None
    assert dpe_depuis_texte("Aucun diagnostic mentionné") is None


def test_dpe_renseigne_sur_l_annonce(benchmarks):
    a = faire_annonce(description="Boutique en pied d'immeuble. DPE : G.")
    enrichir(a, benchmarks, seuil_decote_pct=20)
    assert a.dpe_classe == "G"


def test_annee_fin_bail_jusquen():
    from pipeline.enrichissement import annee_fin_bail
    assert annee_fin_bail("Murs loués, bail jusqu'en 2032, aucune échéance avant.") == 2032
    assert annee_fin_bail("Bail jusqu'à 2029, locataire sérieux.") == 2029
    assert annee_fin_bail("Bail jusqu'au 15/03/2030, loyer à jour.") == 2030


def test_annee_fin_bail_expire_ou_echeance():
    from pipeline.enrichissement import annee_fin_bail
    assert annee_fin_bail("Attention, le bail expire en 2027.") == 2027
    assert annee_fin_bail("Échéance triennale prévue en 2028.") == 2028


def test_annee_fin_bail_absente_ou_hors_bornes():
    from pipeline.enrichissement import annee_fin_bail
    assert annee_fin_bail("Murs loués, bail 3/6/9 en cours, rien de plus précisé.") is None
    assert annee_fin_bail("Immeuble construit en 1978, bail jusqu'en 1985.") is None  # hors bornes


def test_annee_fin_bail_renseignee_sur_l_annonce(benchmarks):
    a = faire_annonce(description="Murs loués, bail jusqu'en 2032.")
    enrichir(a, benchmarks, seuil_decote_pct=20)
    assert a.bail_echeance_annee == 2032


def test_emplacement_numero_formes_courantes():
    from pipeline.enrichissement import emplacement_numero_depuis_texte
    assert emplacement_numero_depuis_texte("Bel emplacement n°1 sur rue commerçante.") == "1"
    assert emplacement_numero_depuis_texte("Emplacement N°1 bis, très bon passage.") == "1bis"
    assert emplacement_numero_depuis_texte("Emplacement numéro 2, correct.") == "2"
    assert emplacement_numero_depuis_texte("emplacement no3, secondaire.") == "3"
    assert emplacement_numero_depuis_texte("Local vide, aucune mention.") is None


def test_emplacement_numero_pas_devine_depuis_autre_chose():
    from pipeline.enrichissement import emplacement_numero_depuis_texte
    # "emplacement" seul, sans marqueur n°/numero, ne doit rien matcher
    assert emplacement_numero_depuis_texte("Très bel emplacement, 1er étage.") is None


def test_emplacement_numero_renseigne_sur_l_annonce(benchmarks):
    a = faire_annonce(description="Murs loués, emplacement n°1 sur rue passante.")
    enrichir(a, benchmarks, seuil_decote_pct=20)
    assert a.emplacement_numero == "1"


def test_taxe_fonciere_annuelle_extraite():
    from pipeline.enrichissement import taxe_fonciere_annuelle_depuis_texte
    assert taxe_fonciere_annuelle_depuis_texte("Murs loués, taxe foncière : 3 200 €/an.") == 3200
    assert taxe_fonciere_annuelle_depuis_texte("Taxe foncière de 1500€ à la charge du bailleur.") == 1500
    assert taxe_fonciere_annuelle_depuis_texte("Aucune mention de taxe ici.") is None


def test_taxe_fonciere_annuelle_hors_bornes_ecartee():
    from pipeline.enrichissement import taxe_fonciere_annuelle_depuis_texte
    # 50€ de taxe foncière annuelle est implausible pour un local commercial :
    # probablement une erreur de lecture (ex. confusion avec autre chose)
    assert taxe_fonciere_annuelle_depuis_texte("Taxe foncière : 50 €.") is None


def test_taxe_fonciere_renseignee_sur_l_annonce(benchmarks):
    a = faire_annonce(description="Murs loués, taxe foncière : 2400€/an, loyer stable.")
    enrichir(a, benchmarks, seuil_decote_pct=20)
    assert a.taxe_fonciere_annuelle == 2400


def test_dpe_passoire_malus_et_vertueux_bonus(config, benchmarks):
    from pipeline.scoring import scorer
    passoire = faire_annonce(description="Local commercial, DPE : G.")
    enrichir(passoire, benchmarks, seuil_decote_pct=20)
    scorer(passoire, config)
    assert "dpe_passoire" in passoire.bonus_detectes
    assert passoire.detail_score["bonus_malus"] == -2.0

    vertueux = faire_annonce(description="Local refait, classe énergie A.")
    enrichir(vertueux, benchmarks, seuil_decote_pct=20)
    scorer(vertueux, config)
    assert "dpe_vertueux" in vertueux.bonus_detectes
    assert vertueux.detail_score["bonus_malus"] == 1.0

    muet = faire_annonce(description="Local commercial bien placé.")
    enrichir(muet, benchmarks, seuil_decote_pct=20)
    scorer(muet, config)
    assert muet.detail_score["bonus_malus"] == 0.0  # non mentionné = neutre
