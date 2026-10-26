"""Approfondissement : texte de page, extraction, budget, tolérance aux pannes."""
from __future__ import annotations

from pipeline.approfondissement import approfondir, approfondir_annonces, texte_de_page
from pipeline.config import Config
from sources.http import SourceBloqueeErreur
from tests.fabriques import faire_annonce

PAGE = """<html><head><title>x</title><style>.a{color:red}</style>
<script>var piege = "loyer annuel de 99 999 €";</script></head>
<body><nav>Accueil &gt; Annonces</nav>
<h1>Murs de boutique</h1>
<p>Local de 45 m² lou&eacute;. Loyer annuel de 18 000 €.
Dettes de copropri&eacute;t&eacute; signal&eacute;es. DPE : F.
Article 606 &agrave; la charge du locataire.</p>
<footer>Mentions légales</footer></body></html>"""


def _config(actif=True, max_par_run=10):
    return Config({"analyse": {"approfondissement": {
        "actif": actif, "max_par_run": max_par_run, "budget_secondes": 60}}})


class ClientFactice:
    def __init__(self, reponses=None, leve=None):
        self.reponses = reponses or {}
        self.leve = leve
        self.urls = []

    def obtenir(self, url):
        self.urls.append(url)
        if self.leve:
            raise self.leve
        return self.reponses.get(url, PAGE)


def test_texte_de_page_retire_scripts_nav_et_entites():
    texte = texte_de_page(PAGE)
    assert "99 999" not in texte            # le script est retiré (piège classique)
    assert "color:red" not in texte
    assert "loué" in texte                  # entité &eacute; décodée
    assert "Loyer annuel de 18 000" in texte


def test_approfondir_remplit_loyer_et_alimente_les_detecteurs():
    a = faire_annonce(loyer_mensuel=None, surface_m2=None, prix=250_000.0)
    appris = approfondir(a, texte_de_page(PAGE))
    assert a.loyer_mensuel == 1_500.0       # 18 000 € annuels / 12
    assert a.surface_m2 == 45.0
    assert len(appris) == 2
    # le texte de détail nourrit texte_complet() : dettes de copro, DPE, 606
    assert "dettes de copropriété" in a.texte_complet().lower()
    assert "article 606" in a.texte_complet().lower()


def test_priorite_aux_meilleurs_scores_et_budget(monkeypatch):
    client = ClientFactice()
    monkeypatch.setattr("pipeline.approfondissement.ClientPoli", lambda: client)
    annonces = {
        "a": faire_annonce(id="a", url="https://exemple.fr/a", score=40),
        "b": faire_annonce(id="b", url="https://exemple.fr/b", score=80),
        "c": faire_annonce(id="c", url="https://exemple.fr/c", score=60),
    }
    approfondir_annonces(annonces, _config(max_par_run=2))
    assert client.urls == ["https://exemple.fr/b", "https://exemple.fr/c"]
    assert annonces["b"].approfondie and annonces["c"].approfondie
    assert not annonces["a"].approfondie    # au prochain run


def test_site_bloque_marque_sans_acharnement(monkeypatch):
    client = ClientFactice(leve=SourceBloqueeErreur("robots.txt interdit"))
    monkeypatch.setattr("pipeline.approfondissement.ClientPoli", lambda: client)
    annonces = {"a": faire_annonce(id="a", url="https://exemple.fr/a", score=80)}
    approfondir_annonces(annonces, _config())
    assert annonces["a"].approfondie is True   # interdit : on n'y reviendra pas


def test_panne_reseau_reessaiera(monkeypatch):
    client = ClientFactice(leve=TimeoutError("réseau"))
    monkeypatch.setattr("pipeline.approfondissement.ClientPoli", lambda: client)
    annonces = {"a": faire_annonce(id="a", url="https://exemple.fr/a", score=80)}
    approfondir_annonces(annonces, _config())
    assert annonces["a"].approfondie is False  # pas marquée : nouvel essai plus tard


def test_inactif_ne_fait_rien(monkeypatch):
    client = ClientFactice()
    monkeypatch.setattr("pipeline.approfondissement.ClientPoli", lambda: client)
    annonces = {"a": faire_annonce(id="a", score=80)}
    approfondir_annonces(annonces, _config(actif=False))
    assert client.urls == []


def test_texte_detail_ignore_les_loyers_des_recommandations():
    html = '<main><h1>Murs de 30 m²</h1><p>Local libre.</p><section class="related-properties">Loyer annuel 99 000 €</section></main>'
    texte = texte_de_page(html)
    assert "99 000" not in texte and "30 m²" in texte
    html = '<main><h1>Local libre</h1><h2>Annonces similaires</h2><div><p>Loyer 8000 €/mois</p></div></main>'
    assert "8000" not in texte_de_page(html)


def test_priorite_detail_aux_petites_surfaces(monkeypatch):
    client = ClientFactice()
    monkeypatch.setattr("pipeline.approfondissement.ClientPoli", lambda: client)
    annonces = {"grand": faire_annonce(score=90, url="https://exemple.fr/grand"),
                "petit": faire_annonce(surface_m2=25, score=55, url="https://exemple.fr/petit")}
    approfondir_annonces(annonces, _config(max_par_run=1))
    assert client.urls == ["https://exemple.fr/petit"]


def test_grandes_opportunites_ne_sont_pas_affamees_par_les_petites(monkeypatch):
    client = ClientFactice()
    monkeypatch.setattr("pipeline.approfondissement.ClientPoli", lambda: client)
    annonces = {f"p{i}": faire_annonce(id=f"p{i}", surface_m2=25, score=60,
                                     url=f"https://exemple.fr/p{i}") for i in range(10)}
    annonces["grande"] = faire_annonce(id="grande", score=90, url="https://exemple.fr/grande")
    # Une nouvelle fiche sans score reste éligible à l'exploration si son
    # revenu déclaré est intéressant ; sa qualification sera faite après lecture.
    annonces["nouvelle"] = faire_annonce(id="nouvelle", score=None, url="https://exemple.fr/nouvelle")
    annonces["ordinaire"] = faire_annonce(id="ordinaire", score=30, loyer_mensuel=500,
                                         url="https://exemple.fr/ordinaire")
    rapport = approfondir_annonces(annonces, _config(max_par_run=6))
    assert client.urls == [f"https://exemple.fr/{id}" for id in
                           ["p0", "p1", "grande", "p2", "p3", "nouvelle"]]
    assert rapport["tentees"] == 6
    assert not annonces["ordinaire"].approfondie


def test_creneaux_inutilises_reviennent_aux_petites_surfaces(monkeypatch):
    client = ClientFactice()
    monkeypatch.setattr("pipeline.approfondissement.ClientPoli", lambda: client)
    annonces = {str(i): faire_annonce(id=str(i), surface_m2=25, url=f"https://exemple.fr/{i}")
                for i in range(4)}
    rapport = approfondir_annonces(annonces, _config(max_par_run=4))
    assert rapport["tentees"] == 4
    assert len(set(client.urls)) == 4
