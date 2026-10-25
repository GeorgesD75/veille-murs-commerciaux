from unittest.mock import Mock

import pytest
import requests

from sources.http import ClientPoli, SourceBloqueeErreur, SourceTemporaireErreur


def client_avec(*reponses):
    client = ClientPoli(0, 0)
    client.session = Mock()
    client.session.get.side_effect = reponses
    return client


@pytest.mark.parametrize("statut", [429, 500, 503])
def test_robots_indisponible_ne_declenche_pas_la_collecte(statut):
    c = client_avec(Mock(status_code=statut))
    with pytest.raises(SourceTemporaireErreur):
        c.obtenir("https://exemple.fr/annonce")
    assert c.session.get.call_count == 1


def test_robots_erreur_reseau_retentable():
    c = client_avec(requests.Timeout())
    with pytest.raises(SourceTemporaireErreur):
        c.obtenir("https://exemple.fr/annonce")
    assert not c._robots


def test_arret_hote_apres_limitation_sans_interdire_prochaine_tournee():
    c = client_avec(Mock(status_code=404), Mock(status_code=429))
    for chemin in ["a", "b"]:
        with pytest.raises(SourceTemporaireErreur):
            c.obtenir(f"https://exemple.fr/{chemin}")
    assert c.session.get.call_count == 2  # robots + une annonce, pas la deuxième


def test_interdiction_robots_respectee():
    c = client_avec(Mock(status_code=200, text="User-agent: *\nDisallow: /annonce"))
    with pytest.raises(SourceBloqueeErreur):
        c.obtenir("https://exemple.fr/annonce")
    assert c.session.get.call_count == 1


def test_robots_absent_et_cache_par_hote():
    c = client_avec(Mock(status_code=404), Mock(status_code=200, text="A"), Mock(status_code=200, text="B"))
    assert c.obtenir("https://exemple.fr/a") == "A"
    assert c.obtenir("https://exemple.fr/b") == "B"
    assert c.session.get.call_count == 3
