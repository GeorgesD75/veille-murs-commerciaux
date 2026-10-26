"""QA optionnelle sur le HTML généré : python scripts/verifier_interactions.py.

Nécessite Playwright (pip install playwright) et un Chrome/Chromium installé.
Utilise le navigateur existant ; aucune installation de navigateur automatique.
"""
from pathlib import Path
import shutil

from playwright.sync_api import sync_playwright

RACINE = Path(__file__).resolve().parent.parent


def main():
    candidats = [shutil.which("google-chrome"), shutil.which("chromium"),
                 r"C:\Program Files\Google\Chrome\Application\chrome.exe"]
    navigateur = next((c for c in candidats if c and Path(c).exists()), None)
    if not navigateur:
        raise SystemExit("Chrome/Chromium installé requis pour ce contrôle optionnel.")
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=navigateur, headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        erreurs = []
        page.on("pageerror", lambda e: erreurs.append(str(e)))
        # Les images distantes ne sont pas nécessaires aux tests d'interaction.
        page.route("**/*", lambda route: route.abort() if route.request.resource_type == "image" else route.continue_())
        page.goto((RACINE / "docs/index.html").as_uri(), wait_until="domcontentloaded")
        assert not page.locator("#volet-filtres").evaluate("e=>e.open")
        assert page.locator(".carte").first.bounding_box()["y"] < 250
        assert not page.locator(".analyse-annonce").first.evaluate("e=>e.open")
        page.locator(".analyse-annonce > summary").first.click()
        assert page.locator(".analyse-contenu").first.is_visible()
        page.locator(".analyse-annonce > summary").first.click()
        page.locator(".outils-annonce > summary").first.click()
        assert page.locator(".carte button[data-check]").first.is_visible()
        page.locator(".outils-annonce > summary").first.click()
        page.locator("#volet-filtres > summary").click()
        assert page.locator("#f-surface").input_value() == "40"
        assert page.locator(".decision .priorite").count() > 0
        page.locator("#f-surface").fill("25")
        assert page.evaluate("D.retenues.filter(a=>appliquer(a,filtres())).every(a=>a.surface_m2<25)")
        page.reload(wait_until="domcontentloaded")
        page.locator("#volet-filtres > summary").click()
        assert page.locator("#f-surface").input_value() == "25"
        page.locator("#f-reset").click()
        assert page.locator("#f-surface").input_value() == ""
        assert not page.locator("#f-cf").is_checked()
        assert not page.locator("#f-archives").is_checked()
        page.locator("#f-surface").fill("40")
        page.locator("#f-trajet").fill("30")
        page.locator("#f-tri").select_option("prix")
        assert page.evaluate("D.retenues.filter(a=>appliquer(a,filtres())).every(a=>a.surface_m2<40 && a.temps_trajet_min<=30)")
        page.locator(".carte button[data-contact]").first.click()
        premier = page.locator("#contact-texte").input_value()
        page.locator("[data-contact-mode=dossier]").click()
        dossier = page.locator("#contact-texte").input_value()
        page.locator("[data-contact-mode=relance]").click()
        relance = page.locator("#contact-texte").input_value()
        assert len({premier, dossier, relance}) == 3
        assert all("__URL__" not in m and "__REFERENCE__" not in m for m in [premier, dossier, relance])
        page.keyboard.press("Escape")
        page.locator("#f-texte").fill("Paris")
        assert page.evaluate("D.retenues.filter(a=>appliquer(a,filtres())).every(a=>(a.titre+' '+a.ville).toLowerCase().includes('paris'))")
        page.locator("#f-texte").fill("")
        page.locator("#f-trajet").fill("30")
        assert page.locator("#f-trajet").input_value() == "30"
        # Le simulateur et le formulaire de contact doivent encore s'ouvrir.
        page.locator(".carte button[data-sim]").first.click()
        assert page.locator("#outil-contenu").is_visible()
        page.keyboard.press("Escape")
        for largeur in [320, 390, 768, 1440]:
            page.set_viewport_size({"width": largeur, "height": 900})
            if largeur <= 760:
                page.locator("#volet-filtres").evaluate("e=>e.open=true")
            assert not page.evaluate("document.documentElement.scrollWidth > innerWidth"), f"Débordement à {largeur}px"
        page.set_viewport_size({"width":390,"height":844})
        page.locator("#volet-filtres").evaluate("e=>e.open=false")
        page.evaluate("scrollTo(0,0)")
        assert page.locator(".carte").first.bounding_box()["y"] < 260
        assert not erreurs, erreurs
        browser.close()
    print("Interactions, persistance, simulateur et responsive 320–1440 px : OK")


if __name__ == "__main__":
    main()
