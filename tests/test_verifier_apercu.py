"""Le script exige un vrai navigateur headless — hors de portée d'un test
rapide. Seule la logique pure (comparaison de couleurs) est testée ici ;
le comportement bout en bout est vérifié à la main avant chaque changement
de mise en page (cf. historique de commits sur scripts/verifier_apercu.py)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from verifier_apercu import _distance  # noqa: E402


def test_distance_couleurs_identiques():
    assert _distance((20, 58, 45), (20, 58, 45)) == 0


def test_distance_couleurs_proches_sous_le_seuil():
    # Un léger bruit d'anti-aliasing ne doit pas déclencher une fausse alerte
    assert _distance((20, 58, 45), (22, 57, 46)) < 20


def test_distance_couleurs_tres_differentes():
    # Vert du bandeau vs fond de page blanc cassé : nettement au-dessus du seuil
    assert _distance((20, 58, 45), (246, 246, 241)) >= 20
