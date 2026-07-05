"""Parsers Niveau 1, testés sur des fixtures HTML réelles anonymisées."""
from __future__ import annotations

import json
from pathlib import Path

from pipeline.modeles import TypeMurs
from sources.bienici import SourceBienici
from sources.cessionpme import SourceCessionPme
from sources.extraction import (
    deviner_type_murs,
    extraire_nombre,
    extraire_surface,
    loyer_mensuel_depuis_texte,
    rentabilite_depuis_texte,
)
from sources.geolocaux import SourceGeolocaux
from sources.hektor import SourceFlagship, SourceIburoshop
from sources.murscommerciaux import SourceMursCommerciaux
from sources.papcommerces import SourcePapCommerces
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
    assert extraire_nombre("515.000 €") == 515_000      # milliers à point (PAP)
    assert extraire_nombre("1.250.000 €") == 1_250_000
    assert extraire_nombre("2333.83") == 2_333.83       # décimale à point conservée
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


def test_loyer_generique_vendu_loue():
    # « Vendu loué : 2 087 € » sans précision = mensuel (rendement plausible)
    assert loyer_mensuel_depuis_texte("**Vendu loué : 2087€** belle boutique", 415_000) == 2_087
    # Un « loyer : 24 000 € » qui donnerait 96 %/an est réinterprété comme annuel
    assert loyer_mensuel_depuis_texte("loyer : 24 000 €", 300_000) == 2_000
    # Mention explicite « /an »
    assert loyer_mensuel_depuis_texte("loyer 18 000 € /an", 230_000) == 1_500


def test_deviner_type_murs():
    assert deviner_type_murs("local vendu occupé, bail 3/6/9") is TypeMurs.MURS_OCCUPES
    assert deviner_type_murs("vendus libres de toute occupation") is TypeMurs.MURS_LIBRES
    assert deviner_type_murs("local vide, vitrine d'angle") is TypeMurs.MURS_LIBRES
    assert deviner_type_murs("bail en cours, loyer 1 200 €") is TypeMurs.MURS_OCCUPES


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


# --- papcommerces.fr ---


class TestPapCommerces:
    def test_extraction(self):
        annonces = SourcePapCommerces().extraire(charger("papcommerces_liste.html"))
        assert len(annonces) == 2

        paris = next(a for a in annonces if a.id_source == "900100001")
        assert paris.prix == 415_000                    # « 415.000 € »
        assert paris.surface_m2 == 20
        assert paris.code_postal == "75005"             # déduit de « Paris 5E »
        assert paris.type_murs is TypeMurs.MURS_OCCUPES  # « Vendu loué »
        assert paris.loyer_mensuel == 2_087
        assert paris.image_url and "cdn.pap.fr" in paris.image_url
        # Titre de la source, sans préfixe injecté (sinon le contrôle
        # suspect_fonds serait neutralisé)
        assert paris.titre == "Local commercial Paris 5E"

    def test_carte_sans_photo_et_cp_dans_url(self):
        annonces = SourcePapCommerces().extraire(charger("papcommerces_liste.html"))
        montreuil = next(a for a in annonces if a.id_source == "900100002")
        assert montreuil.code_postal == "93100"          # depuis l'URL
        assert montreuil.type_murs is TypeMurs.MURS_LIBRES  # « local vide »
        assert montreuil.image_url is None               # visuel-nophoto ignoré
        assert montreuil.prix == 260_000


# --- cessionpme.com ---


class TestCessionPme:
    def test_extraction(self):
        annonces = SourceCessionPme().extraire(charger("cessionpme_liste.html"))
        assert len(annonces) == 2

        paris = next(a for a in annonces if a.id_source == "9900001")
        assert paris.ville == "Paris 11e"
        assert paris.code_postal == "75011"                 # arrondissement -> CP
        assert paris.prix == 257_000
        assert paris.surface_m2 == 38
        assert paris.type_murs is TypeMurs.MURS_OCCUPES     # « vendus loués »
        assert paris.loyer_mensuel == 1_080                 # « 1 080 Euro TTC / mois »
        assert paris.titre == "Murs de boutique loués secteur Saint-Ambroise"

    def test_cp_depuis_description(self):
        annonces = SourceCessionPme().extraire(charger("cessionpme_liste.html"))
        montreuil = next(a for a in annonces if a.id_source == "9900002")
        assert montreuil.code_postal == "93100"             # depuis « (93100) »
        assert montreuil.type_murs is TypeMurs.MURS_LIBRES  # « local vide »
        assert montreuil.prix == 198_000


# --- geolocaux.com ---


class TestGeolocaux:
    def test_extraction(self):
        annonces = SourceGeolocaux().extraire(charger("geolocaux_liste.html"), "75")
        assert len(annonces) == 2

        paris = next(a for a in annonces if a.id_source == "717001")
        assert paris.ville == "Paris 5e"
        assert paris.code_postal == "75005"
        assert paris.prix == 420_000
        assert paris.surface_m2 == 55
        assert paris.images and "900000001_1.jpg" in paris.images[0]
        assert "Voir l'annonce" not in paris.description

    def test_loyer_annuel_et_photo_par_defaut_ignoree(self):
        annonces = SourceGeolocaux().extraire(charger("geolocaux_liste.html"), "93")
        montreuil = next(a for a in annonces if a.id_source == "717002")
        assert montreuil.ville == "Montreuil"
        assert montreuil.code_postal == "93000"          # CP départemental approx.
        assert montreuil.type_murs is TypeMurs.MURS_OCCUPES  # « vendus loués »
        assert montreuil.loyer_mensuel == 1_200          # 14 400 € annuels / 12
        assert montreuil.images == []                    # photo par défaut ignorée

    def test_arrondissement_avec_suffixe(self):
        # relevé live du 2026-07-05 : le site écrit aussi « Paris 17e », « Paris 1er »
        source = SourceGeolocaux()
        assert source._localiser("Vente local commercial Paris 17e - Épinettes", "75") == (
            "Paris 17e", "75017")
        assert source._localiser("Vente boutique Paris 1er - Les Halles", "75") == (
            "Paris 1er", "75001")
        assert source._localiser("Vente murs Paris 5ème", "75") == ("Paris 5e", "75005")


# --- bienici.com (API JSON) ---


class TestBienici:
    def test_conversion(self):
        donnees = json.loads(charger("bienici_annonces.json"))
        annonces = SourceBienici().convertir(donnees)
        # La cession de fonds (adType businessTakeOver) est écartée à la source
        assert len(annonces) == 2

        occ = next(a for a in annonces if a.id_source == "agence-exemple-123456")
        assert occ.type_murs is TypeMurs.MURS_OCCUPES
        assert occ.code_postal == "93300"
        assert occ.prix == 230_000
        assert occ.loyer_mensuel == 1_500               # loyer annuel 18 000 € / 12
        assert occ.image_url == "https://media.exemple.fr/photos/123456a.jpg"
        assert occ.url == "https://www.bienici.com/annonce/agence-exemple-123456"

    def test_photo_cle_alternative_et_type_libre(self):
        donnees = json.loads(charger("bienici_annonces.json"))
        annonces = SourceBienici().convertir(donnees)
        libre = next(a for a in annonces if a.id_source == "agence-exemple-888888")
        assert libre.type_murs is TypeMurs.MURS_LIBRES
        assert libre.image_url == "https://media.exemple.fr/photos/888888a.jpg"
