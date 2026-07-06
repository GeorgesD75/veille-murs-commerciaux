"""Scoring /100 : linéarité du rendement, emplacement, benchmark, flags, pépite."""
from __future__ import annotations

from pipeline.enrichissement import enrichir
from pipeline.scoring import scorer
from tests.fabriques import faire_annonce

# --- Rendement (40 pts, linéaire de 4 % à 9 %) ---


def test_rendement_plancher_zero_point(config):
    a = faire_annonce()
    a.rendement_brut_pct = 4.0
    scorer(a, config)
    assert a.detail_score["rendement"] == 0.0


def test_rendement_plafond_quarante_points(config):
    a = faire_annonce()
    a.rendement_brut_pct = 9.0
    scorer(a, config)
    assert a.detail_score["rendement"] == 40.0


def test_rendement_intermediaire_lineaire(config):
    a = faire_annonce()
    a.rendement_brut_pct = 6.5  # à mi-chemin -> 20 pts
    scorer(a, config)
    assert a.detail_score["rendement"] == 20.0


def test_rendement_au_dela_du_plafond_plafonne(config):
    a = faire_annonce()
    a.rendement_brut_pct = 12.0
    scorer(a, config)
    assert a.detail_score["rendement"] == 40.0


def test_penalite_murs_libres_loyer_estime(config):
    a = faire_annonce()
    a.rendement_brut_pct = 9.0
    a.loyer_estime = True
    scorer(a, config)
    assert a.detail_score["rendement"] == 30.0  # 40 - 10 d'incertitude


def test_rendement_inconnu_zero_point(config):
    a = faire_annonce()
    a.rendement_brut_pct = None
    scorer(a, config)
    assert a.detail_score["rendement"] == 0.0


# --- Emplacement (25 pts) ---


def test_emplacement_paris(config):
    a = faire_annonce(ville="Paris 18e", code_postal="75018", departement="75")
    scorer(a, config)
    assert a.detail_score["emplacement"] == 25.0


def test_emplacement_petite_couronne_dynamique(config):
    a = faire_annonce(ville="Pantin", departement="93")
    scorer(a, config)
    assert a.detail_score["emplacement"] == 20.0


def test_emplacement_commune_dynamique_nom_long(config):
    a = faire_annonce(ville="Saint-Ouen-sur-Seine", code_postal="93400", departement="93")
    scorer(a, config)
    assert a.detail_score["emplacement"] == 20.0


def test_emplacement_petite_couronne_autre(config):
    a = faire_annonce(ville="Vincennes", code_postal="94300", departement="94")
    scorer(a, config)
    assert a.detail_score["emplacement"] == 15.0


def test_emplacement_grande_couronne_centre_ville(config):
    a = faire_annonce(
        ville="Argenteuil",
        code_postal="95100",
        departement="95",
        description="Local en plein centre-ville, proche gare.",
    )
    scorer(a, config)
    assert a.detail_score["emplacement"] == 10.0


def test_emplacement_grande_couronne_autre(config):
    a = faire_annonce(
        ville="Meaux", code_postal="77100", departement="77", description="Zone commerciale."
    )
    scorer(a, config)
    assert a.detail_score["emplacement"] == 5.0


def test_penalite_loyer_estime_comparables_reduite(config):
    # Un loyer adossé à des baux réels voisins pèse moins qu'une estimation
    # générique de zone : la pénalité d'incertitude est plus faible.
    a = faire_annonce()
    a.rendement_brut_pct = 9.0
    a.loyer_estime = True
    a.loyer_confiance = "comparables"
    scorer(a, config)
    assert a.detail_score["rendement"] == 36.0  # 40 - 4 (comparables) au lieu de 40 - 10


def test_penalite_loyer_estime_benchmark_inchangee(config):
    a = faire_annonce()
    a.rendement_brut_pct = 9.0
    a.loyer_estime = True
    a.loyer_confiance = "benchmark"
    scorer(a, config)
    assert a.detail_score["rendement"] == 30.0  # 40 - 10, comme avant


# --- Emplacement rue par rue (ajustement du palier administratif) ---


def test_rue_tres_commercante_ajoute_des_points(config):
    a = faire_annonce(ville="Meaux", code_postal="77100", departement="77")  # 5 pts de base
    a.rue_categorie = "tres_commercante"
    a.rue_nb_vacants = 0
    scorer(a, config)
    assert a.detail_score["emplacement"] == 9.0  # 5 + 4


def test_rue_peu_commercante_retire_des_points(config):
    a = faire_annonce(ville="Paris 18e", code_postal="75018", departement="75")  # 25 pts de base
    a.rue_categorie = "peu_commercante"
    a.rue_nb_vacants = 0
    scorer(a, config)
    assert a.detail_score["emplacement"] == 21.0  # 25 - 4


def test_rue_vacance_commerciale_ajoute_un_malus(config):
    a = faire_annonce(ville="Paris 18e", code_postal="75018", departement="75")
    a.rue_categorie = "calme"       # 0 ajustement
    a.rue_nb_vacants = 5             # >= seuil (3) -> malus supplémentaire
    scorer(a, config)
    assert a.detail_score["emplacement"] == 22.0  # 25 + 0 - 3


def test_rue_ajustement_ne_depasse_jamais_le_plafond(config):
    a = faire_annonce(ville="Paris 18e", code_postal="75018", departement="75")  # déjà 25/25
    a.rue_categorie = "tres_commercante"  # +4, mais plafonné
    a.rue_nb_vacants = 0
    scorer(a, config)
    assert a.detail_score["emplacement"] == 25.0


def test_rue_non_evaluee_score_inchange(config):
    # rue_categorie=None (valeur par défaut) : comportement strictement identique
    # à avant l'introduction du signal de rue.
    a = faire_annonce(ville="Meaux", code_postal="77100", departement="77")
    scorer(a, config)
    assert a.detail_score["emplacement"] == 5.0


# --- Prix/m² vs benchmark (20 pts) et proximité (10 pts) ---


def test_points_benchmark(config):
    a = faire_annonce()
    for position, attendu in [("decote_forte", 20.0), ("dans_fourchette", 10.0), ("surcote", 0.0)]:
        a.position_benchmark = position
        scorer(a, config)
        assert a.detail_score["prix_m2_vs_benchmark"] == attendu


def test_points_proximite(config):
    a = faire_annonce()
    for temps, attendu in [(10, 5.0), (30, 3.0), (55, 1.0)]:
        a.temps_trajet_min = temps
        scorer(a, config)
        assert a.detail_score["proximite"] == attendu


# --- Quartier (5 pts : attachement au 18e) ---


def test_points_quartier_18e(config):
    a = faire_annonce(ville="Paris 18e", code_postal="75018", departement="75")
    scorer(a, config)
    assert a.detail_score["quartier"] == 5.0


def test_pas_de_points_quartier_ailleurs(config):
    a = faire_annonce(ville="Paris 17e", code_postal="75017", departement="75")
    scorer(a, config)
    assert a.detail_score["quartier"] == 0.0


def test_bareme_total_fait_cent(config):
    s = config.scoring
    total = (
        s["rendement"]["points"] + s["emplacement"]["paris"]
        + s["prix_m2_vs_benchmark"]["decote_forte"]
        + s["proximite"]["moins_de_20_min"] + s["quartier"]["points"] + 5  # bonus max
    )
    assert total == 100


# --- Bonus/malus (borné à [-3 ; +5]) ---


def test_bonus_cumules_plafonnes_a_cinq(config):
    a = faire_annonce(
        description=(
            "Murs occupés, bail récent, taxe foncière à la charge du locataire, "
            "enseigne nationale."
        )
    )
    scorer(a, config)
    assert a.detail_score["bonus_malus"] == 5.0


def test_malus_travaux(config):
    a = faire_annonce(description="Murs loués mais travaux à prévoir.")
    scorer(a, config)
    assert a.detail_score["bonus_malus"] == -3.0


def test_dette_copropriete_flag_prominent(config):
    # Information vitale : signalée par un flag dédié (pas juste un malus de
    # score), pour un badge visible sur le dashboard, distinct du travail.
    a = faire_annonce(description="Murs loués, mais dettes de copropriété en cours.")
    scorer(a, config)
    assert "dette_copropriete" in a.bonus_detectes
    assert "dette_copropriete" in a.flags
    assert a.detail_score["bonus_malus"] == -3.0


def test_pas_de_flag_dette_copropriete_sans_mention(config):
    a = faire_annonce(description="Murs loués, aucun souci signalé.")
    scorer(a, config)
    assert "dette_copropriete" not in a.flags


# --- Flags ---


def test_flag_rendement_anormalement_eleve(config):
    a = faire_annonce()
    a.rendement_brut_pct = 11.0
    scorer(a, config)
    assert "rendement_anormalement_eleve" in a.flags


def test_rendement_suspect_plafonne_le_score(config):
    # 20 % « de rendement » à Paris = piège probable (cession de bail déguisée) :
    # jamais en haut du panier, jamais d'email pépite.
    a = faire_annonce(ville="Paris 10e", code_postal="75010", departement="75")
    a.rendement_brut_pct = 20.0
    a.position_benchmark = "decote_forte"
    a.temps_trajet_min = 10
    scorer(a, config)
    assert a.score is not None
    assert a.score < config.scoring["seuils"]["affichage"]


def test_pas_de_flag_sous_le_seuil(config):
    a = faire_annonce()
    a.rendement_brut_pct = 9.5
    scorer(a, config)
    assert "rendement_anormalement_eleve" not in a.flags


# --- Cas complet : la pépite doit dépasser le seuil d'alerte immédiate ---


def test_pepite_saint_ouen_depasse_80(config, benchmarks):
    a = faire_annonce(
        ville="Saint-Ouen",
        code_postal="93400",
        prix=152_000.0,
        surface_m2=80.0,
        loyer_mensuel=1_200.0,
        description=(
            "Vente des murs occupés. Bail récent, taxe foncière à la charge du locataire, "
            "enseigne nationale en place."
        ),
    )
    a.temps_trajet_min = 10  # renseigné par les filtres dans le pipeline réel
    enrichir(a, benchmarks, config.scoring["prix_m2_vs_benchmark"]["seuil_decote_pct"])
    scorer(a, config)
    assert a.score is not None and a.score >= config.scoring["seuils"]["pepite"]
