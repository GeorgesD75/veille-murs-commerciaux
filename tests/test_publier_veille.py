"""Vraies courses Git entre une tournée et une mise à jour du site."""
from pathlib import Path
import json
import subprocess

import pytest

from scripts import publier_veille as publication


def git(repo, *args, check=True):
    return subprocess.run(["git", *args], cwd=repo, check=check, capture_output=True,
                          text=True, encoding="utf-8")


def ecrire(repo, nom, texte):
    p = repo / nom
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(texte, encoding="utf-8")


def committer(repo):
    git(repo, "add", ".")
    git(repo, "commit", "-m", "modification")


@pytest.fixture
def depots(tmp_path):
    distant = tmp_path / "distant.git"
    git(tmp_path, "init", "--bare", "--initial-branch=master", str(distant))
    humain, robot = tmp_path / "humain", tmp_path / "robot"
    git(tmp_path, "clone", str(distant), str(humain))
    git(humain, "config", "user.name", "test")
    git(humain, "config", "user.email", "test@example.invalid")
    ecrire(humain, "data/annonces.json", '{"collecte":1}')
    ecrire(humain, "docs/index.html", "ancienne page\n")
    ecrire(humain, "template.txt", "ancien design")
    committer(humain)
    git(humain, "push", "origin", "master")
    # Même historique réduit que le checkout GitHub Actions.
    git(tmp_path, "clone", "--depth=1", distant.as_uri(), str(robot))
    git(robot, "config", "user.name", "robot")
    git(robot, "config", "user.email", "robot@example.invalid")
    return distant, humain, robot


def preparer_collecte(robot):
    ecrire(robot, "data/annonces.json", '{"collecte":2,"nouvelles":["nouveau-local"]}')
    ecrire(robot, "docs/index.html", "page de la tournee\n")


def regenerer(repo):
    # Le rendu dépend vraiment du code distant et des données collectées.
    ecrire(repo, "docs/index.html", (repo / "template.txt").read_text(encoding="utf-8") +
           "\n" + (repo / "data/annonces.json").read_text(encoding="utf-8"))


def changer_design(humain, *, html=True):
    ecrire(humain, "template.txt", "nouveau design")
    if html:
        ecrire(humain, "docs/index.html", "nouvelle page humaine\n")
    committer(humain)
    git(humain, "push", "origin", "master")


def test_publication_sans_course_et_sans_force(depots):
    distant, humain, robot = depots
    preparer_collecte(robot)
    assert publication.publier(robot, reconstruire=lambda _: pytest.fail("inutile"),
                               controler=lambda _: pytest.fail("déjà contrôlé"))
    assert "nouveau-local" in git(distant, "show", "master:data/annonces.json").stdout
    git(humain, "fetch", "origin")
    assert git(humain, "merge-base", "--is-ancestor", "HEAD", "origin/master", check=False).returncode == 0


@pytest.mark.parametrize("conflit_html", [True, False])
def test_code_concurrent_reconstruit_sans_perdre_la_collecte(depots, conflit_html):
    distant, humain, robot = depots
    preparer_collecte(robot)
    changer_design(humain, html=conflit_html)
    controles = []

    def controler(repo):
        html = (repo / "docs/index.html").read_text(encoding="utf-8")
        assert "nouveau design" in html and "nouveau-local" in html
        assert "<<<<<<<" not in html
        controles.append(True)

    assert publication.publier(robot, reconstruire=regenerer, controler=controler)
    assert controles == [True]
    assert git(distant, "show", "master:template.txt").stdout == "nouveau design"
    assert "nouveau-local" in git(distant, "show", "master:docs/index.html").stdout
    assert json.loads(git(distant, "show", "master:data/annonces.json").stdout)["collecte"] == 2


def test_conflit_sur_le_stock_n_est_pas_ecrase(depots):
    distant, humain, robot = depots
    preparer_collecte(robot)
    ecrire(humain, "data/annonces.json", '{"collecte":3,"autre_local":true}')
    committer(humain)
    git(humain, "push", "origin", "master")
    avant = git(distant, "rev-parse", "master").stdout
    with pytest.raises(RuntimeError, match="data/annonces.json"):
        publication.publier(robot, reconstruire=lambda _: pytest.fail("stock en conflit"))
    assert git(distant, "rev-parse", "master").stdout == avant
    assert "nouveau-local" in (robot / "data/annonces.json").read_text(encoding="utf-8")
    assert git(robot, "status", "--porcelain").stdout == ""


def test_validation_apres_rebase_empeche_une_publication_cassee(depots):
    distant, humain, robot = depots
    preparer_collecte(robot)
    changer_design(humain)
    avant = git(distant, "rev-parse", "master").stdout

    def invalide(_):
        raise RuntimeError("JavaScript invalide")

    with pytest.raises(RuntimeError, match="JavaScript invalide"):
        publication.publier(robot, reconstruire=regenerer, controler=invalide)
    assert git(distant, "rev-parse", "master").stdout == avant
    assert "nouveau-local" in (robot / "data/annonces.json").read_text(encoding="utf-8")


def test_nouveau_push_pendant_la_validation_declenche_une_nouvelle_synchronisation(depots):
    distant, humain, robot = depots
    preparer_collecte(robot)
    changer_design(humain)
    controles = []

    def controler(_):
        controles.append(True)
        if len(controles) == 1:
            ecrire(humain, "template.txt", "troisieme design")
            committer(humain)
            git(humain, "push", "origin", "master")

    assert publication.publier(robot, reconstruire=regenerer, controler=controler, attendre=lambda _: None)
    assert len(controles) == 2
    assert "troisieme design" in git(distant, "show", "master:docs/index.html").stdout
    assert "nouveau-local" in git(distant, "show", "master:docs/index.html").stdout


def test_pas_de_commit_si_le_stock_ne_change_pas(depots):
    distant, _, robot = depots
    avant = git(distant, "rev-parse", "master").stdout
    assert publication.publier(robot) is False
    assert git(distant, "rev-parse", "master").stdout == avant
