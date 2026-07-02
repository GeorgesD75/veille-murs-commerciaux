"""Parsers Niveau 1, testés sur des fixtures HTML réelles anonymisées."""
from __future__ import annotations

from pathlib import Path

from pipeline.modeles import TypeMurs
from sources.extraction import (
    extraire_nombre,
    extraire_surface,
    loyer_mensuel_depuis_texte,
    rentabilite_depuis_texte,
)
from sources.hektor import SourceFlagship, SourceIburoshop
from sources.murscommerciaux import SourceMursCommerciaux
from sources.pointdevente import SourcePointDeVente

FIXTURES = Path(__file__).parent / "fixtures"


def charger(nom: str) -> str:
    return (FIXTURES / nom).read_text(encoding="utf-8")


# --- Extracteurs partagés ---


def test_extraire_nombre():
    assert extraire_nombre("360 000 € Net vendeur") == 360_000
    assert extraire_nombre("Loyer : 2 334 € Hc/ht/mois") == 2_334
    assert extraire_nombre("8.7%") == 8.7
    assert extraire_nombre("2 333,83 €") == 2_333.83
    assert extraire_nombre("aucun chiffre") is None
    assert extraire_nombre(None) is None


def test_extraire_surface():
    assert extraire_surface("Vente Commerce Paris 18 75018 43 m²") == 43
    assert extraire_surface("local d'environ 147m² occupé") == 147
    assert extraire_surface("aucune") is None


def test_loyer_annuel_depuis_description():
    texte = "Bail 3 6 9. Loyer annuel : 43 470 € HT HC payable mensuellement."
    assert loyer_mensuel_depuis_texte(texte, 500_000) == 3_622.5
    # Loyer annuel >= prix : donnée aberrante, ignorée
    assert loyer_mensuel_depuis_texte(texte, 40_000) is None


def test_rentabilite_depuis_description():
    assert rentabilite_depuis_texte("bonne clientèle rentabilité (avant révision )7% la") == 7.0
    assert rentabilite_depuis_texte("rentabilité : 8,5 % nette") == 8.5
    assert rentabilite_depuis_texte("rentabilité de 45%") is None  # hors plage plausible
    assert rentabilite_depuis_texte("rien") is None


# --- pointdevente.fr ---


class TestPointDeVente:
    def test_extraction(self):
        annonces = SourcePointDeVente().extraire(charger("pointdevente_liste.html"))
        # 4 cartes : le fonds de commerce est ignoré, le doublon mobile/bureau fusionné
        assert len(annonces) == 2

        occupes = next(a for a in annonces if a.type_murs is TypeMurs.MURS_OCCUPES)
        assert occupes.id_source == "900001"
        assert occupes.ville == "Pantin"
        assert occupes.code_postal == "93500"
        assert occupes.prix == 280_000
        assert occupes.surface_m2 == 95
        assert occupes.loyer_mensuel == 1_900
        assert "murs" in occupes.titre.lower()
        assert occupes.image_url and "/doc/pdv/" in occupes.image_url

    def test_carte_paris_sans_code_postal_dans_le_code(self):
        annonces = SourcePointDeVente().extraire(charger("pointdevente_liste.html"))
        libres = next(a for a in annonces if a.type_murs is TypeMurs.MURS_LIBRES)
        assert libres.ville == "Paris 18e"          # depuis <div class="code">
        assert libres.code_postal == "75018"        # depuis l'URL de photo
        assert libres.prix == 310_000
        assert libres.loyer_mensuel is None
        assert libres.image_url is None             # picto générique ignoré

    def test_urls_pagination(self):
        source = SourcePointDeVente(max_pages=3)
        pages = [
            source.LISTE if n == 0 else f"{source.LISTE}/50/{n}/1"
            for n in range(source.max_pages)
        ]
        assert pages == [
            "/fr/acheter-murs-commerciaux-paris/lf393",
            "/fr/acheter-murs-commerciaux-paris/lf393/50/1/1",
            "/fr/acheter-murs-commerciaux-paris/lf393/50/2/1",
        ]


# --- murscommerciaux.com ---


class TestMursCommerciaux:
    def test_extraction(self):
        annonces = SourceMursCommerciaux().extraire(
            charger("murscommerciaux_occupes.html"), TypeMurs.MURS_OCCUPES
        )
        assert len(annonces) == 2

        paris = next(a for a in annonces if a.id_source == "8001")
        assert paris.ville == "Paris"
        assert paris.code_postal == "75000"        # CP synthétisé depuis « (75) »
        assert paris.prix == 320_000
        assert paris.surface_m2 == 45
        assert paris.loyer_mensuel == 2_000        # loyer annuel 24 000 € / 12
        assert paris.type_murs is TypeMurs.MURS_OCCUPES

    def test_loyer_deduit_de_la_rentabilite(self):
        annonces = SourceMursCommerciaux().extraire(
            charger("murscommerciaux_occupes.html"), TypeMurs.MURS_OCCUPES
        )
        levallois = next(a for a in annonces if a.id_source == "8002")
        assert levallois.ville == "Levallois-Perret"
        assert levallois.code_postal == "92000"
        # Pas de loyer en description : déduit de la rentabilité 8 % affichée
        assert levallois.loyer_mensuel == round(250_000 * 0.08 / 12, 2)


# --- iburoshop.fr / flagship.fr (plateforme commune) ---


class TestHektor:
    def test_extraction_avec_type_impose(self):
        annonces = SourceIburoshop().extraire(
            charger("hektor_vente.html"), TypeMurs.MURS_OCCUPES
        )
        # La carte « location » est ignorée
        assert len(annonces) == 2
        occ = next(a for a in annonces if a.id_source == "uh1-9001")
        assert occ.code_postal == "75018"          # depuis l'URL du bien
        assert occ.ville == "Paris"
        assert occ.prix == 215_000
        assert occ.surface_m2 == 43                # depuis l'attribut alt de la photo
        # Rentabilité 7 % en description -> loyer déduit
        assert occ.loyer_mensuel == round(215_000 * 0.07 / 12, 2)
        assert occ.url.startswith("https://www.iburoshop.fr/")

    def test_type_devine_sur_page_mixte(self):
        annonces = SourceFlagship().extraire(charger("hektor_vente.html"), None)
        occ = next(a for a in annonces if a.id_source == "uh1-9001")
        libre = next(a for a in annonces if a.id_source == "lr1-9003")
        assert occ.type_murs is TypeMurs.MURS_OCCUPES      # « vendu occupé »
        assert libre.type_murs is TypeMurs.MURS_LIBRES     # « vendus libres de toute occupation »
        assert libre.surface_m2 == 38                      # depuis la description
        assert "murs" in libre.titre.lower()
