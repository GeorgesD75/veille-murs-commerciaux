/* Comparaison à financement identique ; aucune modification du score. */
const ImpactReponse = (() => {
  function comparer(avant, apres) {
    const exploitable = r=>r && ["interessant","a_negocier","annonce"].includes(r.niveau)
      && !r.manquants?.length && Number.isFinite(r.finance?.cashflow) && r.finance.prix>0;
    const financier = !!(exploitable(avant) && exploitable(apres));
    return {financier,etatAvant:avant?.titre||"Annonce à compléter",etatApres:apres.titre,
      cashflowAvant:financier?avant.finance.cashflow:null,cashflowApres:financier?apres.finance.cashflow:null,
      prixAvant:financier?avant.finance.prix:null,prixApres:financier?apres.finance.prix:null,
      plafondAvant:financier && Number.isFinite(avant.finance.prixCible)?avant.finance.prixCible:null,
      plafondApres:financier && Number.isFinite(apres.finance.prixCible)?apres.finance.prixCible:null};
  }
  return {comparer};
})();
