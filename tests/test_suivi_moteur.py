"""Calendrier et classement des actions locales, exécutés en JavaScript."""
from pathlib import Path
import shutil
import subprocess

import pytest


def test_suivi_moteur():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node facultatif requis pour le moteur de suivi")
    resultat = subprocess.run([node, "--test", str(Path(__file__).with_suffix(".cjs"))],
                              capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert resultat.returncode == 0, resultat.stdout + resultat.stderr
