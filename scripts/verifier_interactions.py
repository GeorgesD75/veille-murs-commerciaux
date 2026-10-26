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
        prix:200000,honoraires:0,loyer_mensuel:1800,loyer_estime:false,taxe_fonciere_annuelle:0,
        ville:'Pantin', code_postal:'93500', departement:'93', type_murs:'murs_occupes',
        peut_etre_retiree:false, est_nouvelle:false, negociation:null, recherche:{...structuredClone(base.recherche),score:surface<40?100:30},
        decision:{...structuredClone(base.decision), relocation:{niveau:'a_verifier',favorables:[],vigilances:[],a_confirmer:['Adresse et passage']}, diagnostic:{occupation:'occupe',bloquant:false,alertes:[]}}
      });
      D.retenues = [creer('petite',70,25,15,false), creer('grande',90,65,45,true),
        creer('limite',85,40,20,true), creer('ordinaire',79,60,15,false),
        creer('estimee',79,60,15,false), creer('retiree',95,65,45,true),
        creer('contradictoire',95,65,45,true)];
      D.retenues.find(a=>a.id==='retiree').peut_etre_retiree=true;
      D.retenues.find(a=>a.id==='contradictoire').decision.diagnostic.bloquant=true;
      const potentiel=creer('potentiel',65,55,45,false);
      potentiel.negociation={statut:'a_negocier',selection:true,prix_plafond:180000,prix_ouverture:174000,
        remise_pct:20,remise_euros:45000,score_cible:82,rendement_cible_pct:8,cashflow_cible:130,stress_cible:-150,
        taxe_estimee:true,taxe_annuelle_retenue:1200,cout_total:194400,apport_reference:38880,pas_euros:1000,
        marge_ouverture_pct:3,hypotheses:{apport_pct:20,taux_pct:3.9,duree_ans:20,vacance_pct:8,charges_pct:10},
        message:'Bonjour, seriez-vous ouverts à une discussion autour de 174 000 € ?'};
      D.retenues.push(potentiel);
      const mieuxNote=creer('mieux-note',79,30,15,false);
      mieuxNote.recherche.score=1; // le score actuel prime sur l'adéquation
      D.retenues.push(mieuxNote);
      D.encheres=[];
    }""")
    page.locator("#volet-filtres > summary").click()
    page.locator("#f-surface").fill("40")
    page.locator("#f-trajet").fill("30")
    assert page.locator(".carte-img").evaluate_all("els=>els.map(e=>e.dataset.id)") == ["grande", "limite", "potentiel", "mieux-note", "petite"]
    assert page.locator("#bloc-prio .carte-img").evaluate_all("els=>els.map(e=>e.dataset.id)") == ["grande", "limite", "potentiel"]
    assert page.locator("#bloc-etudier .carte-img").evaluate_all("els=>els.map(e=>e.dataset.id)") == ["mieux-note", "petite"]
    page.locator("#f-tri").select_option("score")
    assert page.locator(".carte-img").evaluate_all("els=>els.map(e=>e.dataset.id)") == ["grande", "limite", "mieux-note", "petite", "potentiel"]
    page.locator("#f-tri").select_option("recherche")
    cible = page.locator('.carte:has(.carte-img[data-id="potentiel"]) .offre-cible')
    texte_cible = cible.inner_text().replace("\u202f", " ").replace("\u00a0", " ")
    assert "180 000" in texte_cible and "maximum" in texte_cible
    assert "82/100 simulés" in cible.inner_text() and "actuel : 65/100" in cible.inner_text()
    assert "+130" in cible.inner_text() and "20 % d’apport" in cible.inner_text()
    page.evaluate("window.profilTest=structuredClone(profil); Object.assign(profil,{apport:0,taux:20}); rendre()")
    assert page.locator('#bloc-prio .carte-img[data-id="potentiel"]').count() == 0
    assert "Ce plafond ne suffit pas" in cible.inner_text()
    page.evaluate("Object.assign(profil,window.profilTest); rendre()")
    page.evaluate("D.retenues.find(a=>a.id==='potentiel').negociation.cashflow_cible=0; rendre()")
    assert page.locator('#bloc-prio .carte-img[data-id="potentiel"]').count() == 0
    page.evaluate("D.retenues.find(a=>a.id==='potentiel').negociation.cashflow_cible=130; rendre()")
    page.evaluate("D.retenues.find(a=>a.id==='potentiel').decision.relocation.niveau='vigilance'; rendre()")
    assert page.locator('#bloc-prio .carte-img[data-id="potentiel"]').count() == 0
    page.evaluate("D.retenues.find(a=>a.id==='potentiel').decision.relocation.niveau='a_verifier'; rendre()")
    # Le même signal commande l'urgence et le dépliage. Scénarios temporaires,
    # sans modifier le stock publié ni les scénarios de filtrage ci-dessous.
    page.evaluate("D.retenues.forEach(a=>a.est_nouvelle=true); rendre()")
    urgente = page.locator('.carte:has(.carte-img[data-id="grande"])')
    assert urgente.locator(".analyse-annonce").evaluate("e=>e.open")
    assert "Contact prioritaire" in urgente.locator(".analyse-annonce > summary").inner_text()
    assert "Contactez le vendeur en priorité" in urgente.locator(".questions-reponses").text_content()
    assert not page.locator('.carte:has(.carte-img[data-id="potentiel"]) .analyse-annonce').evaluate("e=>e.open")
    assert not page.locator('.carte:has(.carte-img[data-id="mieux-note"]) .analyse-annonce').evaluate("e=>e.open")
    assert page.evaluate("['retiree','contradictoire'].every(id=>!contactPrioritaire(D.retenues.find(a=>a.id===id)))")
    urgente.locator(".analyse-annonce > summary").click()
    assert not urgente.locator(".analyse-annonce").evaluate("e=>e.open")
    urgente.locator(".analyse-annonce > summary").click()
    assert urgente.locator(".analyse-contenu").is_visible()
    for statut in ["contactee", "visite_prevue", "visitee", "offre_faite", "abandonnee"]:
        page.evaluate("statut=>{suivi.grande={statut}; rendre()}", statut)
        assert page.evaluate("!contactPrioritaire(D.retenues.find(a=>a.id==='grande'))")
        if statut != "abandonnee":
            assert not urgente.locator(".analyse-annonce").evaluate("e=>e.open")
    page.evaluate("suivi.grande={statut:'suivie'}; rendre()")
    assert urgente.locator(".analyse-annonce").evaluate("e=>e.open")
    page.evaluate("delete suivi.grande; D.retenues.forEach(a=>a.est_nouvelle=false); rendre()")
    assert not urgente.locator(".analyse-annonce").evaluate("e=>e.open")
    assert "82/100" in page.locator('.carte:has([data-offre="potentiel"]) .offre-cible').inner_text()
    assert page.locator(".exception-recherche").count() == 3
    assert "65 m²" in page.locator(".exception-recherche").first.inner_text()
    assert "45 min" in page.locator(".exception-recherche").first.inner_text()
    page.locator('[data-offre="potentiel"]').click()
    assert "174 000" in page.locator("#contact-texte").input_value()
    assert "82/100" in page.locator("#outil-contenu").inner_text()
    page.locator("#outil-contenu details > summary").filter(has_text="Comprendre le calcul").click()
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
    assert page.locator(".carte-img").evaluate_all("els=>els.map(e=>e.dataset.id)") == ["mieux-note", "petite"]
    page.reload(wait_until="domcontentloaded")
    assert not page.locator("#f-pepites").is_checked()
    assert page.locator("#f-surface").input_value() == "40"
    assert not erreurs, erreurs
    page.close()


def verifier_financement_et_brouillons(browser):
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    erreurs = []
    page.on("pageerror", lambda e: erreurs.append(str(e)))
    page.route("**/*", lambda r: r.abort() if r.request.resource_type == "image" else r.continue_())
    page.goto((RACINE / "docs/index.html").as_uri(), wait_until="domcontentloaded")
    identifiant = page.evaluate("D.retenues[0].id")
    page.evaluate("id=>ouvrirContact(id)", identifiant)
    modele = page.locator("#contact-texte").input_value()
    personnalise = "Bonjour,\nMon créneau : vendredi à 14 h. <Texte personnel>"
    page.locator("#contact-texte").fill(personnalise)
    page.locator("[data-contact-mode=dossier]").click()
    page.locator("#contact-texte").fill("Merci de joindre le bail et le plan coté.")
    page.locator("[data-contact-mode=court]").click()
    assert page.locator("#contact-texte").input_value() == personnalise
    page.keyboard.press("Escape")
    page.reload(wait_until="domcontentloaded")
    page.evaluate("id=>ouvrirContact(id)", identifiant)
    assert page.locator("#contact-texte").input_value() == personnalise
    assert page.locator("[data-contact-mode=court]").get_attribute("aria-pressed") == "true"
    page.evaluate("ouvrirContact(D.retenues[1].id)")
    assert page.locator("#contact-texte").input_value() != personnalise
    page.evaluate("id=>ouvrirContact(id)", identifiant)
    page.locator("#contact-modele").click()
    assert page.locator("#contact-texte").input_value() == modele
    page.locator("[data-contact-mode=dossier]").click()
    assert page.locator("#contact-texte").input_value() == "Merci de joindre le bail et le plan coté."
    page.locator("#contact-texte").fill("")
    page.keyboard.press("Escape")
    page.evaluate("id=>ouvrirContact(id)", identifiant)
    assert page.locator("#contact-texte").input_value() == ""
    assert page.evaluate("Object.keys(suivi).length===0")  # écrire/copier n'est pas envoyer
    page.keyboard.press("Escape")

    # Confrontation des deux moteurs sur les données réelles, sans arrondi caché.
    assert page.evaluate("""() => D.retenues.filter(a=>a.decision.revenu_prudent!=null).every(a=>{
      const e=exploitation(a), d=a.decision;
      return Math.abs(e.revenu-d.revenu_prudent)<1e-6 && Math.abs(e.stress-d.revenu_stress)<1e-6
        && Math.abs(e.taxe-d.taxe_annuelle_retenue)<1e-6;
    })""")
    page.evaluate("""() => {
      const a=structuredClone(D.retenues[0]);
      Object.assign(a,{id:'finance-test',prix:200000,honoraires:10000,loyer_mensuel:1500,
        loyer_mensuel_estime:null,loyer_estime:false,taxe_fonciere_annuelle:null,
        surface_m2:30,temps_trajet_min:15,score:65,pepite:false,peut_etre_retiree:false});
      a.decision.diagnostic.bloquant=false;
      a.negociation={prix_plafond:180000,message:'Bonjour, échangeons sur le prix.',
        hypotheses:{apport_pct:20,duree_ans:20,taux_pct:0,vacance_pct:8,charges_pct:10}};
      D.retenues=[a];
      Object.assign(profil,{apportMode:'pct',apport:20,taux:0,duree:20});
      ouvrirSimulateur(a.id);
    }""")
    assert page.evaluate("cashflowMensuel(D.retenues[0])") == 352
    assert "352" in page.locator(".sim-bilan").inner_text()
    assert "NaN" not in page.locator("#outil-contenu").inner_text()
    page.locator("#sim-hypotheses > summary").click()
    page.locator('[data-sim-champ="taxe"]').fill("0")
    page.locator('[data-sim-champ="taxe"]').press("Tab")
    assert page.locator("#sim-hypotheses").evaluate("e=>e.open")
    assert "477" in page.locator(".sim-bilan").inner_text()
    page.locator('[data-sim-champ="loyer"]').fill("0")
    page.locator('[data-sim-champ="loyer"]').press("Tab")
    assert page.evaluate("simEtat.loyer") == 0
    page.locator('[data-sim-champ="charges"]').fill("99")
    page.locator('[data-sim-champ="charges"]').press("Tab")
    assert page.evaluate("simEtat.charges") == 10
    page.locator('[data-sim-champ="charges"]').fill("10")
    page.locator('[data-sim-champ="charges"]').press("Tab")
    assert page.evaluate("D.retenues[0].loyer_mensuel===1500 && D.retenues[0].taxe_fonciere_annuelle===null && D.retenues[0].score===65")
    for largeur in [320, 390, 768, 1440]:
        page.set_viewport_size({"width": largeur, "height": 844})
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
    page.evaluate("ouvrirSimulateur('finance-test',180000)")
    assert page.locator('[data-sim-champ="prix"]').input_value() == "180000"
    # Le brouillon chiffré reste distinct des étapes de prise de contact.
    page.evaluate("""() => {
      const a=D.retenues[0];
      a.negociation.hypotheses={apport_pct:20,duree_ans:20,taux_pct:0,vacance_pct:8,charges_pct:10};
      ouvrirProposition(a.id);
    }""")
    page.locator("#contact-texte").fill("Ma discussion personnalisée à 180 000 euros.")
    page.keyboard.press("Escape")
    page.evaluate("ouvrirProposition('finance-test')")
    assert page.locator("#contact-texte").input_value() == "Ma discussion personnalisée à 180 000 euros."
    page.locator('[data-sim-prix="180000"]').click()
    assert page.locator('[data-sim-champ="prix"]').input_value() == "180000"
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
        assert page.locator(".carte").first.bounding_box()["y"] < 290
        assert page.locator("#bloc-prio .carte .carte-img, #bloc-etudier .carte .carte-img").evaluate_all(
            "els=>els.every(e=>D.retenues.find(a=>a.id===e.dataset.id).decision.diagnostic.transaction.nature==='murs')")
        assert page.locator(".carte").first.evaluate("e=>e.querySelector('.analyse-annonce').open === contactPrioritaire(D.retenues.find(a=>a.id===e.querySelector('.carte-img').dataset.id))")
        page.locator(".analyse-annonce").first.evaluate("e=>e.open=true")
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
        assert page.locator(".carte").first.bounding_box()["y"] < 280
        assert not erreurs, erreurs
        verifier_exceptions_pepites(browser)
        verifier_financement_et_brouillons(browser)
        browser.close()
    print("Interactions, persistance, simulateur et responsive 320–1440 px : OK")


if __name__ == "__main__":
    main()
