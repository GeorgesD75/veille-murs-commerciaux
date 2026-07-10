"""immobilier.notaires.fr — API JSON publique : filtres transaction/IdF/vendu."""
from __future__ import annotations

from pathlib import Path

from pipeline.modeles import TypeMurs
from sources.notaires import SourceNotaires

FIXTURES = Path(__file__).parent / "fixtures"


class ClientFactice:
    def __init__(self, reponses: dict[str, str]) -> None:
        self.reponses = reponses
        self.urls: list[str] = []

    def obtenir(self, url: str) -> str:
        self.urls.append(url)
        return self.reponses[url]


def _source(max_pages: int = 5) -> tuple[SourceNotaires, ClientFactice]:
    url = (SourceNotaires.BASE + SourceNotaires.API
           + "?typeBiens=COM&page=1&parPage=100")
    client = ClientFactice({url: (FIXTURES / "notaires_page1.json").read_text(encoding="utf-8")})
    return SourceNotaires(client=client, max_pages=max_pages), client


def test_seules_les_ventes_idf_non_vendues_sont_retenues():
    source, client = _source()
    annonces = source.collecter()
    # 5 annonces au total : la LOCATION, la vente hors IdF et le bien déjà
    # vendu (bienVendu=OUI) sont écartés — restent Paris 18e et Conflans.
    assert {a.id_source for a in annonces} == {"2034001", "2034005"}
    assert len(client.urls) == 1  # nbPages=1 : pas de requête superflue


def test_champs_annonce_paris():
    source, _ = _source()
    paris = next(a for a in source.collecter() if a.id_source == "2034001")
    assert paris.ville == "Paris 18e Arrondissement"
    assert paris.code_postal == "75018"
    assert paris.prix == 380_000.0
    assert paris.surface_m2 == 42.0                 # extraite de la description
    assert paris.loyer_mensuel == 1_800.0           # 21 600 € annuels / 12
    assert paris.type_murs is TypeMurs.MURS_OCCUPES  # « loués » dans le texte
    assert "notaire" in paris.titre
    assert paris.url.endswith("/2034001")


def test_vni_libre_de_toute_occupation():
    source, _ = _source()
    conflans = next(a for a in source.collecter() if a.id_source == "2034005")
    assert conflans.type_murs is TypeMurs.MURS_LIBRES
    assert conflans.surface_m2 == 58.0
