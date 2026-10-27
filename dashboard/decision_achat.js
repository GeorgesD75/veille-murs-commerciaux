/* Lecture de décision : aucune mutation du score, des prix ou du dossier. */
const DecisionAchat = (() => {
  function analyser(a, contexte = {}) {
    const {projection, projectionCible, retour, prioritaire, pepite, potentiel} = contexte;
    const objectif = contexte.objectif ?? 100;
    const d = a.decision?.diagnostic || {};
    const rue = a.decision?.relocation || a.negociation?.relocation;
    const avis = (niveau, titre, raison, prochaine, origine = "annonce") =>
      ({niveau, titre, raison, prochaine, origine});
    // Une réponse privée relue prime toujours sur le signal historique.
    if (retour) {
      if (!retour.confirme || retour.aRelire || !retour.resultat)
        return avis("completer", "Réponse vendeur à relire", "La sélection est suspendue jusqu’à validation des informations reçues.", "Relire les champs dans le dossier vendeur.", "vendeur");
      const r = retour.resultat;
      if (r.niveau === "hors_cible")
        return avis("vigilance", "Écarter cette vente de votre recherche", r.risques?.[0] || "Le retour vendeur ne confirme pas une vente des murs seuls.", "Ne pas préparer d’offre immobilière sur cette base.", "vendeur");
      if (r.niveau === "vigilance")
        return avis("vigilance", "Lever le risque avant une offre", r.risques?.[0] || "Le dossier vendeur comporte un risque non résolu.", "Clarifier ce point avec le vendeur avant d’avancer.", "vendeur");
      if (r.niveau === "a_clarifier" || r.manquants?.length || !r.finance)
        return avis("completer", "Compléter le dossier avant de décider", r.manquants?.[0]?.texte || r.risques?.[0] || "Les informations reçues ne suffisent pas pour retenir un prix.", "Utiliser la courte relance préparée dans le dossier vendeur.", "vendeur");
      if (r.niveau === "a_negocier")
        return avis("negociation", "Négocier sur les chiffres du vendeur", "Le prix retenu laisse une marge mensuelle insuffisante ; le prix cible ci-dessous utilise les informations relues.", "Confirmer les justificatifs avant de discuter ce prix.", "vendeur");
      if (r.niveau === "interessant")
        return avis("favorable", "Avancer vers une visite et les justificatifs", "Les déclarations relues satisfont le premier examen financier. Elles restent à justifier par les pièces.", "Vérifier le bail, les encaissements et les charges avant une offre.", "vendeur");
      return avis("completer", "Analyse vendeur à actualiser", "Le résultat disponible ne permet pas de retenir une recommandation.", "Ouvrir et relire le dossier vendeur.", "vendeur");
    }
    if (a.peut_etre_retiree)
      return avis("completer", "Reconfirmer la disponibilité", "Cette annonce est ancienne ou signalée indisponible ; son prix peut avoir changé.", "Demander si les murs sont toujours à vendre et à quel prix.");
    if (d.transaction && d.transaction.nature !== "murs")
      return avis("vigilance", "Confirmer ce qui est réellement vendu", d.transaction.motif || "La vente des murs seuls n’est pas établie.", "Demander si le prix concerne le local immobilier, hors fonds et droit au bail.");
    if (d.bloquant)
      return avis("vigilance", "Chiffres à clarifier avant toute offre", d.alertes?.find(e => e.niveau === "fort")?.texte || "Des données incohérentes empêchent une simulation fiable.", "Faire confirmer les montants et leur périodicité au vendeur.");
    const risques = {
      dette_copropriete: "Une dette ou procédure de copropriété est signalée.",
      localisation_incoherente: "La localisation annoncée comporte une incohérence.",
      rendement_anormalement_eleve: "Le rendement annoncé est inhabituellement élevé.",
      prix_m2_anormalement_bas: "Le prix au mètre carré demande une vérification.",
      texte_partiel_alerte: "Le contenu lu est incomplet et peut masquer une restriction de vente."
    };
    const risque = (a.flags || []).find(f => risques[f]);
    if (risque)
      return avis("vigilance", "Vérifier ce signal avant de chiffrer une offre", risques[risque], "Lever ce point avec le vendeur ; le score ne suffit pas.");
    if (!(a.loyer_mensuel > 0) || a.loyer_estime || a.decision?.loyer_estime || a.loyer_origine === "rendement")
      return avis("completer", "Obtenir le loyer réel avant de négocier", "Un revenu estimé ou reconstitué ne permet pas de retenir un prix d’achat fiable.", "Demander le loyer mensuel HT/HC et si le local est actuellement loué.");
    if (d.occupation !== "occupe")
      return avis("completer", d.occupation === "libre" ? "Chiffrer la mise en location" : "Confirmer l’occupation du local", "Un loyer annoncé ne garantit pas un revenu encaissé dès l’achat.", "Vérifier le bail en cours ou le délai, les travaux et le loyer réaliste de relocation.");
    if (rue?.niveau === "vigilance")
      return avis("vigilance", "Valider l’emplacement avant de négocier", rue.vigilances?.[0] || "Des points de vigilance sur la relocation sont signalés.", "Vérifier l’adresse, les locaux vacants et les activités autorisées sur place.");
    if (prioritaire)
      return avis("favorable", "À contacter en priorité", "Nouvelle annonce avec signal pépite et objectif de trésorerie atteint au prix affiché avec votre financement.", "Confirmer rapidement disponibilité, loyer encaissé, bail et absence d’impayés.");
    if (pepite && projection?.cashflow >= objectif)
      return avis("favorable", "À contacter · chiffres prometteurs", "Le signal pépite et votre objectif de trésorerie sont réunis au prix affiché, sous réserve des données annoncées.", "Confirmer le bail, les charges à votre charge et l’absence d’impayés.");
    if (a.negociation?.prix_plafond != null && projectionCible?.cashflow != null && projectionCible.cashflow < objectif)
      return avis("vigilance", "Le plafond du modèle ne suffit pas", "Avec votre financement, ce prix n’atteint pas l’objectif mensuel. Le score simulé ne garantit pas votre trésorerie.", "Tester un prix inférieur ou un autre financement avant de préparer une offre.");
    if (potentiel && projectionCible?.cashflow >= objectif)
      return avis("negociation", "À négocier · potentiel à prix réduit", "Sélectionnée pour son potentiel après négociation. Au prix demandé, elle ne réunit pas les mêmes conditions.", "Confirmer les revenus et charges, puis tester la marge de discussion du vendeur.");
    if (projection?.cashflow == null)
      return avis("completer", "Compléter les chiffres avant de décider", "Le scénario prudent n’est pas calculable avec les données ou le financement actuels.", "Vérifier prix, loyer et paramètres du prêt.");
    if (projection.cashflow < 0)
      return avis("negociation", "Prix à revoir pour éviter un effort mensuel", "Au prix affiché, les revenus après provisions ne couvrent pas votre crédit.", "Étudier le prix cible s’il est disponible, puis confirmer les chiffres avec le vendeur.");
    if (projection.cashflow < objectif)
      return avis("negociation", "Cash-flow positif, marge limitée", "Le scénario prudent reste positif mais n’atteint pas votre objectif mensuel.", "Chercher une marge sur le prix ; vérifier les charges et le risque de vacance.");
    return avis("completer", "Chiffres à approfondir", "Le scénario prudent atteint l’objectif ; le dossier ne réunit pas tous les critères du signal pépite.", "Vérifier le bail, les encaissements et la facilité à relouer avant de se positionner.");
  }
  return {analyser};
})();
