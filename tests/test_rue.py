"""Emplacement rue par rue : extraction de voie, géocodage BAN, densité Overpass."""
from __future__ import annotations

import pytest

from pipeline.config import Config
from pipeline.rue import ClientGeo, Coordonnees, DensiteRue, evaluer_annonces, evaluer_rue, extraire_voie
from tests.fabriques import faire_annonce


def _config_rue(max_par_run: int) -> Config:
    """Config minimale et JETABLE : la fixture `config` est partagée entre
    tous les tests (scope session) — on ne la mute jamais ici."""
    return Config({"scoring": {"rue": {"max_par_run": max_par_run}}})


class FakeReponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class FakeSession:
    """Remplace requests.Session : une réponse scriptée par méthode."""

    def __init__(self, reponse_get=None, reponse_post=None, leve=None):
        self.reponse_get = reponse_get
        self.reponse_post = reponse_post
        self.leve = leve
        self.appels_get = 0
        self.appels_post = 0

    def get(self, url, params=None, timeout=None):
        self.appels_get += 1
        if self.leve:
            raise self.leve
        return self.reponse_get

    def post(self, url, data=None, timeout=None):
        self.appels_post += 1
        if self.leve:
            raise self.leve
        return self.reponse_post


# --- extraire_voie : conservateur, seulement avec un mot-type de voie ---


class TestExtraireVoie:
    def test_rue_simple(self):
        assert extraire_voie("Un local situé rue Godefroy Cavaignac à Paris") == \
            "rue Godefroy Cavaignac à Paris"

    def test_place(self):
        assert extraire_voie("Vente local commercial Paris 12e - Place Léon Blum") == "Place Léon Blum"

    def test_coupe_apres_tiret(self):
        assert extraire_voie("rue de Paris - proche métro Nation") == "rue de Paris"

    def test_pas_de_mot_type_renvoie_none(self):
        assert extraire_voie("Vente boutique Paris 5 - Proche Cardinal Lemoine") is None

    def test_simple_repere_sans_voie(self):
        assert extraire_voie("Local commercial à vendre Livry-Gargan - Proche transports") is None


# --- ClientGeo.geocoder : score et département ---


class TestGeocoder:
    def _client(self, **kwargs):
        client = ClientGeo(delai_s=0)
        client.session = FakeSession(**kwargs)
        return client

    def test_succes(self):
        client = self._client(reponse_get=FakeReponse({
            "features": [{
                "properties": {"score": 0.97, "citycode": "75111"},
                "geometry": {"coordinates": [2.3809, 48.8555]},
            }]
        }))
        coord = client.geocoder("rue Godefroy Cavaignac", "Paris", "75")
        assert coord == Coordonnees(lat=48.8555, lon=2.3809)

    def test_score_trop_bas_rejete(self):
        client = self._client(reponse_get=FakeReponse({
            "features": [{
                "properties": {"score": 0.2, "citycode": "75111"},
                "geometry": {"coordinates": [2.38, 48.85]},
            }]
        }))
        assert client.geocoder("rue X", "Paris", "75") is None

    def test_departement_ne_correspond_pas(self):
        # citycode 93048 (Seine-Saint-Denis) alors qu'on cherche dans le 75
        client = self._client(reponse_get=FakeReponse({
            "features": [{
                "properties": {"score": 0.9, "citycode": "93048"},
                "geometry": {"coordinates": [2.4, 48.9]},
            }]
        }))
        assert client.geocoder("rue X", "Paris", "75") is None

    def test_aucun_resultat(self):
        client = self._client(reponse_get=FakeReponse({"features": []}))
        assert client.geocoder("rue introuvable", "Paris", "75") is None

    def test_panne_reseau_ne_leve_pas(self):
        client = self._client(leve=RuntimeError("timeout"))
        assert client.geocoder("rue X", "Paris", "75") is None


# --- ClientGeo.densite_commerces : classification actif/vacant ---


class TestDensiteCommerces:
    def test_compte_actifs_et_vacants(self):
        client = ClientGeo(delai_s=0)
        client.session = FakeSession(reponse_post=FakeReponse({"elements": [
            {"tags": {"shop": "bakery"}},
            {"tags": {"shop": "hairdresser"}},
            {"tags": {"shop": "vacant"}},
            {"tags": {"disused:shop": "clothes"}},
        ]}))
        densite = client.densite_commerces(Coordonnees(lat=48.85, lon=2.35))
        assert densite == DensiteRue(nb_commerces=2, nb_vacants=2)

    def test_panne_reseau_ne_leve_pas(self):
        client = ClientGeo(delai_s=0)
        client.session = FakeSession(leve=RuntimeError("503"))
        assert client.densite_commerces(Coordonnees(lat=48.85, lon=2.35)) is None


class TestCategorieDensite:
    @pytest.mark.parametrize("nb,attendu", [
        (20, "tres_commercante"), (15, "tres_commercante"),
        (10, "commercante"), (8, "commercante"),
        (5, "calme"), (3, "calme"),
        (2, "peu_commercante"), (0, "peu_commercante"),
    ])
    def test_seuils(self, nb, attendu):
        assert DensiteRue(nb_commerces=nb, nb_vacants=0).categorie == attendu


# --- evaluer_annonces : orchestration, plafond, priorité, mémorisation ---


class TestEvaluerAnnonces:
    def test_plafond_et_priorite_par_score(self):
        # 3 annonces sans voie détectable (chemin le plus simple à vérifier) :
        # seules les 2 meilleures scores doivent être traitées si le plafond est 2.
        annonces = {
            "a": faire_annonce(id="a", score=10, titre="Aucune voie ici", description=""),
            "b": faire_annonce(id="b", score=90, titre="Aucune voie ici", description=""),
            "c": faire_annonce(id="c", score=50, titre="Aucune voie ici", description=""),
        }
        evaluer_annonces(annonces, _config_rue(2))
        # b (90) et c (50) traitées en priorité ; a (10) laissée de côté ce run-ci
        assert annonces["b"].rue_evaluee is True
        assert annonces["c"].rue_evaluee is True
        assert annonces["a"].rue_evaluee is False

    def test_annonce_exclue_ignoree(self):
        annonces = {"x": faire_annonce(id="x", score=99, exclue=True)}
        evaluer_annonces(annonces, _config_rue(25))
        assert annonces["x"].rue_evaluee is False

    def test_sans_voie_marquee_evaluee_sans_appel_reseau(self):
        a = faire_annonce(titre="Local à vendre", description="Proche métro Nation")
        evaluer_annonces({"a": a}, _config_rue(25))
        assert a.rue_evaluee is True
        assert a.rue_categorie is None

    def test_succes_remplit_les_champs(self, monkeypatch):
        a = faire_annonce(titre="Local rue Godefroy Cavaignac à Paris", ville="Paris",
                          code_postal="75011", departement="75")
        monkeypatch.setattr(
            "pipeline.rue.evaluer_rue",
            lambda voie, ville, dep, client: DensiteRue(nb_commerces=20, nb_vacants=0),
        )
        evaluer_annonces({"a": a}, _config_rue(25))
        assert a.rue_evaluee is True
        assert a.rue_categorie == "tres_commercante"
        assert a.rue_nb_commerces == 20

    def test_echec_reseau_ne_marque_pas_evaluee(self, monkeypatch):
        # Laisse la porte ouverte à un nouvel essai lors d'un prochain run.
        a = faire_annonce(titre="Local rue Godefroy Cavaignac à Paris", ville="Paris",
                          code_postal="75011", departement="75")
        monkeypatch.setattr("pipeline.rue.evaluer_rue", lambda *a, **k: None)
        evaluer_annonces({"a": a}, _config_rue(25))
        assert a.rue_evaluee is False

    def test_max_par_run_zero_desactive(self):
        a = faire_annonce(titre="rue Godefroy Cavaignac", score=90)
        evaluer_annonces({"a": a}, _config_rue(0))
        assert a.rue_evaluee is False

    def test_budget_de_temps_arrete_avant_le_plafond_de_volume(self, monkeypatch):
        # Un budget de temps déjà écoulé stoppe la boucle même si le plafond
        # de volume (max_par_run) n'est pas atteint — garde-fou contre un
        # Overpass lent à échouer, pas seulement contre son nombre d'appels.
        config = Config({"scoring": {"rue": {"max_par_run": 10, "budget_secondes": 0.001}}})
        annonces = {
            "a": faire_annonce(id="a", titre="rue Godefroy Cavaignac", score=90),
            "b": faire_annonce(id="b", titre="rue de Paris", score=80),
        }
        horloge = iter([0.0, 10.0, 20.0, 30.0, 40.0])  # « débuts » puis vérifications, très en avance
        monkeypatch.setattr("pipeline.rue.time.monotonic", lambda: next(horloge))
        evaluer_annonces(annonces, config)
        assert annonces["a"].rue_evaluee is False
        assert annonces["b"].rue_evaluee is False
