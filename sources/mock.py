"""Source de démonstration (Phase 1) : simule deux portails pour exercer tout le pipeline.

Cas couverts : bon dossier, pépite (score ≥ 80), surcote parisienne, fonds de commerce,
droit au bail, prix hors budget, murs libres, suspect_fonds (prix/m² incohérent),
doublon cross-sources, trajet > 1h, hors Île-de-France.
"""
from __future__ import annotations

from pipeline.modeles import AnnonceBrute, TypeMurs
from sources.base import Source

_ANNONCES: list[dict] = [
    # --- Cas nominal : bon rendement à Pantin (attendu ~73, orange) ---
    dict(
        id_source="pdv-1001", source="mock_portail_a",
        url="https://portail-a.exemple/annonces/1001",
        titre="Murs de boutique occupés – Pantin centre",
        ville="Pantin", code_postal="93500", type_murs=TypeMurs.MURS_OCCUPES,
        prix=250_000, surface_m2=110, loyer_mensuel=1_700,
        image_url="https://portail-a.exemple/img/1001.jpg",
        description="Murs de boutique loués, bail commercial 3/6/9 en cours, rue passante.",
    ),
    # --- Pépite attendue (score ≥ 80) : Saint-Ouen, rendement ~9,5 % ---
    dict(
        id_source="pdv-1002", source="mock_portail_a",
        url="https://portail-a.exemple/annonces/1002",
        titre="Murs occupés Saint-Ouen – rendement 9,5 %",
        ville="Saint-Ouen", code_postal="93400", type_murs=TypeMurs.MURS_OCCUPES,
        prix=152_000, surface_m2=80, loyer_mensuel=1_200,
        image_url="https://portail-a.exemple/img/1002.jpg",
        description=(
            "Vente des murs occupés. Bail récent (2024), taxe foncière à la charge du "
            "locataire, enseigne nationale en place."
        ),
    ),
    # --- Paris 18e : bon emplacement mais surcote (attendu ~56, gris) ---
    dict(
        id_source="pdv-1003", source="mock_portail_a",
        url="https://portail-a.exemple/annonces/1003",
        titre="Murs de boutique occupés – Paris 18e, rue de la Chapelle",
        ville="Paris 18e", code_postal="75018", type_murs=TypeMurs.MURS_OCCUPES,
        prix=380_000, surface_m2=40, loyer_mensuel=2_100,
        image_url="https://portail-a.exemple/img/1003.jpg",
        description="Murs commerciaux loués, locataire en place depuis 2019.",
    ),
    # --- Piège : fonds de commerce (exclu par mot-clé) ---
    dict(
        id_source="pdv-1004", source="mock_portail_a",
        url="https://portail-a.exemple/annonces/1004",
        titre="Fonds de commerce restaurant – Paris 11e",
        ville="Paris 11e", code_postal="75011", type_murs=TypeMurs.MURS_OCCUPES,
        prix=200_000, surface_m2=80, loyer_mensuel=None,
        description="Cession cause retraite, licence IV, matériel inclus.",
    ),
    # --- Piège : droit au bail (exclu par mot-clé) ---
    dict(
        id_source="pdv-1005", source="mock_portail_a",
        url="https://portail-a.exemple/annonces/1005",
        titre="Droit au bail – boutique Paris 4e",
        ville="Paris 4e", code_postal="75004", type_murs=TypeMurs.MURS_LIBRES,
        prix=180_000, surface_m2=35, loyer_mensuel=None,
        description="Cession du droit au bail, emplacement n°1, loyer 2 800 €/mois.",
    ),
    # --- Prix hors budget ---
    dict(
        id_source="pdv-1006", source="mock_portail_a",
        url="https://portail-a.exemple/annonces/1006",
        titre="Murs commerciaux occupés – Paris 17e",
        ville="Paris 17e", code_postal="75017", type_murs=TypeMurs.MURS_OCCUPES,
        prix=850_000, surface_m2=90, loyer_mensuel=3_500,
        description="Murs loués, emplacement premium.",
    ),
    # --- Murs libres en grande couronne (comparaison, loyer estimé) ---
    dict(
        id_source="pdv-1007", source="mock_portail_a",
        url="https://portail-a.exemple/annonces/1007",
        titre="Murs libres – local commercial Argenteuil",
        ville="Argenteuil", code_postal="95100", type_murs=TypeMurs.MURS_LIBRES,
        prix=160_000, surface_m2=60, loyer_mensuel=None,
        description="Local commercial libre en plein centre-ville d'Argenteuil, proche gare.",
    ),
    # --- Suspect : prix/m² incohérent sans mention des murs (fonds déguisé probable) ---
    dict(
        id_source="pdv-1008", source="mock_portail_a",
        url="https://portail-a.exemple/annonces/1008",
        titre="Local commercial occupé – Montreuil",
        ville="Montreuil", code_postal="93100", type_murs=TypeMurs.MURS_OCCUPES,
        prix=150_000, surface_m2=120, loyer_mensuel=1_100,
        description="Local loué, très bon emplacement, idéal investisseur.",
    ),
    # --- Doublon cross-sources de la pépite 1002 (fusion attendue) ---
    dict(
        id_source="b-2001", source="mock_portail_b",
        url="https://portail-b.exemple/biens/2001",
        titre="Local commercial loué Saint-Ouen (murs)",
        ville="Saint-Ouen-sur-Seine", code_postal="93400", type_murs=TypeMurs.MURS_OCCUPES,
        prix=155_000, surface_m2=81, loyer_mensuel=1_200,
        description="Murs de boutique avec locataire en place.",
    ),
    # --- Trop loin : Provins (~95 min) ---
    dict(
        id_source="b-2002", source="mock_portail_b",
        url="https://portail-b.exemple/biens/2002",
        titre="Murs commerciaux occupés – Provins",
        ville="Provins", code_postal="77160", type_murs=TypeMurs.MURS_OCCUPES,
        prix=155_000, surface_m2=70, loyer_mensuel=800,
        description="Murs loués en centre historique.",
    ),
    # --- Hors Île-de-France : Orléans ---
    dict(
        id_source="b-2003", source="mock_portail_b",
        url="https://portail-b.exemple/biens/2003",
        titre="Murs commerciaux occupés – Orléans centre",
        ville="Orléans", code_postal="45000", type_murs=TypeMurs.MURS_OCCUPES,
        prix=200_000, surface_m2=85, loyer_mensuel=1_400,
        description="Murs loués, hypercentre d'Orléans.",
    ),
    # --- Vincennes : correct mais cher au m² (attendu ~38, gris) ---
    dict(
        id_source="b-2004", source="mock_portail_b",
        url="https://portail-b.exemple/biens/2004",
        titre="Murs occupés – Vincennes cœur de ville",
        ville="Vincennes", code_postal="94300", type_murs=TypeMurs.MURS_OCCUPES,
        prix=350_000, surface_m2=55, loyer_mensuel=1_800,
        image_url="https://portail-b.exemple/img/2004.jpg",
        description="Murs commerciaux loués, pied d'immeuble haussmannien.",
    ),
]


class SourceMock(Source):
    nom = "mock"

    def collecter(self) -> list[AnnonceBrute]:
        return [AnnonceBrute(**d) for d in _ANNONCES]
