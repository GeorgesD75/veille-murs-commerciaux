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
