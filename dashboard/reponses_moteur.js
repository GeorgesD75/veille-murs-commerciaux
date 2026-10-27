/* Lecture locale et déterministe. Une réponse vendeur reste déclarative. */
const ReponsesVendeur = (() => {
  const normaliser = t => String(t || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[’‘]/g, "'").toLowerCase();
  const nombre = v => {
    if (v == null || String(v).trim() === "" || typeof v === "boolean") return null;
    const n = Number(String(v).replace(/[\s\u00a0\u202f]/g, "").replace(",", "."));
    return Number.isFinite(n) && n >= 0 && n <= 1e12 ? n : null;
  };
  const annuel = (v, periode) => {
    const n = nombre(v);
    return n == null || !["mois", "an"].includes(periode) ? null : n * (periode === "mois" ? 12 : 1);
  };
  function extraire(texte) {
    const candidats = {}, alertes = [], inconnus = new Set();
    const ajouter = (cle, valeur, extrait) => {
      if (valeur == null || valeur === "") return;
      (candidats[cle] ||= []).push({valeur, extrait: extrait.trim().slice(0, 260)});
    };
    // Ne pas transformer les questions et messages cités du premier contact
    // en affirmations du vendeur. L'utilisateur peut corriger les champs.
    let lignes = String(texte || "").split(/\r?\n/), utiles = [];
    for (const ligne of lignes) {
      if (/^\s*(?:de\s*:|from\s*:|le .{5,100}a [ée]crit\s*:|on .{5,100}wrote\s*:|[-_]{4,})/i.test(ligne)) break;
      if (/^\s*>/.test(ligne)) continue;
      utiles.push(ligne);
    }
    const morceaux = utiles.join("\n").split(/\n|;|[.!]\s+(?=[A-Za-zÀ-ÿ])|,\s+(?=(?:les?\s+)?(?:charges?|taxe|loyer|prix)\b)/i);
    for (const brut of morceaux) {
      if (brut.includes("?")) continue;
      const t = normaliser(brut);
      if (!t.trim()) continue;
      if (/ne sais pas|ne connais pas|n'ai pas.{0,12}(?:info|montant)|inconnu|non renseigne|a confirmer/.test(t)) {
        const vider = cles=>cles.forEach(c=>inconnus.add(c));
        if (/impaye|paiement|loyers? (?:sont |est )?a jour|locataire paie/.test(t)) vider(["impayes"]);
        else {
          if (/loyer/.test(t)) vider(["loyer","periode_loyer","base_loyer"]);
          if (/charges?/.test(t)) vider(["charges","periode_charges","charges_nature"]);
          if (/taxe fonciere|\btf\b/.test(t)) vider(["taxe","periode_taxe"]);
          if (/bail/.test(t)) vider(["bail"]);
          if (/loue|occupation/.test(t)) vider(["occupation"]);
        }
      }
      const fondsVendus = /(?:vente|cession|vends?|s'agit|uniquement|seulement|prix).{0,35}(?:fonds de commerce|droit au bail)|^(?:un |le )?(?:fonds de commerce|droit au bail)\b/.test(t);
      const horsFonds = /(?:hors|sans|pas de|ni|ne comprend pas)\s+(?:de\s+)?(?:vente (?:de|du) )?(?:fonds|droit au bail)|fonds n'est pas (?:vendu|inclus|compris)/.test(t);
      const mixte = /murs\s*(?:et|\+)\s*(?:le |les )?fonds|fonds\s*(?:et|\+)\s*(?:les )?murs/.test(t);
      if (mixte && !horsFonds) ajouter("nature", "mixte", brut);
      else if (fondsVendus && !horsFonds) ajouter("nature", /droit au bail/.test(t) ? "bail" : "fonds", brut);
      else if (/murs (?:seuls|uniquement|commerciaux)|murs (?:sont|seront) (?:bien )?vendus|vente (?:des |du |de )?(?:murs|local)|vends? (?:les |des |le )?(?:murs|local)|(?:oui|bien|confirme).{0,25}(?:les |des )?murs|pleine propriete/.test(t)
        && !/murs (?:non compris|en option|vendus separement)|pas (?:les |de )?murs|ne vend.{0,12}pas.{0,12}murs/.test(t)) ajouter("nature", "murs", brut);
      if (/uniquement.{0,12}location|local (?:est )?a louer/.test(t)) ajouter("nature", "location", brut);
      if (/actuellement (?:loue|occupe)|locataire (?:est )?(?:en place|present)|(?:est|vendu) loue|(?:loue|occupe) depuis|occupe par|murs occupes/.test(t)) ajouter("occupation", "loue", brut);
      if (/^(?:local )?libre[ .!]*$|(?:local est|actuellement|vendu|sera vendu) (?:vide|libre)|non loue|n'est pas loue|sans locataire|aucun locataire/.test(t)) ajouter("occupation", "libre", brut);
      if (/aucun impaye|pas d'impayes?|sans impayes?|loyers? (?:sont |est )?(?:a jour|regles? sans retard)|aucun retard de (?:loyer|paiement)/.test(t)) ajouter("impayes", "non", brut);
      const paiementPositif = t.replace(/(?:aucun|sans) impayes?|pas d'impayes?|(?:aucun|pas de|sans) retards? de (?:loyer|paiement)/g, "");
      if (/impayes? (?:en cours|de |depuis|constates?|actuels?)|(?:il y a|avec|presence d').{0,12}impayes?|retards? de (?:loyer|paiement)|ne paie plus|loyers? (?:non regles?|en retard)/.test(paiementPositif)
        && !/pas d'info|ne sais pas|a verifier|inconnu/.test(t)) ajouter("impayes", "oui", brut);
      if (/(?:bail|locataire|loue).{0,80}(?:depuis|signe|debut|effet|jusqu|echeance|restant|pour \d|de \d.{0,5}ans)/.test(t)) ajouter("bail", brut.trim().slice(0, 220), brut);
      if (/locataire.{0,45}(?:a donne conge|depart (?:est )?(?:prevu|annonce)|quitte|quittera|partira|va partir)|conge (?:donne |recu )?(?:par |du )?locataire/.test(t)
        && !/n'a pas donne conge|aucun conge|pas de conge/.test(t)) ajouter("depart", "oui", brut);
      if (/(?:taxe fonciere|tf) (?:est |etant )?(?:comprise|incluse)|(?:comprenant|incluant|y compris).{0,15}(?:taxe fonciere|\btf\b)/.test(t)) ajouter("taxe_comprise", "oui", brut);
      if (/(?:hors|sans).{0,10}(?:taxe fonciere|\btf\b)|(?:taxe fonciere|tf) (?:est )?(?:a part|non comprise|non incluse|en plus)/.test(t)) ajouter("taxe_comprise", "non", brut);
      if (/charges/.test(t)) {
        if (/proprietaire|bailleur|non recuperable|a ma charge|a notre charge/.test(t)) ajouter("charges_nature", "bailleur", brut);
        if (/(?:taxe fonciere|tf) (?:est |etant )?(?:comprise|incluse)|(?:comprenant|incluant|y compris).{0,15}(?:taxe fonciere|\btf\b)/.test(t)) ajouter("taxe_comprise", "oui", brut);
        if (/(?:hors|sans).{0,10}(?:taxe fonciere|\btf\b)|(?:taxe fonciere|tf) (?:est )?(?:a part|non comprise|non incluse|en plus)/.test(t)) ajouter("taxe_comprise", "non", brut);
        if (/aucune charge.{0,30}(?:bailleur|proprietaire)|(?:bailleur|proprietaire).{0,25}aucune charge/.test(t)) {
          ajouter("charges", 0, brut); ajouter("periode_charges", "an", brut); ajouter("charges_nature", "bailleur", brut);
        }
      }
      let montants = [...brut.matchAll(/(-?\d{1,3}(?:[ \u00a0\u202f.,]\d{3})+(?:[,.]\d{1,2})?|-?\d+(?:[,.]\d{1,2})?)\s*(?:€|euros?\b|eur\b)/gi)];
      const sansDevise = !montants.length;
      if (sansDevise && /loyer|charges?|taxe fonciere|\btf\b/.test(t)) montants = [...brut.matchAll(/(-?\d{1,3}(?:[ \u00a0\u202f.,]\d{3})+(?:[,.]\d{1,2})?|-?\d+(?:[,.]\d{1,2})?)/g)];
      for (const m of montants) {
        let montant = m[1].replace(/[ \u00a0\u202f]/g, "");
        if (/^\d{1,3}(?:[.,]\d{3})+(?:[,.]\d{1,2})?$/.test(montant)) montant = montant.replace(/[.,](?=\d{3}(?:[.,]|$))/g, "");
        montant = nombre(montant);
        if (montant == null) continue;
        const avant = normaliser(brut.slice(0, m.index)), apres = normaliser(brut.slice(m.index + m[0].length, m.index + m[0].length + 55));
        const etiquettes = [...avant.matchAll(/loyer|charges?|taxe fonciere|\btf\b|prix|honoraires/g)];
        const etiquette = etiquettes.at(-1)?.[0];
        const suite = apres.split(/\b(?:taxe fonciere|prix|loyer|charges? (?:bailleur|proprietaire|de |du |sont))\b/)[0].slice(0,35);
        const periode = /(?:\/|par)\s*mois\b|^\s*mensuels?\b/.test(suite) || /mensuel/.test(avant.slice(-32)) ? "mois"
          : /(?:\/|par)\s*(?:an|annee)\b|^\s*annuels?\b/.test(suite) || /annuel/.test(avant.slice(-32)) ? "an" : "";
        if (sansDevise && !periode) continue;
        if (etiquette === "loyer") {
          if (/^(?:\s|ht|hc|[(),])*(?:\/\s*m[²2]|par m[²2])/.test(apres)) { alertes.push("Loyer indiqué au m² : obtenir le montant global."); continue; }
          ajouter("loyer", periode === "an" ? montant/12 : montant, brut); ajouter("periode_loyer", periode ? "mois" : "", brut);
          if (/estime|potentiel|pourrait|envisage|espere/.test(t)) ajouter("base_loyer", "estime", brut);
          else if (/\bht\s*(?:[\/, -]|et)*\s*hc\b|hors taxes.{0,20}hors charges|\bht\b.{0,20}hors charges/.test(t)) ajouter("base_loyer", "ht_hc", brut);
          else if (/\bttc\b|charges comprises|\bcc\b/.test(t)) ajouter("base_loyer", "autre", brut);
        } else if (/^charges?$/.test(etiquette || "")) {
          ajouter("charges", periode === "mois" ? montant*12 : montant, brut); ajouter("periode_charges", periode ? "an" : "", brut);
        } else if (["taxe fonciere", "tf"].includes(etiquette)) {
          ajouter("taxe", periode === "mois" ? montant*12 : montant, brut); ajouter("periode_taxe", periode ? "an" : "", brut);
        } else if (etiquette === "prix") {
          ajouter("prix", montant, brut);
          if (/\bfai\b|honoraires (?:d'agence )?inclus|frais d'agence inclus/.test(t)) ajouter("prix_base", "inclus", brut);
          else if (/net vendeur|hors honoraires/.test(t)) ajouter("prix_base", "net", brut);
        }
      }
    }
    const champs = {}, extraits = {}, conflits = [];
    for (const [cle, liste] of Object.entries(candidats)) {
      const uniques = [...new Map(liste.map(c => [String(c.valeur), c])).values()];
      if (cle === "bail") { champs.bail = uniques.map(v=>v.valeur).join(" ; ").slice(0,220); extraits.bail=uniques.map(v=>v.extrait).join(" ; ").slice(0,520); }
      else if (uniques.length > 1) conflits.push({champ: cle, propositions: uniques});
      else { champs[cle] = uniques[0].valeur; extraits[cle] = uniques[0].extrait; }
    }
    for (const cle of inconnus) { delete champs[cle]; delete extraits[cle]; }
    return {champs, extraits, conflits, inconnus:[...inconnus], alertes: [...new Set(alertes)]};
  }
  function analyser(champs, annonce, profil, configuration, confirme = false) {
    const c = champs || {}, manquants = [], risques = [], points = [];
    const ajouter = (cle, texte) => manquants.push({cle, texte});
    const horsCible = ["fonds", "bail", "mixte", "location"].includes(c.nature);
    if (c.nature !== "murs" && !horsCible) ajouter("nature", "Confirmer que le prix achète les murs seuls.");
    if (!["loue", "libre"].includes(c.occupation)) ajouter("occupation", "Préciser si le local est loué ou libre à la vente.");
    const loyerAnnuel = annuel(c.loyer, c.periode_loyer);
    const loyer = loyerAnnuel == null ? null : loyerAnnuel / 12;
    if (!(loyer > 0) || c.base_loyer !== "ht_hc") ajouter("loyer", "Obtenir le loyer global actuel, HT/HC, avec sa période (mois ou année).");
    const charges = annuel(c.charges, c.periode_charges);
    if (charges == null || c.charges_nature !== "bailleur") ajouter("charges", "Chiffrer les charges restant au propriétaire et leur période.");
    if (!["oui", "non"].includes(c.taxe_comprise)) ajouter("taxe_comprise", "Dire si ces charges comprennent la taxe foncière ou si elle est à part.");
    if (c.occupation === "loue") {
      if (!/(?:depuis|debut|effet|jusqu|echeance|restant|\d.{0,5}(?:an|mois)|\d{4}|\d{1,2}\/\d{1,2}\/\d{2,4})/.test(normaliser(c.bail))) ajouter("bail", "Préciser le début du bail ou sa prochaine échéance, au-delà de « 3/6/9 ».");
      if (!["oui", "non"].includes(c.impayes)) ajouter("impayes", "Confirmer les impayés ou retards de paiement récents.");
    }
    if (c.impayes === "oui") risques.push("Impayés ou retards déclarés : montant, ancienneté et régularisation à clarifier avant de compter sur le loyer.");
    if (c.depart === "oui") risques.push("Départ du locataire annoncé : anticiper la vacance, les travaux éventuels et le loyer de relocation.");
    const bail = normaliser(c.bail);
    const dateBail = bail.match(/(?:echeance|jusqu'au|fin (?:du bail|de bail)|se termine).{0,20}?(\d{1,2})\/(\d{1,2})\/(\d{4})/);
    if (dateBail) {
      const [,j,m,a]=dateBail, date=new Date(Date.UTC(Number(a),Number(m)-1,Number(j)));
      const exacte=date.getUTCFullYear()===Number(a) && date.getUTCMonth()===Number(m)-1 && date.getUTCDate()===Number(j);
      const jours=(date.getTime()-Date.now())/86400000;
      if (!exacte) risques.push("La date d’échéance du bail n’est pas une date valide : faites-la préciser.");
      else if (jours<0) risques.push("Échéance passée mentionnée dans la réponse : faire confirmer le renouvellement ou la situation actuelle du bail.");
      else if (exacte && jours<=180) risques.push("Échéance de bail mentionnée dans les six mois : départ, renouvellement et risque de vacance à clarifier.");
    }
    const relocation = annonce.decision?.relocation;
    if ((annonce.flags||[]).includes("dette_copropriete")) risques.push("Dette ou difficulté de copropriété signalée dans l’annonce : obtenir le montant restant et les pièces avant de conclure.");
    if ((annonce.flags||[]).includes("localisation_incoherente")) risques.push("Localisation contradictoire dans l’annonce : confirmer l’adresse du local.");
    if (relocation?.niveau === "vigilance") risques.push(...(relocation.vigilances || ["Signal de vigilance sur la relocation dans l’annonce."]));
    else if (relocation?.niveau !== "favorable") points.push("Demande locative et facilité à relouer toujours à vérifier sur place.");
    const cfg = configuration || {}, recherche = cfg.recherche || {}, analyse = cfg.analyse || {};
    const objectif = Math.max(1, Number(analyse.negociation?.cashflow_cible_mensuel ?? 100));
    const prixVendeur = nombre(c.prix), prix = prixVendeur ?? nombre(annonce.prix);
    if (!(prix>0)) ajouter("prix", "Confirmer le prix demandé pour les murs seuls et les honoraires.");
    let finance = null;
    const p = profil || {};
    const apport = nombre(p.apport), taux = nombre(p.taux), duree = nombre(p.duree);
    const valideProfil = taux != null && taux <= 30 && duree >= 1 && duree <= 40
      && (p.apportMode === "euros" ? nombre(p.apportEuros) != null : apport != null && apport <= 100);
    if (!valideProfil) risques.push("Profil de financement à corriger dans les filtres de la chasse.");
    if (prix > 0 && loyer > 0 && c.base_loyer === "ht_hc" && valideProfil) {
      if (loyer * 12 / prix > .20) risques.push("Loyer incompatible avec le prix retenu : vérifier la période et le montant global avant de conclure.");
      const honoraires = prixVendeur != null && c.prix_base === "inclus" ? 0 : Math.max(0, nombre(annonce.honoraires) || 0);
      const taxeAnnoncee = annuel(c.taxe, c.periode_taxe);
      const taxeEstimee = taxeAnnoncee == null;
      const taxe = taxeAnnoncee ?? loyer * Number(analyse.dossier_banque?.taxe_fonciere_mois_loyer ?? 1);
      const vacance = Number(recherche.vacance_prudente_pct ?? 8) / 100;
      const provisionCharges = Number(recherche.provision_charges_pct ?? 10) / 100;
      const chargesConnues = charges != null && c.charges_nature === "bailleur";
      let frais, fraisStress;
      if (chargesConnues && c.taxe_comprise === "oui") {
        frais = Math.max(charges/12, loyer * provisionCharges + taxe/12);
        fraisStress = Math.max(charges/12, loyer * .9 * provisionCharges + taxe/12);
        if (taxeAnnoncee != null && charges < taxeAnnoncee) risques.push("Les charges indiquées taxe comprise sont inférieures à la taxe : corriger la répartition.");
      } else {
        frais = Math.max(chargesConnues ? charges/12 : 0, loyer * provisionCharges) + taxe/12;
        fraisStress = Math.max(chargesConnues ? charges/12 : 0, loyer * .9 * provisionCharges) + taxe/12;
      }
      const revenu = loyer * (1-vacance) - frais;
      const revenuStress = loyer * .9 * (1-Math.max(2/12, vacance)) - fraisStress;
      const t = taux / 1200, n = duree * 12, coefficient = t ? t/(1-(1+t)**-n) : 1/n;
      const cout = prix * 1.08 + honoraires;
      const apportEuros = p.apportMode === "euros" ? Math.min(Number(p.apportEuros), cout) : cout * apport/100;
      const mensualite = Math.max(0, cout-apportEuros) * coefficient;
      let prixCible = null;
      if (revenu > objectif && (p.apportMode === "euros" || apport < 100)) {
        const coutMax = p.apportMode === "euros" ? (revenu-objectif)/coefficient + Number(p.apportEuros) : (revenu-objectif)/(coefficient*(1-apport/100));
        prixCible = Math.max(0, Math.floor(Math.min(prix, (coutMax-honoraires)/1.08)/1000)*1000);
      } else if (revenu-mensualite >= objectif) prixCible = prix;
      finance = {prix, prixVendeur: prixVendeur != null, loyer, chargesDeclarees: chargesConnues ? charges : null,
        taxe, taxeEstimee, fraisMensuels: frais, chargesComprises: c.taxe_comprise === "oui", mensualite,
        cashflow: Math.round(revenu-mensualite), stress: Math.round(revenuStress-mensualite),
        objectif, prixCible: prixCible > 0 ? prixCible : null, honoraires, apportEuros, cout,
        taux, duree, revenuNetMensuel:revenu, vacancePct: vacance*100, chargesPct: provisionCharges*100};
      if (revenu < objectif) risques.push("Les revenus après charges et provisions ne permettent pas la marge visée, même sans crédit. Une baisse de prix ne suffit pas à elle seule.");
      if (c.occupation !== "loue") points.push("Simulation de relocation : aucun revenu en place garanti pour un local libre ou d’occupation inconnue.");
      if (prixVendeur != null && c.prix_base !== "inclus") points.push("Base du prix et honoraires restant à confirmer ; les honoraires séparés connus de l’annonce sont conservés.");
      if (taxeEstimee) points.push(`Taxe inconnue : provision annuelle de ${Math.round(taxe)} €, déduite du calcul.`);
    }
    let niveau, titre;
    if (horsCible) { niveau = "hors_cible"; titre = "Ce n’est pas une vente des murs seuls"; finance = null; }
    else if (risques.length) { niveau = "vigilance"; titre = "Clarifier les risques avant d’aller plus loin"; }
    else if (c.occupation === "libre") { niveau = "a_clarifier"; titre = "Local libre : le revenu reste à démontrer"; }
    else if (manquants.length || !finance) { niveau = "a_clarifier"; titre = "Il manque encore des informations décisives"; }
    else if (finance.cashflow >= objectif) { niveau = "interessant"; titre = "Chiffres intéressants : préparer la visite et les justificatifs"; }
    else { niveau = "a_negocier"; titre = "À ce prix, la marge visée n’est pas atteinte"; }
    const questions = [];
    const manque = cle => manquants.some(m=>m.cle===cle);
    if (manque("nature")) questions.push("Le prix porte-t-il bien sur les murs seuls, hors fonds et droit au bail ?");
    if (manque("occupation") || manque("bail")) questions.push("Le local est-il loué, et depuis quand ou jusqu’à quelle prochaine échéance de bail ?");
    if (manque("loyer")) questions.push("Quel est le loyer global actuel HT et hors charges, par mois ou par an ?");
    if (manque("charges") || manque("taxe_comprise")) questions.push("Quel montant de charges reste au propriétaire, par mois ou par an, et la taxe foncière est-elle comprise ou à part ?");
    if (manque("impayes")) questions.push("Les loyers sont-ils à jour, sans impayés ou retards récents ?");
    if (manque("prix")) questions.push("Quel est le prix des murs seuls, honoraires inclus ou détaillés ?");
    if (c.impayes === "oui") questions.unshift("Quel est le montant des impayés, depuis quand, et ont-ils été régularisés ?");
    const relance = questions.length ? ["Bonjour,", "", "Merci pour votre retour. Pour terminer mon premier examen, pourriez-vous simplement préciser :", "", ...questions.slice(0,3).map(q=>"- "+q), "", "Merci beaucoup,", "[Votre nom]"].join("\n") : "";
    return {niveau, titre, confirme: !!confirme, manquants, risques, points, finance, relance};
  }
  return {extraire, analyser, nombre, annuel};
})();
