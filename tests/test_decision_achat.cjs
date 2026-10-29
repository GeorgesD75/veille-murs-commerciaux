const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const contexte = vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../dashboard/decision_achat.js'),'utf8')+';this.moteur=DecisionAchat;',contexte);
const annonce = () => ({prix:200000,loyer_mensuel:1800,flags:[],decision:{
  diagnostic:{bloquant:false,occupation:'occupe',transaction:{nature:'murs'},alertes:[]},
  relocation:{niveau:'a_verifier'}}});
const contexteInitial = () => ({objectif:100,projection:{cashflow:150},projectionCible:{cashflow:120},pepite:true,prioritaire:true});
const analyser = (a=annonce(), c={}) => contexte.moteur.analyser(a,{...contexteInitial(),...c});

test('la priorité exige des données de murs occupés, sans loyer estimé ni alerte',()=>{
  assert.equal(analyser().niveau,'favorable');
  assert.match(analyser().titre,/priorité/);
  for (const nature of ['fonds','droit_au_bail','mixte','indetermine']) {
    const a=annonce(); a.decision.diagnostic.transaction.nature=nature;
    assert.equal(analyser(a).niveau,'vigilance');
  }
  for (const changer of [a=>a.loyer_mensuel=null,a=>a.loyer_estime=true,a=>a.loyer_origine='rendement',a=>a.decision.loyer_estime=true]) {
    const a=annonce(); changer(a); assert.equal(analyser(a).niveau,'completer');
  }
  for (const occupation of ['libre','a_confirmer']) {
    const a=annonce(); a.decision.diagnostic.occupation=occupation;
    assert.equal(analyser(a).niveau,'completer');
  }
});

test('contradictions, risque de copropriété et relocation priment sur le score',()=>{
  const a=annonce(); a.decision.diagnostic.bloquant=true;
  a.decision.diagnostic.alertes=[{niveau:'fort',texte:'Deux prix différents'}];
  assert.equal(analyser(a).raison,'Deux prix différents');
  for (const flag of ['dette_copropriete','localisation_incoherente','rendement_anormalement_eleve','prix_m2_anormalement_bas','texte_partiel_alerte']) {
    const a=annonce(); a.flags=[flag]; assert.equal(analyser(a).niveau,'vigilance');
  }
  const rue=annonce(); rue.decision.relocation={niveau:'vigilance',vigilances:['Trois locaux vacants']};
  assert.equal(analyser(rue).raison,'Trois locaux vacants');
  const ancienne=annonce(); ancienne.peut_etre_retiree=true;
  assert.equal(analyser(ancienne).niveau,'completer');
});

test('potentiel de négociation et trésorerie personnelle restent distincts du prix affiché',()=>{
  const a=annonce(); a.negociation={prix_plafond:160000};
  const c={projection:{cashflow:-200},pepite:false,prioritaire:false,potentiel:true};
  const resultat=analyser(a,c);
  assert.equal(resultat.niveau,'negociation'); assert.match(resultat.raison,/après négociation/);
  const insuffisant=analyser(a,{...c,projectionCible:{cashflow:99}});
  assert.equal(insuffisant.niveau,'vigilance'); assert.match(insuffisant.titre,/ne suffit pas/);
  assert.equal(analyser(a,{...c,projectionCible:{cashflow:100}}).niveau,'negociation');
});

test('positif limité, effort mensuel ou simulation impossible ne valent pas un signal pépite',()=>{
  const c={pepite:false,prioritaire:false};
  assert.match(analyser(annonce(),{...c,projection:{cashflow:50}}).titre,/marge limitée/);
  assert.match(analyser(annonce(),{...c,projection:{cashflow:-1}}).titre,/effort mensuel/);
  assert.equal(analyser(annonce(),{...c,projection:null}).niveau,'completer');
  assert.equal(analyser(annonce(),{...c,projection:{cashflow:100}}).niveau,'completer');
});

test('une réponse non relue suspend la décision, sans utiliser ses anciens chiffres',()=>{
  for (const retour of [{confirme:false},{confirme:true,aRelire:true},{confirme:true,resultat:null}]) {
    const r=analyser(annonce(),{retour});
    assert.equal(r.niveau,'completer'); assert.equal(r.origine,'vendeur'); assert.match(r.titre,/relire/);
  }
});

test('la réponse vendeur relue prime sur le stock et conserve ses réserves',()=>{
  for (const [niveau,attendu] of [['hors_cible','vigilance'],['vigilance','vigilance'],['a_clarifier','completer'],['a_negocier','negociation'],['interessant','favorable']]) {
    const r=analyser(annonce(),{retour:{confirme:true,resultat:{niveau,finance:{cashflow:150},manquants:[],risques:['Information vendeur']}}});
    assert.equal(r.niveau,attendu); assert.equal(r.origine,'vendeur');
  }
  const r=analyser(annonce(),{retour:{confirme:true,resultat:{niveau:'interessant',finance:{cashflow:500},manquants:[{texte:'Charges inconnues'}]}}});
  assert.equal(r.niveau,'completer'); assert.equal(r.raison,'Charges inconnues');
});

test('la lecture ne modifie ni le score, ni les faits, ni les projections',()=>{
  const a=annonce(),c=contexteInitial(); a.score=69;
  const avant=JSON.stringify({a,c}); analyser(a,c);
  assert.equal(JSON.stringify({a,c}),avant);
});

test('prix personnel : plus grand prix sur la grille et prix affiché comme borne maximale',()=>{
  const f=prix=>1300-prix/200;
  const p=contexte.moteur.prixPourCashflow({maximum:300000,objectif:100},f);
  assert.equal(p,240000); assert.ok(f(p)>=100 && f(p+1000)<100);
  assert.equal(contexte.moteur.prixPourCashflow({maximum:200123,objectif:100},f),200123);
  assert.equal(contexte.moteur.prixPourCashflow({maximum:300000,objectif:0},f),260000);
});

test('prix personnel : apport fixe et achat comptant restent monotones',()=>{
  const f=prix=>1200-Math.max(0,prix*1.08+10000-40000)/240;
  const p=contexte.moteur.prixPourCashflow({maximum:400000,objectif:100},f);
  assert.equal(p,272000); assert.ok(f(p)>=100 && f(p+1000)<100);
  assert.equal(contexte.moteur.prixPourCashflow({maximum:200000,objectif:100},()=>1200),200000);
});

test('prix personnel : aucun nombre inventé si revenu ou financement invalide',()=>{
  for (const f of [()=>null,()=>undefined,()=>NaN,()=>Infinity,()=>-50])
    assert.equal(contexte.moteur.prixPourCashflow({maximum:300000,objectif:100},f),null);
  for (const options of [{maximum:NaN},{maximum:-1},{maximum:100000,objectif:-1},{maximum:100000,pas:0}])
    assert.equal(contexte.moteur.prixPourCashflow(options,()=>1000),null);
});

test('classement : prix actuel puis effort de négociation, sans modifier le score',()=>{
  const a=annonce();a.score=69;a.negociation={prix_plafond:170000,remise_pct:15};
  const courant=contexte.moteur.priorite(a,{pepite:true,cf:120,objectif:100});
  const negociable=contexte.moteur.priorite(a,{potentiel:true,cf:-100,cfCible:120,objectif:100});
  a.negociation.remise_pct=33;
  const exigeant=contexte.moteur.priorite(a,{potentiel:true,cfCible:120});
  assert.ok(courant.rang<negociable.rang && negociable.rang<exigeant.rang);
  assert.equal(a.score,69);assert.match(exigeant.libelle,/exigeante/);
  assert.equal(contexte.moteur.priorite(a,{potentiel:true,cfCible:99}).prioritaire,false);
});

test('classement vendeur : dossier relu et négociation modérée, pas les risques',()=>{
  const a=annonce();
  const vendeur=niveau=>({confirme:true,resultat:{niveau,manquants:[],finance:{prix:220000,prixCible:200000,cashflow:120,cashflowCible:130}}});
  assert.equal(contexte.moteur.priorite(a,{vendeur:vendeur('interessant')}).rang,0);
  assert.equal(contexte.moteur.priorite(a,{vendeur:vendeur('a_negocier')}).prioritaire,true);
  assert.equal(contexte.moteur.priorite(a,{vendeur:vendeur('vigilance')}).prioritaire,false);
  const incomplet=vendeur('a_negocier');delete incomplet.resultat.finance.cashflowCible;
  assert.equal(contexte.moteur.priorite(a,{vendeur:incomplet}).prioritaire,false);
  const v=vendeur('a_negocier');v.resultat.finance.prixCible=140000;
  assert.equal(contexte.moteur.priorite(a,{vendeur:v}).prioritaire,false);
});

test('une réponse complète peut qualifier la nature inconnue, sans lever une contradiction de surface',()=>{
  const a=annonce();a.decision.diagnostic={bloquant:true,transaction:{nature:'a_confirmer'},alertes:[{code:'nature_transaction_a_confirmer',niveau:'fort'}]};
  const vendeur={confirme:true,resultat:{niveau:'interessant',manquants:[],finance:{prix:200000,cashflow:150}}};
  assert.equal(contexte.moteur.priorite(a,{vendeur}).prioritaire,true);
  a.decision.diagnostic.alertes.push({code:'conflit_surface_m2',niveau:'fort'});
  assert.equal(contexte.moteur.priorite(a,{vendeur}).prioritaire,false);
  a.decision.diagnostic={bloquant:true,transaction:{nature:'murs'},alertes:[{code:'conflit_charges_bailleur_annuelles',niveau:'fort'}]};
  assert.equal(contexte.moteur.priorite(a,{vendeur}).prioritaire,false);
  vendeur.resultat.finance.chargesDeclarees=0;
  assert.equal(contexte.moteur.priorite(a,{vendeur}).prioritaire,true);
});
