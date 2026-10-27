"""Publie une collecte sans écraser une modification concurrente du site."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

RACINE = Path(__file__).resolve().parent.parent


def git(racine: Path, *arguments: str, verifier: bool = True) -> subprocess.CompletedProcess:
    resultat = subprocess.run(["git", *arguments], cwd=racine,
                              text=True, encoding="utf-8", capture_output=True)
    if verifier and resultat.returncode:
        print(resultat.stderr, file=sys.stderr, flush=True)
        resultat.check_returncode()
    return resultat


def regenerer(racine: Path) -> None:
    # Après rebase, ces fichiers Python sont ceux de la branche distante.
    # Aucun crawl, appel IA ou email : on reconstruit avec le stock collecté.
    subprocess.run([sys.executable, "-c", "from scripts.regenerer_dashboard import main; main(persister=True)"],
                   cwd=racine, check=True)


def verifier_site(racine: Path) -> None:
    subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=racine, check=True)
    html = (racine / "docs/index.html").read_text(encoding="utf-8")
    scripts = re.findall(r"<script>(.*?)</script>", html, re.S)
    if not scripts:
        raise RuntimeError("Aucun script JavaScript dans le dashboard régénéré.")
    with tempfile.TemporaryDirectory() as dossier:
        cible = Path(dossier) / "dashboard.js"
        cible.write_text("\n".join(scripts), encoding="utf-8")
        subprocess.run(["node", "--check", str(cible)], cwd=racine, check=True)
    subprocess.run([sys.executable, "scripts/verifier_apercu.py"], cwd=racine, check=True)


def publier(racine: Path = RACINE, *, reconstruire=regenerer,
            controler=verifier_site, attendre=time.sleep, essais: int = 3) -> bool:
    git(racine, "add", "--", "data/", "docs/")
    autres = [p for p in git(racine, "diff", "--cached", "--name-only").stdout.splitlines()
              if not p.startswith(("data/", "docs/"))]
    if autres:
        raise RuntimeError("Fichiers indexés hors collecte : " + ", ".join(autres))
    if git(racine, "diff", "--cached", "--quiet", verifier=False).returncode == 0:
        print("Rien de nouveau à publier.", flush=True)
        return False
    git(racine, "commit", "-m", f"Tournée du {datetime.now(timezone.utc):%Y-%m-%d}")
    for tentative in range(1, essais + 1):
        git(racine, "fetch", "origin", "master")
        # Une avance distante impose une nouvelle génération, même si Git
        # saurait fusionner le HTML automatiquement : le template a pu changer.
        avance = git(racine, "merge-base", "--is-ancestor", "origin/master", "HEAD", verifier=False)
        if avance.returncode not in (0, 1):
            raise RuntimeError(avance.stderr)
        if avance.returncode == 1:
            print("Modification distante détectée : mise à jour du code et reconstruction du site.", flush=True)
            rebase = git(racine, "rebase", "origin/master", verifier=False)
            if rebase.returncode:
                conflits = git(racine, "diff", "--name-only", "--diff-filter=U").stdout.splitlines()
                if conflits != ["docs/index.html"]:
                    git(racine, "rebase", "--abort", verifier=False)
                    raise RuntimeError("Publication interrompue sans écrasement : " +
                                       (", ".join(conflits) or rebase.stderr))
                print("Conflit sur la page générée : reconstruction avec les données de la tournée.", flush=True)
                try:
                    reconstruire(racine)
                    git(racine, "add", "--", "data/", "docs/")
                    git(racine, "-c", "core.editor=true", "rebase", "--continue")
                except Exception:
                    git(racine, "rebase", "--abort", verifier=False)
                    raise
            else:
                reconstruire(racine)
                git(racine, "add", "--", "data/", "docs/")
                if git(racine, "diff", "--cached", "--quiet", verifier=False).returncode:
                    git(racine, "commit", "--amend", "--no-edit")
            controler(racine)
        resultat = git(racine, "push", "origin", "HEAD:master", verifier=False)
        if resultat.returncode == 0:
            print("Données et site publiés.", flush=True)
            return True
        print(f"Push refusé (tentative {tentative}/{essais}) : {resultat.stderr.strip()}", flush=True)
        if tentative < essais:
            attendre(5)
    raise RuntimeError("Publication impossible après trois tentatives ; la sauvegarde de la collecte reste disponible dans les artefacts.")


if __name__ == "__main__":
    publier()
