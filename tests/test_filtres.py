"""Filtres d'exclusion : détection fonds de commerce, budget, géographie, cohérence prix."""
from __future__ import annotations

from pipeline.filtres import raison_exclusion
from tests.fabriques import faire_annonce

# --- Détection fonds de commerce / droit au bail (piège n°1) ---


def test_fonds_de_commerce_toujours_exclu(config, trajets):
    a = faire_annonce(titre="Fonds de commerce restaurant", description="Belle affaire.")
    raison = raison_exclusion(a, config, trajets)
    assert raison is not None and "fonds de commerce" in raison


def test_fonds_de_commerce_exclu_meme_avec_murs(config, trajets):
    a = faire_annonce(description="Vente du fonds de commerce, murs non compris.")
    assert raison_exclusion(a, config, trajets) is not None


def test_fond_de_commerce_sans_s_exclu_aussi(config, trajets):
    """Faute courante dans les annonces réelles (vue sur une annonce notariale) :
    « fond de commerce » sans « s » doit tomber dans le même piège n°1."""
    a = faire_annonce(titre="A saisir", description="Fond de commerce de pharmacie en zone commerciale.")
    assert raison_exclusion(a, config, trajets) is not None
    a2 = faire_annonce(titre="A saisir", description="Cession de fond suite retraite.")
    assert raison_exclusion(a2, config, trajets) is not None


def test_droit_au_bail_exclu(config, trajets):
    a = faire_annonce(titre="Droit au bail boutique", description="Emplacement n°1.")
    raison = raison_exclusion(a, config, trajets)
    assert raison is not None and "droit au bail" in raison


def test_pas_de_porte_sans_murs_exclu(config, trajets):
    a = faire_annonce(titre="Pas de porte à céder", description="Local commercial.")
    assert raison_exclusion(a, config, trajets) is not None


def test_pas_de_porte_avec_murs_conserve(config, trajets):
    a = faire_annonce(
        titre="Vente des murs", description="Pas de porte également disponible, murs loués."
    )
    assert raison_exclusion(a, config, trajets) is None


def test_cause_retraite_sans_murs_exclu(config, trajets):
    a = faire_annonce(titre="Vente cause retraite", description="Local commercial loué.")
    assert raison_exclusion(a, config, trajets) is not None


def test_cause_retraite_avec_murs_conserve(config, trajets):
    a = faire_annonce(titre="Vente des murs cause retraite", description="Locataire en place.")
    assert raison_exclusion(a, config, trajets) is None


# --- Budget ---


def test_prix_trop_bas_exclu(config, trajets):
    a = faire_annonce(prix=100_000.0)
    raison = raison_exclusion(a, config, trajets)
    assert raison is not None and "prix" in raison


def test_prix_trop_haut_exclu(config, trajets):
    a = faire_annonce(prix=500_000.0)
    assert raison_exclusion(a, config, trajets) is not None


def test_prix_borne_basse_conserve(config, trajets):
    # 140 000 € / 100 m² = 1 400 €/m² : sous le plancher petite couronne, mais la
    # description mentionne explicitement les murs -> conservé.
    a = faire_annonce(prix=140_000.0)
    assert raison_exclusion(a, config, trajets) is None


def test_prix_manquant_exclu(config, trajets):
    a = faire_annonce(prix=None)
    assert raison_exclusion(a, config, trajets) == "prix non renseigné"


# --- Géographie ---


def test_hors_ile_de_france_exclu(config, trajets):
    a = faire_annonce(ville="Orléans", code_postal="45000", departement="45")
    raison = raison_exclusion(a, config, trajets)
    assert raison is not None and "Île-de-France" in raison


def test_trajet_trop_long_exclu(config, trajets):
    a = faire_annonce(ville="Provins", code_postal="77160", departement="77")
    raison = raison_exclusion(a, config, trajets)
    assert raison is not None and "loin" in raison


def test_temps_trajet_renseigne_pour_le_scoring(config, trajets):
    a = faire_annonce()  # Pantin
    raison_exclusion(a, config, trajets)
    assert a.temps_trajet_min == 15


# --- Cohérence prix/m² (fonds déguisé) ---


def test_prix_m2_incoherent_sans_murs_exclu(config, trajets):
    a = faire_annonce(
        titre="Local commercial occupé",
        description="Local loué, très bon emplacement.",
        prix=150_000.0,
        surface_m2=120.0,  # 1 250 €/m² en petite couronne
    )
    raison = raison_exclusion(a, config, trajets)
    assert raison is not None and "suspect_fonds" in raison


def test_prix_m2_incoherent_avec_murs_conserve(config, trajets):
    a = faire_annonce(prix=150_000.0, surface_m2=120.0)  # description mentionne les murs
    assert raison_exclusion(a, config, trajets) is None


def test_plancher_paris_plus_strict(config, trajets):
    # 1 550 €/m² dans Paris sans mention des murs : cession de bail probable.
    a = faire_annonce(
        titre="Vente Local commercial 103m² Paris",
        description="Local commercial, loyer : 2 700 €. Emplacement n°1.",
        ville="Paris 10e", code_postal="75010", departement="75",
        prix=160_000.0, surface_m2=103.0,
    )
    raison = raison_exclusion(a, config, trajets)
    assert raison is not None and "suspect_fonds" in raison


def test_plancher_grande_couronne_moins_strict(config, trajets):
    # 937 €/m² à Cergy : au-dessus du plancher grande couronne (800 €/m²) -> conservé.
    a = faire_annonce(
        titre="Local commercial occupé",
        description="Local loué proche gare.",
        ville="Cergy",
        code_postal="95000",
        departement="95",
        prix=150_000.0,
        surface_m2=160.0,
    )
    assert raison_exclusion(a, config, trajets) is None
