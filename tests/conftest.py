from __future__ import annotations

import pytest

from pipeline.config import RACINE, Config
from pipeline.enrichissement import Benchmarks
from pipeline.geo import Trajets


@pytest.fixture(scope="session")
def config() -> Config:
    return Config.charger(RACINE / "config.yaml")


@pytest.fixture(scope="session")
def trajets() -> Trajets:
    return Trajets.charger(RACINE / "data" / "trajets.json")


@pytest.fixture(scope="session")
def benchmarks() -> Benchmarks:
    return Benchmarks.charger(RACINE / "data" / "benchmarks.json")
