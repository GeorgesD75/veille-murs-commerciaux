from unittest.mock import Mock

import pytest
import requests

from sources.http import ClientPoli, SourceBloqueeErreur, SourceTemporaireErreur
from sources.http import robots_autorise
from urllib.robotparser import RobotFileParser


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


@pytest.mark.parametrize('chemin,autorise',[
    ('/produit.list?search=1',False),('/fr/lf10/10/0/1',False),
    ('/fr/lf10/50/0/1',True),('/fr/lf10/50/0/2',False),
    ('/fr/lf10/50/0/2/autre',True),('/public',True),
])
def test_robots_regle_la_plus_longue_et_jokers(chemin,autorise):
    r=RobotFileParser()
    r.parse(['User-agent: *','Allow: /','Disallow: /produit.list',
             'Disallow: /*/lf*/10','Disallow: /*/lf*/*/*/2$'])
    assert robots_autorise(r,'VeilleMursCommerciaux/0.1','https://exemple.fr'+chemin)==autorise


def test_robots_groupe_specifique_et_allow_prioritaire_a_egalite():
    r=RobotFileParser()
    r.parse(['User-agent: *','Disallow: /','',
             'User-agent: VeilleMursCommerciaux','Allow: /','Disallow: /secret','Allow: /secret/public'])
    assert robots_autorise(r,'VeilleMursCommerciaux/0.1','https://exemple.fr/secret/public')
    assert not robots_autorise(r,'VeilleMursCommerciaux/0.1','https://exemple.fr/secret/prive')
    assert not robots_autorise(r,'AutreBot','https://exemple.fr/public')
