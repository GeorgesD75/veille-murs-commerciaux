from pathlib import Path
import shutil
import subprocess

import pytest


def test_impact_reponse():
    node=shutil.which("node")
    if not node:
        pytest.skip("Node requis pour les comparaisons du moteur JavaScript")
    r=subprocess.run([node,"--test",str(Path(__file__).with_suffix('.cjs'))],capture_output=True,text=True,encoding='utf-8',timeout=30)
    assert r.returncode==0,r.stdout+r.stderr
