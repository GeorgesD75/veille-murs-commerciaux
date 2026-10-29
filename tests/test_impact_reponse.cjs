const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const c=vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../dashboard/impact_reponse.js'),'utf8')+';this.m=ImpactReponse;',c);
const analyse=(cf,plafond,niveau='interessant')=>({niveau,titre:niveau,manquants:[],finance:{prix:200000,cashflow:cf,prixCible:plafond}});

test('un nouveau montant de charges réduit le plafond et la marge sans toucher aux résultats',()=>{
  const a=analyse(150,210000),b=analyse(-50,180000,'a_negocier'),avant=JSON.stringify([a,b]);
  const e=c.m.comparer(a,b);
  assert.ok(e.financier);assert.equal(e.plafondAvant,210000);assert.equal(e.plafondApres,180000);
  assert.equal(e.cashflowAvant,150);assert.equal(e.cashflowApres,-50);
  assert.equal(JSON.stringify([a,b]),avant);
});

test('pas de delta financier affiché sur un dossier incomplet, risqué ou un fonds',()=>{
  for(const niveau of ['a_clarifier','vigilance','hors_cible']){
    const e=c.m.comparer(analyse(150,210000),analyse(500,250000,niveau));
    assert.equal(e.financier,false);assert.equal(e.plafondApres,null);
  }
  const incomplet=analyse(150,210000);incomplet.manquants=[{cle:'loyer'}];
  assert.equal(c.m.comparer(incomplet,analyse(500,250000)).financier,false);
});

test('premier retour : comparaison explicitement possible avec les hypothèses de l’annonce',()=>{
  const e=c.m.comparer(analyse(-100,170000,'annonce'),analyse(50,190000,'a_negocier'));
  assert.ok(e.financier);assert.equal(e.plafondAvant,170000);
  assert.equal(c.m.comparer(null,analyse(50,190000)).financier,false);
});
