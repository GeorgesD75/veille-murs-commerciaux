"""bureauxlocaux.com — JSON react-context, is_occupied/is_sale_of_business_assets."""
from __future__ import annotations

from pathlib import Path

from pipeline.modeles import TypeMurs
from sources.bureauxlocaux import SourceBureauxLocaux

FIXTURES = Path(__file__).parent / "fixtures"


def _charger(nom: str) -> str:
    return (FIXTURES / nom).read_text(encoding="utf-8")


class ClientFactice:
    """Sert les pages fixture par URL, et compte les appels (test de pagination)."""

    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages
        self.urls: list[str] = []

    def obtenir(self, url: str) -> str:
        self.urls.append(url)
        return self.pages[url]


class TestExtractionItem:
    def _annonces_page1(self):
        source = SourceBureauxLocaux(client=ClientFactice({
            SourceBureauxLocaux.BASE
            + "/immobilier-d-entreprise/annonces/seine-saint-denis-93/vente-commerces":
                _charger("bureauxlocaux_page1.html"),
        }), departements=["93"], max_pages=1)
        return source.collecter()

    def test_murs_occupes_champ_structure(self):
        annonces = self._annonces_page1()
        pantin = next(a for a in annonces if a.id_source == "900001")
        assert pantin.type_murs is TypeMurs.MURS_OCCUPES
        assert pantin.ville == "Pantin"
        assert pantin.code_postal == "93500"
        assert pantin.prix == 280_000.0
        assert pantin.surface_m2 == 72.0
        assert pantin.loyer_mensuel == 1_400.0  # 16 800 € annuels / 12
        assert "Voir l'annonce" not in pantin.description
        assert "<br>" not in pantin.description

    def test_murs_libres_et_caracteristiques_traduites_en_texte(self):
        annonces = self._annonces_page1()
        ivry = next(a for a in annonces if a.id_source == "900002")
        assert ivry.type_murs is TypeMurs.MURS_LIBRES
        assert "Extraction possible" in ivry.description
        assert "Emplacement en angle de rue" in ivry.description
        assert ivry.images == []
        assert ivry.image_url is None

    def test_fonds_de_commerce_signale_fiablement_dans_la_description(self):
        source = SourceBureauxLocaux(client=ClientFactice({
            SourceBureauxLocaux.BASE
            + "/immobilier-d-entreprise/annonces/seine-saint-denis-93/vente-commerces":
                _charger("bureauxlocaux_page2.html"),
        }), departements=["93"], max_pages=1)
        annonces = source.collecter()
        fantome = next(a for a in annonces if a.id_source == "900003")
        assert "Cession de fonds de commerce" in fantome.description
        # is_occupied absent (null) : repli sur l'heuristique textuelle habituelle
        assert fantome.type_murs is TypeMurs.MURS_LIBRES

    def test_contradiction_titre_libre_description_occupee_est_signalee(self):
        """Cas réel constaté (annonce « Brochant ») : la case structurée dit
        « libres » mais le texte de la description dit « occupés ». Le champ
        structuré fait foi pour le score, mais l'incohérence doit apparaître
        en clair dans la description pour que l'acheteur vérifie."""
        source = SourceBureauxLocaux(client=ClientFactice({
            SourceBureauxLocaux.BASE
            + "/immobilier-d-entreprise/annonces/seine-saint-denis-93/vente-commerces":
                _charger("bureauxlocaux_page2.html"),
        }), departements=["93"], max_pages=1)
        annonces = source.collecter()
        brochant = next(a for a in annonces if a.id_source == "900004")
        assert brochant.type_murs is TypeMurs.MURS_LIBRES
        assert "⚠" in brochant.description
        assert "contradictoire" in brochant.description
        assert "murs libres" in brochant.description
        assert "murs occupés" in brochant.description


class TestPagination:
    def test_suit_la_pagination_jusqu_au_total_pages(self):
        base = SourceBureauxLocaux.BASE + "/immobilier-d-entreprise/annonces/seine-saint-denis-93/vente-commerces"
        client = ClientFactice({
            base: _charger("bureauxlocaux_page1.html"),
            base + "/page/2": _charger("bureauxlocaux_page2.html"),
        })
        source = SourceBureauxLocaux(client=client, departements=["93"], max_pages=5)
        annonces = source.collecter()
        assert {a.id_source for a in annonces} == {"900001", "900002", "900003", "900004"}
        # total_pages=2 lu sur la page 1 : pas de 3e requête malgré max_pages=5
        assert len(client.urls) == 2

    def test_max_pages_plafonne_avant_le_total_reel(self):
        base = SourceBureauxLocaux.BASE + "/immobilier-d-entreprise/annonces/seine-saint-denis-93/vente-commerces"
        client = ClientFactice({base: _charger("bureauxlocaux_page1.html")})
        source = SourceBureauxLocaux(client=client, departements=["93"], max_pages=1)
        annonces = source.collecter()
        assert {a.id_source for a in annonces} == {"900001", "900002"}
        assert len(client.urls) == 1
