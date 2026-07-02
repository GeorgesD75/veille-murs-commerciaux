"""Dédoublonnage : identifiant stable, similarité cross-sources, fusion."""
from __future__ import annotations

from pipeline.dedoublonnage import fusionner, sont_similaires, trouver_similaire
from pipeline.modeles import identifiant
from tests.fabriques import faire_annonce


def test_identifiant_stable_et_discriminant():
    assert identifiant("pointdevente", "123") == identifiant("pointdevente", "123")
    assert identifiant("pointdevente", "123") != identifiant("pointdevente", "124")
    assert identifiant("pointdevente", "123") != identifiant("seloger", "123")


def test_similaires_dans_les_tolerances(config):
    a = faire_annonce()  # 250 000 €, 100 m², 93500
    b = faire_annonce(id="autre", source="test2", prix=255_000.0, surface_m2=102.0)
    assert sont_similaires(a, b, config)


def test_surface_trop_differente(config):
    b = faire_annonce(id="autre", source="test2", surface_m2=105.0)  # +5 m² > ±3
    assert not sont_similaires(faire_annonce(), b, config)


def test_prix_trop_different(config):
    b = faire_annonce(id="autre", source="test2", prix=280_000.0)  # +12 % > ±5 %
    assert not sont_similaires(faire_annonce(), b, config)


def test_code_postal_different(config):
    b = faire_annonce(id="autre", source="test2", code_postal="93100")
    assert not sont_similaires(faire_annonce(), b, config)


def test_trouver_similaire_cross_sources(config):
    existante = faire_annonce()
    candidate = faire_annonce(id="autre", source="test2", prix=252_000.0, surface_m2=99.0)
    assert trouver_similaire(candidate, [existante], config) is existante


def test_trouver_similaire_ignore_la_meme_source(config):
    # Même source : deux biens proches peuvent légitimement coexister.
    existante = faire_annonce()
    candidate = faire_annonce(id="autre", source="test", prix=252_000.0)
    assert trouver_similaire(candidate, [existante], config) is None


def test_fusion_conserve_une_fiche_et_les_liens(config):
    principale = faire_annonce(image_url=None, loyer_mensuel=None)
    doublon = faire_annonce(
        id="autre",
        source="test2",
        url="https://autre-portail.fr/2",
        loyer_mensuel=1_650.0,
        image_url="https://autre-portail.fr/img/2.jpg",
        date_premiere_vue="2026-06-28T07:00:00+02:00",
    )
    fusionner(principale, doublon)
    assert principale.urls_multiples == ["https://autre-portail.fr/2"]
    assert principale.loyer_mensuel == 1_650.0  # trou comblé par le doublon
    assert principale.image_url == "https://autre-portail.fr/img/2.jpg"
    assert principale.date_premiere_vue == "2026-06-28T07:00:00+02:00"  # la plus ancienne
