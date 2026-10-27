"""Le moteur local est testé directement en JavaScript, sans serveur."""
from pathlib import Path
import shutil
import subprocess

import pytest

from pipeline.contact import messages_contact
from tests.fabriques import faire_annonce


def test_moteur_reponses_vendeur():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node facultatif requis pour les scénarios du moteur JavaScript")
    resultat = subprocess.run([node, "--test", str(Path(__file__).with_suffix(".cjs"))],
                              capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert resultat.returncode == 0, resultat.stdout + resultat.stderr


def test_premier_contact_reste_court_et_decisif():
    texte = messages_contact(faire_annonce())["court"]
    assert len(texte.split()) < 180
    assert sum(l.startswith("- ") for l in texte.splitlines()) == 5
    for essentiel in ["murs seuls", "loué", "durée de bail", "HT et hors charges", "charges", "taxe foncière", "impayés"]:
        assert essentiel in texte
    for dossier in ["procès-verbaux", "diagnostics", "solvabilité", "plan coté", "règlement de copropriété", "travaux"]:
        assert dossier not in texte
