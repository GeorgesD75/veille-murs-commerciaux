"""Scénarios de décision exécutés sur le même module JavaScript que le site."""
from pathlib import Path
import shutil
import subprocess

import pytest


def test_decision_achat():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node facultatif requis pour les scénarios de décision")
    resultat = subprocess.run([node, "--test", str(Path(__file__).with_suffix(".cjs"))],
                              capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert resultat.returncode == 0, resultat.stdout + resultat.stderr
