"""Garde-fou visuel léger : le header a déjà explosé en hauteur sans qu'aucun
test ne s'en aperçoive (régression corrigée en 5eeb9a9, ré-ajustée en
337e7fb) — la structure HTML était valide, la hauteur RENDUE ne l'était pas,
et ça ne se voit qu'après rendu CSS réel, jamais dans le HTML brut ni dans le
payload JSON que testent les tests Python habituels.

Pas de diff pixel par pixel (fragile : polices, anti-aliasing, sous-pixel) —
juste la hauteur du bandeau vert, repérée par transition de couleur sur une
capture d'écran headless, comparée à une plage large. Attrape une vraie
explosion, jamais un ajustement mineur de quelques pixels.

Ignoré proprement (jamais bloquant) si aucun Chrome/Chromium n'est trouvé sur
la machine — c'est un filet en plus des tests, pas une dépendance dure.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CIBLE = RACINE / "docs" / "index.html"
CAPTURE = RACINE / "_apercu_header.png"
HAUTEUR_MIN, HAUTEUR_MAX = 100, 260  # px — généreux, on attrape une explosion, pas un pixel près


def _navigateur() -> str | None:
    for nom in ("google-chrome-stable", "google-chrome", "chromium-browser", "chromium",
                "microsoft-edge", "msedge"):
        chemin = shutil.which(nom)
        if chemin:
            return chemin
    return None


def _distance(a: tuple, b: tuple) -> int:
    return sum(abs(x - y) for x, y in zip(a[:3], b[:3]))


def hauteur_header(navigateur: str) -> int:
    from PIL import Image

    subprocess.run(
        [navigateur, "--headless", "--disable-gpu", "--hide-scrollbars",
         f"--screenshot={CAPTURE}", "--window-size=1400,500",
         CIBLE.resolve().as_uri()],
        check=True, timeout=30,
    )
    img = Image.open(CAPTURE)
    # y=20 : dans le vert du bandeau, après la fine bordure or du tout haut
    # (3 px) — un point de repère stable plutôt que le tout premier pixel.
    couleur_bandeau = img.getpixel((5, 20))
    for y in range(20, img.height):
        if _distance(img.getpixel((5, y)), couleur_bandeau) < 20:
            continue
        return y
    return img.height


def main() -> int:
    if not CIBLE.exists():
        print(f"{CIBLE} introuvable — génère le dashboard avant ce script.")
        return 1
    navigateur = _navigateur()
    if navigateur is None:
        print("Aucun navigateur headless trouvé — vérification visuelle ignorée (pas bloquant).")
        return 0
    try:
        hauteur = hauteur_header(navigateur)
    finally:
        CAPTURE.unlink(missing_ok=True)
    print(f"Hauteur du header : {hauteur} px (plage attendue : {HAUTEUR_MIN}-{HAUTEUR_MAX} px)")
    if not (HAUTEUR_MIN <= hauteur <= HAUTEUR_MAX):
        print("Hors plage — probable régression de mise en page (cf. commentaire en tête de fichier).")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
