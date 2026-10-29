"""Le prix d'offre doit satisfaire le vrai barème sans modifier l'annonce."""
from copy import deepcopy
from datetime import datetime

import pytest

from pipeline.contact import message_negociation
from pipeline.decision import analyser_decision, est_pepite
from pipeline.enrichissement import enrichir
from pipeline.negociation import plan_negociation, simuler_prix
from pipeline.scoring import scorer
from tests.fabriques import faire_annonce

MAINTENANT = datetime.fromisoformat("2026-10-26T12:00:00+01:00")


def candidat(config, benchmarks, **changements):
    valeurs = dict(titre="Murs occupés", description="Murs occupés, locataire en place.",
                   ville="Paris", code_postal="75018", departement="75", surface_m2=35,
                   prix=230000, loyer_mensuel=1400, temps_trajet_min=20,
                   date_derniere_vue=MAINTENANT.isoformat())
    valeurs.update(changements)
    a = faire_annonce(**valeurs)
    enrichir(a, benchmarks, config.scoring["prix_m2_vs_benchmark"]["seuil_decote_pct"])
    scorer(a, config)
    return a


def test_plafond_et_ouverture_satisfont_score_et_equilibre_sans_muter_le_stock(config, benchmarks):
    a = candidat(config, benchmarks)
    avant = deepcopy(a.to_dict())
    n = plan_negociation(a, config, MAINTENANT)
    assert n["statut"] == "a_negocier" and n["selection"]
    assert 0 < n["prix_ouverture"] <= n["prix_plafond"] < a.prix
    assert n["prix_plafond"] % 1000 == 0
    assert 0 < n["prix_min_coherent"] <= n["prix_ouverture"]
    assert n["score_ouverture"] == simuler_prix(a, n["prix_ouverture"], config).score
    assert n["score_cible"] == simuler_prix(a, n["prix_plafond"], config).score
    base = deepcopy(a)
    base.taxe_fonciere_annuelle = n["taxe_annuelle_retenue"]
    for prix in [n["prix_plafond"], n["prix_ouverture"]]:
        s = simuler_prix(base, prix, config)
        assert est_pepite(s, config)
        assert analyser_decision(s, config)["cashflow_prudent"] >= n["objectif_cashflow"] == 100
    # Le cran supérieur échoue : il s'agit bien du plafond sur la grille.
    suivant = simuler_prix(base, n["prix_plafond"] + 1000, config)
    assert not est_pepite(suivant, config) or analyser_decision(suivant, config)["cashflow_prudent"] <= 0
    assert a.to_dict() == avant
    assert a.score < config.scoring["seuils"]["pepite"]


def test_une_taxe_inconnue_est_provisionnee_et_explicitement_signalee(config, benchmarks):
    a = candidat(config, benchmarks)
    inconnu = plan_negociation(a, config, MAINTENANT)
    assert inconnu["taxe_estimee"] and inconnu["taxe_annuelle_retenue"] == a.loyer_mensuel
    a.taxe_fonciere_annuelle = 0
    connu = plan_negociation(a, config, MAINTENANT)
    assert not connu["taxe_estimee"] and connu["taxe_annuelle_retenue"] == 0
    assert inconnu["prix_plafond"] <= connu["prix_plafond"]


@pytest.mark.parametrize("changements", [
    {"loyer_mensuel": None}, {"loyer_estime": True}, {"loyer_origine": "rendement"},
    {"surface_m2": None}, {"prix": None}, {"prix": float("nan")},
    {"etat_detail": "retiree"}, {"conflits_donnees": ["prix"]},
    {"date_derniere_vue": "2026-09-01T12:00:00+02:00"},
    {"description": "Vente de murs libres", "titre": "Local libre"},
    {"flags": ["dette_copropriete"]},
])
def test_pas_de_prix_magique_sur_un_dossier_non_qualifie(config, benchmarks, changements):
    a = candidat(config, benchmarks)
    for cle, valeur in changements.items():
        setattr(a, cle, valeur)
    n = plan_negociation(a, config, MAINTENANT)
    assert n["statut"] == "a_documenter"
    assert n["prix_plafond"] is None and not n["selection"]
    assert n["raisons"]
    assert message_negociation(a, n) == ""


def test_baisse_tres_importante_calculee_mais_non_promue(config, benchmarks):
    a = candidat(config, benchmarks, prix=400000)
    n = plan_negociation(a, config, MAINTENANT)
    assert n["prix_plafond"] and n["remise_pct"] > 25
    assert not n["selection"]


def test_bon_prix_calcule_sans_promouvoir_un_emplacement_a_risque(config, benchmarks):
    a = candidat(config, benchmarks, rue_categorie="tres_commercante", rue_nb_vacants=4)
    n = plan_negociation(a, config, MAINTENANT)
    assert n["prix_plafond"] is not None and n["cashflow_cible"] > 0
    assert n["relocation"]["niveau"] == "vigilance"
    assert not n["selection"]


def test_prix_deja_dans_la_cible_et_marge_bornee_par_les_controles(config, benchmarks):
    a = candidat(config, benchmarks, prix=168000)
    n = plan_negociation(a, config, MAINTENANT)
    assert n["statut"] == "deja_cible" and not n["selection"]
    assert n["prix_plafond"] == a.prix
    assert 0 < n["prix_ouverture"] <= n["prix_plafond"]
    assert est_pepite(simuler_prix(a, n["prix_ouverture"], config), config)


def test_prix_affiche_non_arrondi_est_teste_et_taux_zero_supporte(config, benchmarks):
    cfg = deepcopy(config)
    cfg.donnees["analyse"]["financement"]["taux_pct"] = 0
    a = candidat(cfg, benchmarks, prix=190123)
    n = plan_negociation(a, cfg, MAINTENANT)
    assert n["prix_plafond"] == a.prix
    assert n["hypotheses"]["taux_pct"] == 0


def test_la_baisse_ne_doit_pas_contourner_les_plafonds_anti_anomalies(config, benchmarks):
    a = candidat(config, benchmarks, ville="Pantin", code_postal="93500", departement="93",
                  surface_m2=40, prix=200000, loyer_mensuel=1400)
    n = plan_negociation(a, config, MAINTENANT)
    assert not n["selection"]  # le prix nécessaire demande trop de baisse
    assert n["prix_seuil_financier"] < a.prix
    assert n["cashflow_seuil_financier"] >= n["objectif_cashflow"]
    assert not n["selection"]
    trop_bas = simuler_prix(a, 50000, config)
    assert not est_pepite(trop_bas, config)
    assert "loyer_incoherent" in trop_bas.flags


def test_un_rendement_accru_par_le_prix_propose_ne_degrade_pas_une_donnee_saine(config, benchmarks):
    cfg = deepcopy(config)
    cfg.donnees["analyse"]["financement"]["taux_pct"] = 5.34
    a = candidat(cfg, benchmarks)
    avant = deepcopy(a.to_dict())
    n = plan_negociation(a, cfg, MAINTENANT)
    assert n["rendement_cible_pct"] > cfg.scoring["seuil_alerte_rendement_pct"]
    assert n["rendement_simule_eleve"]
    assert n["score_cible"] >= cfg.scoring["seuils"]["pepite"]
    assert n["cashflow_cible"] >= 100
    assert a.to_dict() == avant
    copie = simuler_prix(a, n["prix_plafond"], cfg)
    assert "rendement_anormalement_eleve" not in copie.flags
    # Le même rendement au prix réellement publié reste contrôlé normalement.
    scorer(copie, cfg)
    assert "rendement_anormalement_eleve" in copie.flags
    assert not est_pepite(copie, cfg)


def test_simulation_recalcule_la_decote_a_partir_de_la_mediane_exacte(config, benchmarks):
    a = candidat(config, benchmarks)
    a.marche_prix_m2_median = 9000
    a.marche_prix_m2_haut = 12000
    a.decote_pct = -99  # aucune déduction de médiane à partir de cette valeur
    s = simuler_prix(a, 180000, config)
    assert s.decote_pct == round((9000 - round(180000 / 35)) / 9000 * 100, 1)
    assert s.position_benchmark == "decote_forte"


def test_honoraires_separes_diminuent_le_prix_cible_et_la_tresorerie(config, benchmarks):
    a = candidat(config, benchmarks)
    sans = plan_negociation(a, config, MAINTENANT)
    prudent_sans = analyser_decision(a, config)
    a.honoraires = 12000
    avec = plan_negociation(a, config, MAINTENANT)
    assert avec["prix_plafond"] < sans["prix_plafond"]
    assert analyser_decision(a, config)["cashflow_prudent"] < prudent_sans["cashflow_prudent"]
    assert avec["cout_total"] == round(avec["prix_plafond"] * 1.08 + 12000)


def test_brouillon_chiffre_sans_affirmer_une_decote_de_marche(config, benchmarks):
    a = candidat(config, benchmarks)
    n = plan_negociation(a, config, MAINTENANT)
    message = message_negociation(a, n)
    montant = f'{n["prix_ouverture"]:,.0f}'.replace(",", " ")
    assert montant in message and a.url in message
    assert "HT/HC" in message and "honoraires" in message
    assert "seriez-vous ouverts" in message and "Avant de me positionner" in message
    assert "décote" not in message and "offre ferme" not in message
