/* Les réponses restent dans le navigateur ; aucun texte n'est envoyé. */
const CLE_REPONSES = "veille-murs-reponses-v1";
const CLE_REPONSE_SELECTION = "veille-murs-reponse-selection";
let dossiersReponses = {}, reponseSelectionnee = "";
try {
  const donnees = JSON.parse(localStorage.getItem(CLE_REPONSES) || "{}");
  if (donnees && typeof donnees === "object" && !Array.isArray(donnees)) dossiersReponses = donnees;
  reponseSelectionnee = localStorage.getItem(CLE_REPONSE_SELECTION) || "";
} catch (e) {}
const CHAMPS_REPONSE = [
  {cle:"nature", label:"Ce qui est vendu", choix:[["","À confirmer"],["murs","Murs seuls"],["fonds","Fonds de commerce"],["bail","Droit au bail"],["mixte","Murs et fonds"],["location","Location"]]},
  {cle:"occupation", label:"À la vente, le local est…", choix:[["","À confirmer"],["loue","Loué"],["libre","Libre"]]},
  {cle:"loyer", label:"Loyer global déclaré (€)", nombre:true},
  {cle:"periode_loyer", label:"Période de ce loyer", choix:[["","Non précisée"],["mois","Par mois"],["an","Par an"]]},
  {cle:"base_loyer", label:"Base du loyer", choix:[["","À confirmer"],["ht_hc","HT et hors charges"],["autre","TTC / charges comprises"],["estime","Loyer estimé ou potentiel"]]},
  {cle:"bail", label:"Bail : début, durée ou prochaine échéance", placeholder:"Ex. depuis juin 2022, prochaine échéance juin 2028"},
  {cle:"impayes", label:"Impayés / retards récents", choix:[["","Pas de réponse"],["non","Aucun selon le vendeur"],["oui","Oui, à clarifier"]]},
  {cle:"charges", label:"Charges déclarées (€)", nombre:true},
  {cle:"periode_charges", label:"Période de ces charges", choix:[["","Non précisée"],["an","Par an"],["mois","Par mois"]]},
  {cle:"charges_nature", label:"Charges restant au propriétaire ?", choix:[["","Répartition à confirmer"],["bailleur","Oui, montant bailleur"],["autre","Montant total / charges locataire"]]},
  {cle:"taxe_comprise", label:"Taxe foncière dans ces charges ?", choix:[["","À préciser"],["oui","Comprise"],["non","À part"]]},
];
const COMPLEMENTS_REPONSE = [
  {cle:"depart", label:"Départ du locataire annoncé ?", choix:[["","Non précisé"],["oui","Oui, à anticiper"],["non","Non selon le vendeur"]]},
  {cle:"prix", label:"Nouveau prix indiqué (€), sinon prix de l’annonce", nombre:true},
  {cle:"prix_base", label:"Base de ce prix", choix:[["","À confirmer"],["inclus","Honoraires inclus"],["net","Net vendeur / hors honoraires"]]},
  {cle:"taxe", label:"Taxe foncière précisée (€)", nombre:true},
  {cle:"periode_taxe", label:"Période de la taxe", choix:[["","Non précisée"],["an","Par an"],["mois","Par mois"]]},
];
const LIBELLES_REPONSE = Object.fromEntries([...CHAMPS_REPONSE,...COMPLEMENTS_REPONSE].map(c=>[c.cle,c.label]));
function urlReponse(url) {
  try { const u = new URL(url); return ["http:","https:"].includes(u.protocol) ? u.href : "#"; } catch (e) { return "#"; }
}
function sauvegarderReponses() {
  try {
    localStorage.setItem(CLE_REPONSES, JSON.stringify(dossiersReponses));
    localStorage.setItem(CLE_REPONSE_SELECTION, reponseSelectionnee);
    return true;
  } catch (e) { return false; }
}
function statutSauvegardeReponse(ok) {
  const el = document.getElementById("rep-enregistrement");
  if (el) el.textContent = ok ? "Enregistré sur cet appareil." : "Conservé en mémoire : stockage local indisponible. Exportez le dossier pour le garder.";
}
function annonceReponse(id) {
  return D.retenues.find(a=>a.id===id) || dossiersReponses[id]?.instantane;
}
function choisirReponse(id) {
  const a = annonceReponse(id);
  if (!a) return;
  reponseSelectionnee = id;
  if (!dossiersReponses[id]) {
    const instantane = Object.fromEntries(["id","titre","url","ville","prix","surface_m2","honoraires","loyer_mensuel","loyer_estime","score","flags","decision","peut_etre_retiree"].map(c=>[c,a[c]]));
    dossiersReponses[id] = {texte:"", champs:{}, corrections:{}, lecture:null, confirme:false, aRelire:false, instantane, maj:new Date().toISOString()};
  }
  const ok = sauvegarderReponses();
  rafraichirChoixReponse();
  document.getElementById("rep-association").open = false;
  rendreDossierReponse();
  statutSauvegardeReponse(ok);
}
function ouvrirReponse(id) {
  document.getElementById("outil-fond").style.display = "none";
  basculerVue("reponses");
  choisirReponse(id);
  document.getElementById("rep-texte")?.focus();
}
function rafraichirChoixReponse() {
  const select = document.getElementById("rep-annonce");
  if (!select) return;
  const normaliser = t=>String(t||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase();
  const texte = normaliser(document.getElementById("rep-recherche").value);
  const annonces = new Map(D.retenues.map(a=>[a.id,a]));
  for (const [id,r] of Object.entries(dossiersReponses)) if (!annonces.has(id) && r.instantane) annonces.set(id,r.instantane);
  const eligibles = [...annonces.values()].filter(a=>normaliser(`${a.titre} ${a.ville} ${a.id} ${a.url}`).includes(texte));
  eligibles.sort((a,b)=>Number(!!dossiersReponses[b.id])-Number(!!dossiersReponses[a.id]) || Number(!!suivi[b.id])-Number(!!suivi[a.id]) || (b.score||0)-(a.score||0));
  const lot = eligibles.slice(0,80);
  const courante = annonceReponse(reponseSelectionnee);
  if (courante && !lot.some(a=>a.id===courante.id)) lot.unshift(courante);
  select.innerHTML = '<option value="">Choisir une annonce…</option>' + lot.map(a=>`<option value="${ech(a.id)}"${a.id===reponseSelectionnee?" selected":""}>${dossiersReponses[a.id]?"● ":""}${ech(a.titre)} — ${ech(a.ville)} · ${fmtEuros(a.prix)}</option>`).join("");
  document.getElementById("rep-choix-note").textContent = `${eligibles.length} annonce(s) trouvée(s)${eligibles.length>80?" · affinez la recherche pour voir les suivantes":""}. ● = dossier déjà ouvert.`;
}
function rendreReponses() {
  const cible = document.getElementById("reponses-contenu");
  cible.innerHTML = `<h2 class="section">Réponses des vendeurs</h2>
    <p class="rep-intro">Associez sa réponse à une annonce, vérifiez les informations lues, puis examinez les chiffres. Tout reste sur cet appareil.</p>
    <details id="rep-association"${annonceReponse(reponseSelectionnee)?"":" open"}><summary>Choisir ou changer d’annonce</summary><div class="rep-choix">
      <label>Rechercher une annonce<input id="rep-recherche" type="search" placeholder="Ville, titre, lien ou référence"></label>
      <label>Annonce concernée<select id="rep-annonce"></select></label>
    </div><p id="rep-choix-note" class="rep-note"></p></details>
    <div id="rep-dossier"></div>
    <div class="rep-sauvegarde"><button type="button" class="btn-outil" data-rep-action="exporter">Exporter mes réponses</button>
      <label class="btn-outil rep-import">Importer une sauvegarde<input id="rep-importer" type="file" accept="application/json,.json"></label>
      <span id="rep-import-statut" role="status"></span></div>`;
  rafraichirChoixReponse();
  if (annonceReponse(reponseSelectionnee)) rendreDossierReponse();
  else document.getElementById("rep-dossier").innerHTML = '<div class="note-vide">Choisissez une annonce ou utilisez « Analyser sa réponse » depuis la fenêtre de contact.</div>';
}
function champReponseHtml(champ, dossier) {
  const valeur = dossier.champs?.[champ.cle] ?? "";
  return `<label>${ech(champ.label)}${champ.choix
    ? `<select data-rep-champ="${champ.cle}">${champ.choix.map(([v,t])=>`<option value="${v}"${valeur===v?" selected":""}>${ech(t)}</option>`).join("")}</select>`
    : `<input data-rep-champ="${champ.cle}" type="${champ.nombre?"number":"text"}"${champ.nombre?' min="0" max="1000000000000" step="any"':' maxlength="220"'} value="${ech(String(valeur))}" placeholder="${ech(champ.placeholder||"Non précisé")}">`}</label>`;
}
function rendreDossierReponse() {
  const id = reponseSelectionnee, r = dossiersReponses[id], a = annonceReponse(id);
  if (!r || !a) return;
  document.getElementById("rep-dossier").innerHTML = `<article class="rep-dossier">
    <div class="rep-entete"><div><h3>${ech(a.titre)}</h3><p>${ech(a.ville)}${a.surface_m2?` · ${ech(String(a.surface_m2))} m²`:""} · annonce à ${fmtEuros(a.prix)} · <a href="${ech(urlReponse(a.url))}" target="_blank" rel="noopener">Ouvrir l’annonce</a></p></div>
      ${r.lecture && !r.aRelire?'<button type="button" class="btn-outil" data-rep-action="ajouter">Ajouter une réponse</button>':""}</div>
    ${!D.retenues.some(x=>x.id===id)?'<p class="alerte-donnee">Annonce absente du stock actuel : analyse sur l’instantané conservé, disponibilité à reconfirmer.</p>':""}
    <label for="rep-texte">${r.historique?.length?"Réponse complémentaire · les informations des échanges précédents sont conservées":"La réponse reçue"}</label>
    <textarea id="rep-texte" class="contact-texte" rows="7" maxlength="20000" placeholder="Collez ici uniquement la réponse du vendeur, sans le fil de vos anciennes questions.">${ech(r.texte)}</textarea>
    <div class="contact-actions"><button type="button" class="btn-outil rep-principal" data-rep-action="extraire">${r.lecture?"Relire le texte et réinitialiser les champs":"Analyser la réponse"}</button>
      <button type="button" class="btn-outil" data-rep-action="manuel">Renseigner les chiffres moi-même</button></div>
    <p id="rep-enregistrement" class="rep-note" role="status"></p>
    <div id="rep-analyse" aria-live="polite"></div>
    <div id="rep-informations"></div>
    ${r.historique?.length?`<details class="rep-preuves"><summary>Échanges précédents (${r.historique.length} conservés, 10 derniers maximum)</summary>${r.historique.map(h=>`<p class="rep-note">Enregistré le ${ech(fmtDate(h.maj))}</p><blockquote class="rep-message">${ech(h.texte)}</blockquote>`).join("")}</details>`:""}
  </article>`;
  if (r.lecture) rendreInformationsReponse();
  rendreAnalyseReponse();
}
function rendreInformationsReponse() {
  const r = dossiersReponses[reponseSelectionnee];
  if (!r) return;
  const lecture = r.lecture || {extraits:{}, conflits:[], alertes:[]};
  const preuves = Object.entries(lecture.extraits || {});
  document.getElementById("rep-informations").innerHTML = `<details class="rep-informations"${!r.confirme?' open':""}>
    <summary>Vérifier les informations retenues</summary>
    <p class="rep-note">Un champ vide signifie « inconnu ». Vérifiez surtout les périodes, la base HT/HC et les charges bailleur. Vos corrections restent distinctes du stock d’annonces.</p>
    <div class="rep-champs">${CHAMPS_REPONSE.map(c=>champReponseHtml(c,r)).join("")}</div>
    <details class="rep-complements"><summary>Prix et taxe foncière, si précisés</summary><div class="rep-champs">${COMPLEMENTS_REPONSE.map(c=>champReponseHtml(c,r)).join("")}</div></details>
    ${preuves.length?`<details class="rep-preuves"><summary>Extraits des échanges utilisés (${preuves.length})</summary><ul>${preuves.map(([c,t])=>`<li><b>${ech(LIBELLES_REPONSE[c]||c)} :</b> « ${ech(t)} »${r.corrections?.[c]?" — valeur corrigée manuellement":""}</li>`).join("")}</ul></details>`:""}
    <button type="button" class="btn-outil rep-principal" data-rep-action="valider">Valider ces données et recalculer</button>
  </details>`;
}
function calculerDossierReponse(r, a) {
  const resultat = ReponsesVendeur.analyser(r.champs,a,profil,D,r.confirme);
  const conflits = (r.lecture?.conflits||[]).filter(c=>!r.corrections?.[c.champ]);
  if (conflits.length) {
    resultat.niveau = "a_clarifier";
    resultat.titre = "Plusieurs valeurs à départager dans la réponse";
    resultat.risques.push(...conflits.map(c=>`${LIBELLES_REPONSE[c.champ]||c.champ} : ${c.propositions.map(v=>v.valeur).join(" / ")}. Choisissez la bonne valeur dans les champs.`));
  }
  return resultat;
}
function rendreAnalyseReponse() {
  const r = dossiersReponses[reponseSelectionnee], a = annonceReponse(reponseSelectionnee), cible = document.getElementById("rep-analyse");
  if (!r || !a || !cible) return;
  if (r.aRelire) { cible.innerHTML = '<p class="alerte-donnee">Texte modifié : relancez la lecture pour actualiser les informations et l’analyse.</p>'; return; }
  if (!r.lecture) { cible.innerHTML = ""; return; }
  const resultat = calculerDossierReponse(r,a), f = resultat.finance;
  const signe = v=>`${v>=0?"+":"−"}${fmtEuros(Math.abs(v))}`;
  const financierFiable = r.confirme && ["interessant","a_negocier"].includes(resultat.niveau) && !resultat.manquants.length;
  cible.innerHTML = `<section class="rep-resultat ${r.confirme?resultat.niveau:"provisoire"}">
    <p class="rep-etat">${r.confirme?"Données relues par vous · déclarations du vendeur, pièces non vérifiées":"Lecture provisoire · vérifiez les champs avant de retenir le résultat"}</p>
    <h3>${ech(resultat.titre)}</h3>
    ${[...(r.lecture.alertes||[]),...resultat.risques].map(t=>`<p class="alerte-donnee fort">${ech(t)}</p>`).join("")}
    ${f?`<div class="rep-bilan"><div><span>Prudent · votre financement</span><b>${signe(f.cashflow)}/mois</b></div><div><span>Scénario dégradé</span><b>${signe(f.stress)}/mois</b></div></div>
      <p class="rep-note">${financierFiable?"Calcul sur les chiffres retenus":"Simulation indicative : les inconnues ou risques empêchent de conclure"}. Avant impôt, assurance emprunteur et travaux exceptionnels.</p>
      ${financierFiable && f.prixCible?`<p class="rep-prix">Pour viser +${fmtEuros(f.objectif)}/mois : <b>${fmtEuros(f.prixCible)} maximum</b> au financement actuel.</p><p class="rep-note">Seuil financier, sans nouveau score pépite. Demande locative, bail, pièces et accord du vendeur restent à qualifier.</p>`:""}
      <details class="rep-calcul"><summary>Hypothèses et comparaison avec l’annonce</summary>
        <p>Prix retenu ${fmtEuros(f.prix)} (${f.prixVendeur?"réponse du vendeur":"annonce"}), plus ${fmtEuros(f.honoraires)} d’honoraires séparés connus et 8 % de frais d’acquisition.
        Apport ${fmtEuros(f.apportEuros)}, prêt sur ${f.duree} ans à ${fmtPct(f.taux)}, mensualité ${fmtEuros(Math.round(f.mensualite))}.</p>
        <p>Loyer retenu ${fmtEuros(f.loyer)}/mois HT/HC${a.loyer_mensuel!=null?` (annonce : ${fmtEuros(a.loyer_mensuel)}/mois)`:""}. Vacance : ${fmtPct(f.vacancePct)}.
        Budget charges et taxe retenu : ${fmtEuros(Math.round(f.fraisMensuels))}/mois ; le maximum des charges déclarées et de la provision d’entretien/gestion est conservé.
        ${f.chargesComprises?"Les charges annoncées taxe comprise ne sont pas additionnées une deuxième fois à la taxe.":"La taxe est déduite à part."}</p>
        <p>Taxe ${f.taxeEstimee?"provisionnée faute de montant connu":"déclarée"} : ${fmtEuros(f.taxe)}/an. Provision entretien/gestion/charges : au moins ${fmtPct(f.chargesPct)} du loyer.
        Stress : loyer −10 %, au moins deux mois sans loyer, mêmes montants de charges fixes. Le score de la chasse n’est pas modifié.</p>
      </details>`:""}
    ${resultat.manquants.length?`<div class="rep-manquants"><b>À obtenir pour décider</b><ul>${resultat.manquants.map(m=>`<li>${ech(m.texte)}</li>`).join("")}</ul></div>`:""}
    ${resultat.points.map(t=>`<p class="rep-note">${ech(t)}</p>`).join("")}
    ${resultat.relance?`<details class="rep-relance"><summary>Une relance courte sur ce qui manque</summary><p class="rep-note">Trois questions maximum ; les autres points à éclaircir restent listés ci-dessus.</p><textarea id="rep-relance" class="contact-texte" rows="8">${ech(r.relance?.modele===resultat.relance?r.relance.texte:resultat.relance)}</textarea><button type="button" class="btn-outil" data-rep-action="copier">Copier cette relance</button><span id="rep-copie" role="status"></span></details>`:""}
  </section>`;
}
document.addEventListener("input", ev=>{
  if (ev.target.id === "rep-recherche") { rafraichirChoixReponse(); return; }
  const r = dossiersReponses[reponseSelectionnee];
  if (!r) return;
  if (ev.target.id === "rep-relance") {
    r.relance={modele:calculerDossierReponse(r,annonceReponse(reponseSelectionnee)).relance,texte:ev.target.value};
    statutSauvegardeReponse(sauvegarderReponses()); return;
  }
  if (ev.target.id === "rep-texte") {
    r.texte = ev.target.value; r.aRelire = !!r.lecture; r.confirme = false;
  } else if (ev.target.matches("[data-rep-champ]")) {
    const cle = ev.target.dataset.repChamp;
    r.champs[cle] = ev.target.value; (r.corrections ||= {})[cle] = true; r.confirme = false;
  } else return;
  r.maj = new Date().toISOString();
  statutSauvegardeReponse(sauvegarderReponses());
  rendreAnalyseReponse();
});
document.addEventListener("change", async ev=>{
  if (ev.target.id === "rep-annonce") choisirReponse(ev.target.value);
  if (ev.target.id !== "rep-importer" || !ev.target.files?.[0]) return;
  const statut = document.getElementById("rep-import-statut"), fichier = ev.target.files[0];
  try {
    if (fichier.size > 1500000) throw new Error("Fichier trop volumineux (maximum 1,5 Mo).");
    const contenu = JSON.parse(await fichier.text());
    if (contenu.version !== 1 || !contenu.dossiers || typeof contenu.dossiers !== "object" || Array.isArray(contenu.dossiers)) throw new Error("Format de sauvegarde non reconnu.");
    const entrees = Object.entries(contenu.dossiers);
    if (entrees.length > 300) throw new Error("Trop de dossiers dans ce fichier.");
    let total = 0;
    for (const [id, r] of entrees) {
      if (!/^[a-zA-Z0-9_-]{1,100}$/.test(id) || ["__proto__","constructor","prototype"].includes(id) || !r || r.instantane?.id !== id || typeof r.texte !== "string" || r.texte.length>20000) continue;
      // Une importation ne remplace pas un dossier déjà présent sur cet appareil.
      if (Object.hasOwn(dossiersReponses,id)) continue;
      const champs = {};
      for (const c of [...CHAMPS_REPONSE,...COMPLEMENTS_REPONSE]) {
        const v = r.champs?.[c.cle];
        if (c.choix && c.choix.some(([cle])=>cle===v)) champs[c.cle]=v;
        else if (c.nombre && ReponsesVendeur.nombre(v)!=null) champs[c.cle]=ReponsesVendeur.nombre(v);
        else if (!c.choix && !c.nombre && typeof v==="string") champs[c.cle]=v.slice(0,220);
      }
      const historique = Array.isArray(r.historique) ? r.historique.slice(-10).filter(h=>h && typeof h.texte==="string" && h.texte.length<=20000).map(h=>({texte:h.texte,maj:typeof h.maj==="string"?h.maj:""})) : [];
      dossiersReponses[id] = {texte:r.texte, champs, corrections:{}, lecture:{extraits:{},conflits:[],alertes:[]}, historique,
        base:historique.length?{champs:{...champs},extraits:{},conflits:[],corrections:{}}:null,
        relance:typeof r.relance?.modele==="string" && typeof r.relance?.texte==="string"?{modele:r.relance.modele.slice(0,5000),texte:r.relance.texte.slice(0,10000)}:null,
        confirme:false, aRelire:false, instantane:r.instantane, maj:new Date().toISOString()};
      total++;
    }
    const ok = sauvegarderReponses();
    statut.textContent = `${total} dossier(s) importé(s), à relire. Les dossiers déjà présents sont conservés.${ok?"":" Stockage indisponible : conservez la sauvegarde."}`;
    rafraichirChoixReponse();
  } catch (e) { statut.textContent = e.message; }
  ev.target.value = "";
});
document.addEventListener("click", async ev=>{
  const lien = ev.target.closest("[data-reponse-vendeur]");
  if (lien) { ouvrirReponse(lien.dataset.reponseVendeur); return; }
  const bouton = ev.target.closest("[data-rep-action]");
  if (!bouton) return;
  const action = bouton.dataset.repAction;
  if (action === "exporter") {
    const url = URL.createObjectURL(new Blob([JSON.stringify({version:1,exporteLe:new Date().toISOString(),dossiers:dossiersReponses},null,2)],{type:"application/json"}));
    const a = document.createElement("a"); a.href=url; a.download=`mes-reponses-vendeurs-${new Date().toISOString().slice(0,10)}.json`; a.click(); setTimeout(()=>URL.revokeObjectURL(url),1000); return;
  }
  const r = dossiersReponses[reponseSelectionnee];
  if (!r) return;
  if (action === "ajouter") {
    if (!r.lecture || r.aRelire || !r.texte.trim()) return;
    r.historique=[...(r.historique||[]),{texte:r.texte,maj:r.maj}].slice(-10);
    r.base={champs:{...r.champs},extraits:{...r.lecture.extraits},conflits:(r.lecture.conflits||[]).filter(c=>!r.corrections?.[c.champ]),corrections:{...r.corrections}};
    r.texte=""; r.aRelire=true; r.confirme=false; r.maj=new Date().toISOString();
    const ok=sauvegarderReponses(); rendreDossierReponse(); statutSauvegardeReponse(ok); document.getElementById("rep-texte").focus(); return;
  }
  if (action === "extraire" || action === "manuel") {
    if (action === "manuel" && r.lecture && !r.aRelire) {
      document.querySelector(".rep-informations").open=true;
      document.querySelector("[data-rep-champ]").focus(); return;
    }
    if (action === "extraire" && !r.texte.trim()) { document.getElementById("rep-texte").focus(); return; }
    const lecture = action === "extraire" ? ReponsesVendeur.extraire(r.texte) : {champs:{},extraits:{},conflits:[],alertes:[]};
    const base = r.base || {champs:{},extraits:{},conflits:[],corrections:{}};
    r.champs = {...base.champs,...lecture.champs};
    const extraits = {...base.extraits,...lecture.extraits};
    r.corrections = {...base.corrections};
    for (const cle of Object.keys(lecture.champs)) delete r.corrections[cle];
    for (const c of lecture.conflits) delete r.champs[c.champ];
    for (const cle of (lecture.inconnus||[])) { delete r.champs[cle]; delete extraits[cle]; delete r.corrections[cle]; }
    r.lecture={...lecture,extraits,conflits:[...(base.conflits||[]).filter(c=>!(c.champ in lecture.champs)),...lecture.conflits]};
    r.confirme=false; r.aRelire=false;
    r.maj=new Date().toISOString(); const ok=sauvegarderReponses();
    rendreDossierReponse(); statutSauvegardeReponse(ok);
    document.getElementById("rep-analyse").scrollIntoView({behavior:"smooth",block:"start"}); return;
  }
  if (action === "valider") {
    if (r.aRelire) { rendreAnalyseReponse(); document.getElementById("rep-texte").focus(); return; }
    const invalide = [...document.querySelectorAll("[data-rep-champ]")].find(e=>!e.checkValidity());
    if (invalide) { invalide.reportValidity(); return; }
    r.confirme=true; r.maj=new Date().toISOString();
    statutSauvegardeReponse(sauvegarderReponses()); rendreAnalyseReponse();
    document.getElementById("rep-analyse").scrollIntoView({behavior:"smooth",block:"start"}); return;
  }
  if (action === "copier") {
    const champ=document.getElementById("rep-relance"), statut=document.getElementById("rep-copie");
    try { await navigator.clipboard.writeText(champ.value); statut.textContent=" Copié ✓"; }
    catch (e) { champ.select(); statut.textContent=document.execCommand("copy")?" Copié ✓":" Texte sélectionné : copiez-le avec votre clavier."; }
  }
});
