"""QA optionnelle sur le HTML généré : python scripts/verifier_interactions.py.

Nécessite Playwright (pip install playwright) et un Chrome/Chromium installé.
Utilise le navigateur existant ; aucune installation de navigateur automatique.
"""
from pathlib import Path
import shutil

from playwright.sync_api import sync_playwright

RACINE = Path(__file__).resolve().parent.parent


def verifier_exceptions_pepites(browser):
    """Scénarios en mémoire uniquement : le stock réel peut n'avoir aucune pépite."""
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    erreurs = []
    page.on("pageerror", lambda e: erreurs.append(str(e)))
    page.route("**/*", lambda r: r.abort() if r.request.resource_type == "image" else r.continue_())
    page.goto((RACINE / "docs/index.html").as_uri(), wait_until="domcontentloaded")
    assert page.locator("#f-pepites").is_checked()
    page.evaluate("""() => {
      const base = structuredClone(D.retenues[0]);
      const creer = (id, score, surface, trajet, pepite) => ({...structuredClone(base),
        id, titre:id, score, surface_m2:surface, temps_trajet_min:trajet, pepite,
        ville:'Pantin', code_postal:'93500', departement:'93', type_murs:'murs_occupes',
        peut_etre_retiree:false, est_nouvelle:false, negociation:null, recherche:{...structuredClone(base.recherche),score:surface<40?100:30},
        decision:{...structuredClone(base.decision), diagnostic:{occupation:'occupe',bloquant:false,alertes:[]}}
      });
      D.retenues = [creer('petite',70,25,15,false), creer('grande',90,65,45,true),
        creer('limite',85,40,20,true), creer('ordinaire',79,60,15,false),
        creer('estimee',79,60,15,false), creer('retiree',95,65,45,true),
        creer('contradictoire',95,65,45,true)];
      D.retenues.find(a=>a.id==='retiree').peut_etre_retiree=true;
      D.retenues.find(a=>a.id==='contradictoire').decision.diagnostic.bloquant=true;
      const potentiel=creer('potentiel',65,55,45,false);
      potentiel.negociation={statut:'a_negocier',selection:true,prix_plafond:180000,prix_ouverture:174000,
        remise_pct:20,remise_euros:45000,score_cible:82,rendement_cible_pct:8,cashflow_cible:30,stress_cible:-150,
        taxe_estimee:true,taxe_annuelle_retenue:1200,cout_total:194400,apport_reference:38880,pas_euros:1000,
        marge_ouverture_pct:3,hypotheses:{apport_pct:20,taux_pct:3.9,duree_ans:20,vacance_pct:8,charges_pct:10},
        message:'Bonjour, seriez-vous ouverts à une discussion autour de 174 000 € ?'};
      D.retenues.push(potentiel);
      D.encheres=[];
    }""")
    page.locator("#volet-filtres > summary").click()
    page.locator("#f-surface").fill("40")
    page.locator("#f-trajet").fill("30")
    assert page.locator(".carte-img").evaluate_all("els=>els.map(e=>e.dataset.id)") == ["grande", "limite", "potentiel", "petite"]
    assert page.locator(".exception-recherche").count() == 3
    assert "65 m²" in page.locator(".exception-recherche").first.inner_text()
    assert "45 min" in page.locator(".exception-recherche").first.inner_text()
    page.locator('[data-offre="potentiel"]').click()
    assert "174 000" in page.locator("#contact-texte").input_value()
    assert "82/100" in page.locator("#outil-contenu").inner_text()
    page.locator("#outil-contenu details > summary").click()
    assert "provisionnée" in page.locator("#outil-contenu").inner_text()
    for largeur in [320, 390, 1440]:
        page.set_viewport_size({"width":largeur,"height":844})
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
    page.keyboard.press("Escape")
    page.locator("#f-signal").select_option("negociation")
    assert page.locator(".carte-img").evaluate_all("els=>els.map(e=>e.dataset.id)") == ["potentiel"]
    page.locator("#f-signal").select_option("tous")
    # Une préférence souple ne contourne pas une recherche explicite.
    page.locator("#f-texte").fill("petite")
    assert page.locator(".carte").count() == 1
    page.locator("#f-texte").fill("")
    page.locator("#f-nouv").check()
    assert page.locator(".carte").count() == 0
    page.locator("#f-nouv").uncheck()
    page.locator("#f-type").select_option("murs_libres")
    assert page.locator(".carte").count() == 0
    page.locator("#f-type").select_option("tous")
    page.evaluate("masquees.push('grande'); rendre()")
    assert page.locator('.carte-img[data-id="grande"]').count() == 0
    page.evaluate("masquees=[]; rendre()")
    for largeur in [320, 390, 768]:
        page.set_viewport_size({"width":largeur,"height":844})
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
    page.locator("#f-pepites").uncheck()
    assert page.locator(".carte-img").evaluate_all("els=>els.map(e=>e.dataset.id)") == ["petite"]
    page.reload(wait_until="domcontentloaded")
    assert not page.locator("#f-pepites").is_checked()
    assert page.locator("#f-surface").input_value() == "40"
    assert not erreurs, erreurs
    page.close()


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
        assert page.evaluate("D.retenues.filter(a=>appliquer(a,filtres())).every(a=>a.surface_m2<25 || estPepite(a) || estPotentiel(a))")
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
        page.locator("#f-pepites").uncheck()
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
        verifier_exceptions_pepites(browser)
        browser.close()
    print("Interactions, persistance, simulateur et responsive 320–1440 px : OK")


if __name__ == "__main__":
    main()
