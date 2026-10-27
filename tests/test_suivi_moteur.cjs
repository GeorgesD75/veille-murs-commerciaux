const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const contexte = vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../dashboard/suivi_moteur.js'),'utf8')+';this.moteur=SuiviMoteur;',contexte);
const m=contexte.moteur;

test('dates calendaires réelles : années bissextiles, dates impossibles et texte hostile',()=>{
  for (const d of ['2026-10-27','2028-02-29','2026-12-31']) assert.ok(m.dateValide(d));
  for (const d of ['2026-02-29','2026-02-31','2026-13-01','<script>','27/10/2026','',null,undefined]) assert.equal(m.dateValide(d),false);
  assert.equal(m.formatDate('2026-10-27'),'27/10/2026');
});

test('rappels passés, du jour et futurs ; aucune relance pour une piste abandonnée',()=>{
  const jour='2026-10-27';
  for (const [rappel,etat] of [['2026-10-26','retard'],[jour,'aujourdhui'],['2026-10-28','avenir'],['','aucun']])
    assert.equal(m.etatRappel({statut:'contactee',rappel},jour),etat);
  assert.equal(m.etatRappel({statut:'abandonnee',rappel:'2026-10-20'},jour),'aucun');
  assert.equal(m.etatRappel({},jour),'aucun');
});

test('les échéances priment sur la date de modification, sans modifier les données',()=>{
  const a={rappel:'2026-10-26',maj:'2026-10-01'},b={rappel:'2026-10-28',maj:'2026-10-27'},c={maj:'2026-10-27'};
  const avant=JSON.stringify([a,b,c]);
  assert.ok(m.trier(a,b)<0 && m.trier(b,c)<0);
  assert.equal(JSON.stringify([a,b,c]),avant);
});

test('la date locale respecte le calendrier de la machine même autour de minuit UTC',()=>{
  const d=new Date(2026,9,27,0,5);
  assert.equal(m.jourLocal(d),'2026-10-27');
  assert.equal(m.jourLocal(new Date('invalide')),'');
});
