"""Fabriques d'objets de test."""
from __future__ import annotations

from pipeline.modeles import Annonce, TypeMurs


def faire_annonce(**surcharges) -> Annonce:
    """Annonce valide par défaut (murs occupés à Pantin) ; surcharger au besoin."""
    base: dict = dict(
        id="abc123",
        id_source="1",
        source="test",
        url="https://exemple.fr/1",
        titre="Murs de boutique occupés",
        ville="Pantin",
        code_postal="93500",
        departement="93",
        type_murs=TypeMurs.MURS_OCCUPES,
        prix=250_000.0,
        surface_m2=100.0,
        loyer_mensuel=1_700.0,
        honoraires=None,
        image_url=None,
        description="Murs commerciaux loués, bail 3/6/9 en cours.",
        date_premiere_vue="2026-07-01T07:00:00+02:00",
        date_derniere_vue="2026-07-01T07:00:00+02:00",
    )
    base.update(surcharges)
    return Annonce(**base)
