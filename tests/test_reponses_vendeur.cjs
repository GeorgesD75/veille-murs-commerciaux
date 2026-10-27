const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const contexte = vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../dashboard/reponses_moteur.js'),'utf8')+';this.moteur=ReponsesVendeur;',contexte);
const m = contexte.moteur;
const annonce = {prix:200000,honoraires:0,loyer_mensuel:1400,decision:{relocation:{niveau:'a_verifier'}}};
const profil = {apport:20,apportMode:'pct',apportEuros:50000,taux:4,duree:20};
const configuration = {recherche:{vacance_prudente_pct:8,provision_charges_pct:10},analyse:{negociation:{cashflow_cible_mensuel:100},dossier_banque:{taxe_fonciere_mois_loyer:1}}};
const complet = {nature:'murs',occupation:'loue',loyer:1800,periode_loyer:'mois',base_loyer:'ht_hc',bail:'depuis juin 2022 pour 9 ans',impayes:'non',charges:600,periode_charges:'an',charges_nature:'bailleur',taxe_comprise:'non',taxe:1200,periode_taxe:'an'};
const analyser = (c={},a=annonce,p=profil)=>m.analyser({...complet,...c},a,p,configuration,true);

test('réponse française : extraits, annuel converti et cinq informations essentielles',()=>{
  const e=m.extraire('Oui, vente des murs seuls hors fonds de commerce. Le local est actuellement loué. Bail signé en 2022 pour 9 ans. Loyer annuel de 21 600 € HT HC. Charges non récupérables du propriétaire : 600 €/an, hors taxe foncière. Taxe foncière annuelle : 1200 €. Aucun impayé.');
  assert.equal(e.champs.nature,'murs'); assert.equal(e.champs.occupation,'loue');
  assert.equal(e.champs.loyer,1800); assert.equal(e.champs.periode_loyer,'mois'); assert.equal(e.champs.base_loyer,'ht_hc');
  assert.equal(e.champs.charges,600); assert.equal(e.champs.charges_nature,'bailleur'); assert.equal(e.champs.taxe_comprise,'non');
  assert.equal(e.champs.taxe,1200); assert.equal(e.champs.impayes,'non'); assert.ok(e.champs.bail.includes('2022'));
  assert.ok(e.extraits.loyer.includes('21 600')); assert.equal(e.conflits.length,0);
});
test('mensuel, HT et hors charges, taxe comprise et loyers à jour',()=>{
  const e=m.extraire('Les murs sont bien vendus. Locataire en place depuis 2021. Loyer 1 500 € par mois HT et hors charges. Charges bailleur : 100 € par mois, taxe foncière comprise. Les loyers sont à jour.');
  assert.equal(e.champs.nature,'murs'); assert.equal(e.champs.loyer,1500); assert.equal(e.champs.base_loyer,'ht_hc');
  assert.equal(e.champs.charges,1200); assert.equal(e.champs.taxe_comprise,'oui'); assert.equal(e.champs.impayes,'non');
});
test('ne confond pas montant et période inconnue',()=>{
  const e=m.extraire('Loyer : 1500 € HT HC. Charges propriétaire : 600 €.');
  assert.equal(e.champs.loyer,1500); assert.equal(e.champs.periode_loyer,undefined);
  assert.equal(e.champs.periode_charges,undefined);
  const r=analyser({...e.champs,periode_loyer:''}); assert.equal(r.finance,null); assert.equal(r.niveau,'a_clarifier');
});
test('les questions citées ne deviennent pas des réponses',()=>{
  const e=m.extraire('Bonjour, je vous rappelle demain.\n> Le prix porte-t-il sur les murs seuls ?\n> Loyer 1800 €/mois HT HC.\nLe 24 octobre Jean a écrit :\nVente des murs seuls. Aucun impayé.');
  assert.equal(Object.keys(e.champs).length,0);
});
test('fonds, droit au bail et mixte ne sont pas des murs seuls',()=>{
  for(const [texte,nature] of [['Vente du fonds de commerce, murs non compris.','fonds'],['Cession du droit au bail.','bail'],['Vente des murs et fonds.','mixte']]) {
    assert.equal(m.extraire(texte).champs.nature,nature);
    const r=analyser({nature}); assert.equal(r.niveau,'hors_cible'); assert.equal(r.finance,null);
  }
});
test('contradictions : deux loyers distincts ne sont pas choisis arbitrairement',()=>{
  const e=m.extraire('Loyer 1500 €/mois HT HC. Loyer 1900 €/mois HT HC.');
  assert.equal(e.champs.loyer,undefined); assert.ok(e.conflits.some(c=>c.champ==='loyer'));
});
test('loyers annuel et mensuel équivalents ne créent pas une contradiction',()=>{
  const e=m.extraire('Loyer 1500 €/mois HT HC. Loyer annuel 18 000 € HT HC.');
  assert.equal(e.champs.loyer,1500); assert.equal(e.conflits.length,0);
});
test('un loyer au m² ne devient pas un loyer global',()=>{
  const e=m.extraire('Loyer annuel : 250 €/m² HT HC.');
  assert.equal(e.champs.loyer,undefined); assert.ok(e.alertes.length);
});
test('estimation et TTC ne deviennent pas un revenu de bail HT/HC',()=>{
  for(const texte of ['Loyer estimé 1500 €/mois HT HC.','Loyer 1500 €/mois TTC charges comprises.']) {
    const e=m.extraire(texte); assert.notEqual(e.champs.base_loyer,'ht_hc');
    assert.equal(analyser(e.champs).finance,null);
  }
});
test('absence de mention des impayés n’est jamais absence d’impayés',()=>{
  assert.equal(m.extraire('Loué depuis 2021. Loyer 1500 €/mois.').champs.impayes,undefined);
  assert.equal(m.extraire("Je n'ai pas d'info sur les impayés.").champs.impayes,undefined);
  assert.equal(analyser({impayes:''}).niveau,'a_clarifier');
});
test('impayés déclarés : pas de conclusion favorable',()=>{
  assert.equal(m.extraire('Il y a des impayés depuis juin.').champs.impayes,'oui');
  const r=analyser({impayes:'oui'}); assert.equal(r.niveau,'vigilance'); assert.ok(r.relance.includes('régularisés'));
});
test('bail 3/6/9 seul ne prouve aucune date ni durée restante',()=>{
  const r=analyser({bail:'Bail 3/6/9'}); assert.ok(r.manquants.some(m=>m.cle==='bail'));
});
test('charges inconnues différentes de zéro déclaré',()=>{
  assert.equal(analyser({charges:''}).niveau,'a_clarifier');
  const r=analyser({charges:0}); assert.equal(r.manquants.some(m=>m.cle==='charges'),false);
  assert.equal(r.finance.fraisMensuels,280); // provision 180 + taxe 100
});
test('taxe comprise : jamais additionnée deux fois',()=>{
  const a=analyser({charges:3600,taxe_comprise:'oui'}).finance;
  const b=analyser({charges:2400,taxe_comprise:'non'}).finance;
  assert.equal(a.fraisMensuels,300); assert.equal(a.cashflow,b.cashflow);
});
test('taxe inconnue provisionnée, zéro réel conservé',()=>{
  const a=analyser({taxe:''}), b=analyser({taxe:0});
  assert.equal(a.finance.taxe,1800); assert.equal(a.finance.taxeEstimee,true);
  assert.equal(b.finance.taxe,0); assert.ok(a.finance.cashflow<b.finance.cashflow);
});
test('FAI du vendeur n’ajoute pas les anciens honoraires une deuxième fois',()=>{
  const a={...annonce,honoraires:10000};
  assert.equal(analyser({prix:200000,prix_base:'inclus'},a).finance.honoraires,0);
  assert.equal(analyser({prix:200000,prix_base:'net'},a).finance.honoraires,10000);
});
test('chiffres favorables mais aucune promesse de relocation facile',()=>{
  const r=analyser(); assert.equal(r.niveau,'interessant'); assert.ok(r.points.some(p=>p.includes('locative')));
  assert.equal(r.manquants.length,0); assert.ok(r.finance.cashflow>=100);
});
test('risque de rue, local libre, manque d’information : pas de feu vert',()=>{
  assert.equal(analyser({}, {...annonce,decision:{relocation:{niveau:'vigilance',vigilances:['Rue à vérifier']}}}).niveau,'vigilance');
  assert.equal(analyser({occupation:'libre'}).niveau,'a_clarifier');
  assert.equal(analyser({charges_nature:''}).niveau,'a_clarifier');
});
test('prix cible financier conservateur : cash-flow visé atteint au plafond',()=>{
  const r=analyser({prix:300000,prix_base:'inclus'}); assert.equal(r.niveau,'a_negocier');
  assert.ok(r.finance.prixCible<300000);
  const cible=analyser({prix:r.finance.prixCible,prix_base:'inclus'}).finance;
  assert.ok(cible.cashflow>=100);
  assert.equal(r.finance.cashflowCible,cible.cashflow);
  assert.equal(r.finance.stressCible,cible.stress);
  assert.equal(r.finance.mensualiteCible,cible.mensualite);
  assert.ok(r.finance.cashflowCible>r.finance.cashflow);
});
test('cash-flow au prix cible recalculé avec apport fixe, frais et taux zéro',()=>{
  const a={...annonce,honoraires:10000};
  const p={...profil,apportMode:'euros',apportEuros:40000,taux:0};
  const r=analyser({prix:400000,prix_base:'net'},a,p).finance;
  const cible=analyser({prix:r.prixCible,prix_base:'net'},a,p).finance;
  assert.equal(r.cashflowCible,cible.cashflow);
  assert.equal(r.stressCible,cible.stress);
  assert.ok(r.cashflowCible>=100);
});
test('taux zéro, apport fixe et achat comptant',()=>{
  assert.ok(Number.isFinite(analyser({},annonce,{...profil,taux:0}).finance.cashflow));
  assert.equal(analyser({},annonce,{...profil,apportMode:'euros',apportEuros:500000}).finance.mensualite,0);
  assert.equal(analyser({},annonce,{...profil,apport:100}).finance.mensualite,0);
});
test('profil invalide suspend le calcul ; données originales intactes',()=>{
  const original=JSON.stringify({annonce,profil,complet});
  assert.equal(analyser({},annonce,{...profil,duree:0}).finance,null);
  assert.equal(analyser({},annonce,{...profil,apport:101}).finance,null);
  analyser(); assert.equal(JSON.stringify({annonce,profil,complet}),original);
});
test('relance courte et ciblée, au maximum trois questions',()=>{
  const r=m.analyser({},annonce,profil,configuration,false);
  assert.ok(r.relance.includes('Merci pour votre retour')); assert.ok((r.relance.match(/^- /gm)||[]).length<=3);
  assert.equal(analyser().relance,'');
});
test('dates et durée ne sont pas extrapolées, échéance passée explicite signalée',()=>{
  assert.equal(analyser({bail:'Depuis 2017 pour 9 ans'}).niveau,'interessant');
  assert.equal(analyser({bail:"Prochaine échéance le 01/01/2000"}).niveau,'vigilance');
  const e=m.extraire('Locataire en place depuis 2019. Bail signé en 2024 pour 9 ans.');
  assert.ok(e.champs.bail.includes('2019') && e.champs.bail.includes('2024'));
  assert.equal(e.conflits.length,0);
});
test('erreur de période manifeste et budget de charges intenable ne passent pas',()=>{
  assert.equal(analyser({loyer:18000}).niveau,'vigilance');
  const r=analyser({charges:24000}); assert.equal(r.niveau,'vigilance'); assert.equal(r.finance.prixCible,null);
});
test('négation du fonds et départ du locataire sont traités séparément',()=>{
  assert.equal(m.extraire("Le fonds n'est pas vendu, les murs uniquement.").champs.nature,'murs');
  const e=m.extraire('Le locataire a donné congé et quittera le local en décembre.');
  assert.equal(e.champs.depart,'oui'); assert.equal(analyser(e.champs).niveau,'vigilance');
  assert.equal(m.extraire("Le locataire n'a pas donné congé.").champs.depart,undefined);
});
test('montants sans symbole euro admis seulement avec une période explicite',()=>{
  const e=m.extraire('Loyer annuel 18000 HT HC. Charges propriétaire 600/an, hors taxe foncière.');
  assert.equal(e.champs.loyer,1500); assert.equal(e.champs.charges,600);
  assert.equal(m.extraire('Loyer 1500 HT HC.').champs.loyer,undefined);
  assert.equal(analyser({bail:'Prochaine échéance le 31/02/2035'}).niveau,'vigilance');
});
test('une inconnue explicite invalide aussi une ancienne valeur consolidée',()=>{
  const e=m.extraire("Je ne connais pas le montant de la taxe foncière. Je ne sais pas s'il y a des impayés.");
  assert.ok(e.inconnus.includes('taxe')); assert.ok(e.inconnus.includes('impayes'));
  assert.equal(e.champs.impayes,undefined);
});
