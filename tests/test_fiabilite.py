import json

import pytest

from pipeline.contact import messages_contact
from pipeline.fiabilite import diagnostiquer
from pipeline.normalisation import normaliser
from pipeline.scoring import scorer
from sources.donnees_structurees import extraire_structure, appliquer_structure
from sources.extraction import loyer_mensuel_depuis_texte
from pipeline.enrichissement import enrichir
from tests.fabriques import faire_annonce
from tests.test_run import _brute
from pipeline.stockage import Stockage
from pipeline.dedoublonnage import trouver_similaire
from sources.imap_alertes import SourceImap
from sources.bienici import SourceBienici
from urllib.parse import urlparse, parse_qs
from pipeline.approfondissement import est_page_de_liste, approfondir_annonces
from scripts.nettoyer_fiches import nettoyer
from pipeline.filtres import raison_exclusion


URL = "https://agence.fr/local/123"


def page(objet):
    return '<script type="application/ld+json">' + json.dumps(objet) + '</script>'


def bien(**changements):
    o = {"@type": "Product", "url": URL,
         "floorSize": {"value": 28, "unitCode": "MTK"},
         "offers": {"price": 150000, "priceCurrency": "EUR"},
         "address": {"postalCode": "75018"}}
    o.update(changements)
    return o


def test_structure_fiche_et_unites_explicites():
    d = extraire_structure(page(bien()), URL)
    assert d["prix"] == 150000 and d["surface_m2"] == 28
    assert d["code_postal"] == "75018"
    assert "surface_m2" not in extraire_structure(page(bien(floorSize={"value": 300, "unitCode": "FTK"})), URL)


def test_ne_prend_pas_le_prix_dune_recommandation():
    assert extraire_structure(page(bien(url="https://agence.fr/autre")), URL) == {}
    assert extraire_structure(page({"@type": "ItemList", "itemListElement": [bien()]}), URL) == {}


def test_jsonld_invalide_ignore_et_graph_resolu():
    assert extraire_structure('<script type="application/ld+json">invalide</script>', URL) == {}
    o = bien()
    o["@id"] = URL + "#bien"
    graph = {"@graph": [{"@type": "WebPage", "url": URL, "mainEntity": {"@id": o["@id"]}}, o]}
    assert extraire_structure(page(graph), URL)["surface_m2"] == 28


def test_conflit_conserve_les_deux_chiffres_et_plafonne(config):
    a = faire_annonce(prix=250000, surface_m2=30, score=90, url=URL)
    appliquer_structure(a, {"prix": 150000, "surface_m2": 45}, "2026-10-25T12:00:00+01:00")
    assert a.prix == 250000 and a.surface_m2 == 30
    assert a.preuves["prix"][0]["valeur"] == 150000
    assert diagnostiquer(a)["bloquant"]
    scorer(a, config)
    assert a.score < config.scoring["seuils"]["affichage"]


@pytest.mark.parametrize("valeur", [float("nan"), float("inf"), -10, 0, True])
def test_valeurs_non_exploitables_ne_poussent_pas_les_scores(valeur):
    a = normaliser(_brute(prix=valeur, surface_m2=valeur, loyer_mensuel=valeur))
    assert a.prix is None and a.surface_m2 is None and a.loyer_mensuel is None


def test_loyer_au_m2_et_unite_explicite_aberrante():
    assert loyer_mensuel_depuis_texte("Loyer 300 €/m²/an", 150000) is None
    assert loyer_mensuel_depuis_texte("Loyer 300 €/m²/an", 150000, 30) == 750
    assert loyer_mensuel_depuis_texte("Loyer 24 000 €/mois", 150000) is None
    assert loyer_mensuel_depuis_texte("Loyer annuel 60 000 €", 150000) is None
    assert loyer_mensuel_depuis_texte("Loyer 18 000 €/an", 230000) == 1500


def test_recalcul_ne_conserve_pas_un_ancien_rendement(benchmarks):
    a = faire_annonce()
    enrichir(a, benchmarks, 20)
    assert a.rendement_brut_pct
    a.loyer_mensuel = None
    enrichir(a, benchmarks, 20)
    assert a.rendement_brut_pct is None and a.prix_cible_rendement is None


def test_messages_libres_occupes_et_relance():
    libre = faire_annonce(description="Vente de murs libres, local vide.")
    occupe = faire_annonce(description="Murs occupés, locataire en place.", loyer_mensuel=1200)
    assert "dernier loyer" in messages_contact(libre)["court"]
    assert "loyer actuel HT et hors charges" in messages_contact(occupe)["court"]
    assert "Bail signé" in messages_contact(occupe)["dossier"]
    assert "précédent message" in messages_contact(occupe)["relance"]
    for texte in messages_contact(occupe).values():
        assert "le secteur se négocie" not in texte and "disponible rapidement" not in texte


def test_sauvegarde_invalide_ne_detruit_pas_le_stock(tmp_path):
    chemin = tmp_path / "annonces.json"
    stockage = Stockage(chemin)
    a = faire_annonce()
    stockage.sauvegarder({a.id: a}, {})
    avant = chemin.read_bytes()
    a.prix = float("nan")
    with pytest.raises(ValueError):
        stockage.sauvegarder({a.id: a}, {})
    assert chemin.read_bytes() == avant
    assert not list(tmp_path.glob("*.tmp"))


def test_meme_prix_surface_cp_ne_suffit_pas_pour_fusionner(config):
    a = faire_annonce(url="https://agence.fr/a")
    b = faire_annonce(source="autre", id="autre", url="https://autre.fr/b")
    assert trouver_similaire(b, [a], config) is None
    b.images = ["https://photos.fr/un-bien-unique.jpg"]
    a.images = b.images
    assert trouver_similaire(b, [a], config) is a


def test_resolution_chaines_et_cache_imap(monkeypatch):
    appels = []
    urls = {"https://click.by.seloger.com/a": "https://redirect.seloger.com/b",
            "https://redirect.seloger.com/b": "https://www.seloger.com/annonce/987654321"}
    def head(url, **kwargs):
        appels.append(url)
        return type("Reponse", (), {"status_code": 302, "headers": {"Location": urls[url]}})()
    monkeypatch.setattr("sources.imap_alertes.requests.head", head)
    source = SourceImap()
    for _ in range(2):
        assert source._resoudre_redirection("https://click.by.seloger.com/a") == "https://www.seloger.com/annonce/987654321"
    assert len(appels) == 2


def test_pagination_bienici_change_reellement_offset():
    source = SourceBienici(max_pages=3)
    filtres = [json.loads(parse_qs(urlparse(source._url(p)).query)["filters"][0]) for p in [1,2,3]]
    assert [f["from"] for f in filtres] == [0, 100, 200]


def test_une_redirection_vers_listing_ne_donne_pas_un_loyer(config, monkeypatch):
    html = '<h1>Vente commerces Paris - 401 annonces</h1>' + '<a href="/annonce/autre">Local</a>' * 5 + '<p>Loyer annuel 17714 €</p>'
    assert est_page_de_liste(html)
    client = type("Client", (), {"obtenir": lambda self, url: html})()
    monkeypatch.setattr("pipeline.approfondissement.ClientPoli", lambda: client)
    a = faire_annonce(loyer_mensuel=None, date_derniere_vue="2026-10-25T12:00:00+01:00")
    rapport = approfondir_annonces({a.id: a}, config)
    assert a.loyer_mensuel is None and not a.texte_detail
    assert a.etat_detail == "redirection_liste" and rapport["listes"] == 1


def test_nettoyage_ancien_listing_ne_conserve_pas_un_loyer_parasite():
    a = faire_annonce(loyer_mensuel=1476, texte_detail="Vente commerces Paris - 401 annonces ... Loyer annuel 17714 €")
    rapport = nettoyer({a.id:a})
    assert not a.texte_detail and a.loyer_mensuel is None
    assert a.etat_detail == "redirection_liste"
    assert rapport["loyers_retires_ou_corriges"] == 1


def test_petits_tickets_autorises_uniquement_sur_les_petites_surfaces(config, trajets):
    petit = faire_annonce(prix=75000, surface_m2=15)
    grand = faire_annonce(prix=75000, surface_m2=80)
    assert raison_exclusion(petit, config, trajets) is None
    assert "budget" in raison_exclusion(grand, config, trajets)


def test_loyer_reconstitue_reste_estime_meme_si_occupe(config, benchmarks):
    a = faire_annonce(loyer_origine="rendement", description="Murs occupés, locataire en place.")
    enrichir(a, benchmarks, 20)
    scorer(a, config)
    assert a.loyer_estime and a.loyer_confiance == "rendement"
    assert a.score < config.scoring["seuils"]["pepite"]
    assert "loyer_deduit" in a.flags
    assert "loyer actuel HT et hors charges" in messages_contact(a)["court"]
