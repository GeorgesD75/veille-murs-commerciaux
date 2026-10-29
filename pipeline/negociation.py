"""Prix de discussion simulés : même barème, revenu constant, aucun envoi."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
import math

from pipeline.config import Config
from pipeline.decision import analyser_decision, analyser_relocation, est_pepite
from pipeline.enrichissement import position_vs_fourchette
from pipeline.fiabilite import diagnostiquer, nombre_positif
from pipeline.filtres import plancher_prix_m2
from pipeline.financement import hypotheses_exploitation, mensualite_credit
from pipeline.modeles import Annonce
from pipeline.scoring import scorer


def simuler_prix(a: Annonce, prix: float, config: Config) -> Annonce:
    """Copie indépendante ; on ne modifie ni le stock, ni les preuves de prix."""
    copie = deepcopy(a)
    copie.prix = prix
    copie.prix_m2 = round(prix / a.surface_m2)
    copie.rendement_brut_pct = round(a.loyer_mensuel * 1200 / prix, 2)
    copie.rendement_acte_en_main_pct = round(a.loyer_mensuel * 1200 / (prix * 1.08 + (a.honoraires or 0)), 2)
    # Médiane exacte utilisée lors de l'enrichissement, jamais reconstruite
    # depuis une décote arrondie ou depuis le milieu de la fourchette.
    mediane = a.marche_prix_m2_median
    if mediane and a.marche_prix_m2_haut:
        copie.position_benchmark = position_vs_fourchette(
            copie.prix_m2, mediane, a.marche_prix_m2_haut,
            config.scoring["prix_m2_vs_benchmark"]["seuil_decote_pct"])
        copie.decote_pct = round((mediane - copie.prix_m2) / mediane * 100, 1)
    else:
        copie.position_benchmark = "inconnu"
        copie.decote_pct = None
    return scorer(copie, config, reference_prix=a)


def plan_negociation(a: Annonce, config: Config, maintenant: datetime) -> dict:
    """Cherche le prix maximal validant pépite ET trésorerie prudente positive.

    La recherche n'est pas monotone : un prix trop bas déclenche les contrôles
    anti-anomalies (rendement/prix au m²). On teste la grille dans son domaine
    plausible, sans désactiver ces contrôles ni gonfler le loyer.
    """
    diagnostic = diagnostiquer(a)
    objectif = max(1, float(config["analyse"].get("negociation", {}).get("cashflow_cible_mensuel", 100)))
    raisons = []
    if diagnostic["transaction"]["nature"] != "murs":
        raisons.append("Confirmer la vente et le prix des murs seuls avant toute proposition immobilière.")
    elif a.exclue or diagnostic["bloquant"]:
        raisons.append("Résoudre les exclusions ou contradictions de la fiche.")
    if datetime.fromisoformat(a.date_derniere_vue) < maintenant - timedelta(days=14):
        raisons.append("Disponibilité et prix à actualiser : annonce non revue depuis plus de 14 jours.")
    if not nombre_positif(a.prix) or not nombre_positif(a.surface_m2):
        raisons.append("Confirmer le prix et la surface avant de calculer une offre.")
    if not nombre_positif(a.loyer_mensuel) or a.loyer_estime or a.loyer_origine == "rendement":
        raisons.append("Obtenir le loyer réel HT/HC ; un loyer estimé ne suffit pas à viser une pépite.")
    if diagnostic["occupation"] != "occupe":
        raisons.append("Confirmer l’occupation et le bail en place.")
    if set(a.flags).intersection({"dette_copropriete", "localisation_incoherente",
                                "prix_m2_anormalement_bas", "rendement_anormalement_eleve", "texte_partiel_alerte"}):
        raisons.append("Clarifier les risques signalés avant de fixer un prix.")
    relocation = analyser_relocation(a)
    resultat = {"statut": "a_documenter", "raisons": raisons, "prix_plafond": None,
                "prix_ouverture": None, "selection": False, "relocation": relocation,
                "objectif_cashflow": objectif}
    if raisons:
        return resultat

    cfg = config["analyse"].get("negociation", {})
    pas = max(1, int(cfg.get("pas_euros", 1000)))
    # Une taxe inconnue ne vaut pas zéro pour décider d'un prix d'achat.
    base = a
    exploitation = hypotheses_exploitation(a, config)
    # Repère financier distinct de la qualification pépite. Il reste utile
    # quand le score ou les contrôles de prix empêchent une recommandation.
    f = config["analyse"]["financement"]
    apport = float(config.scoring.get("financement", {}).get("apport_reference_pct", 20))
    coefficient = mensualite_credit(1, float(f["taux_pct"]), int(f["duree_ans"]))
    revenu_disponible = exploitation["revenu_prudent"] - objectif
    if revenu_disponible > 0 and apport < 100:
        seuil = ((revenu_disponible / ((1 - apport/100) * coefficient)) - (a.honoraires or 0)) / 1.08
        seuil = math.floor(min(a.prix, seuil) / pas) * pas
        if seuil > 0:
            credit = mensualite_credit((seuil * 1.08 + (a.honoraires or 0)) * (1 - apport/100), float(f["taux_pct"]), int(f["duree_ans"]))
            resultat.update({"prix_seuil_financier": seuil,
                             "cashflow_seuil_financier": round(exploitation["revenu_prudent"] - credit),
                             "score_seuil_financier": simuler_prix(a, seuil, config).score,
                             "hypotheses": {"apport_pct": apport, "taux_pct": f["taux_pct"], "duree_ans": f["duree_ans"],
                                            "vacance_pct": exploitation["vacance_pct"], "charges_pct": exploitation["charges_pct"]},
                             "taxe_estimee": exploitation["taxe_estimee"], "taxe_annuelle_retenue": exploitation["taxe_annuelle_retenue"]})
    # Le seuil de cohérence absolu reste celui de diagnostiquer (20 %).
    # Le contrôle à 10 % s'applique au prix OBSERVÉ, pas au seul prix proposé.
    prix_min = max(a.loyer_mensuel * 1200 / 20,
                   (plancher_prix_m2(a.departement, config) or 0) * a.surface_m2)
    minimum = math.ceil(prix_min / pas) * pas
    resultat["prix_min_coherent"] = minimum

    def evaluer(prix):
        simulee = simuler_prix(base, prix, config)
        decision = analyser_decision(simulee, config)
        return simulee, decision, est_pepite(simulee, config) and (decision["cashflow_prudent"] or 0) > 0

    # Prix affiché exact d'abord, puis grille décroissante pour obtenir le
    # plafond sur la grille, y compris aux discontinuités du score marché.
    prix_testes = [a.prix] + list(range(math.floor(a.prix / pas) * pas, minimum - 1, -pas))
    retenue = None
    for prix in dict.fromkeys(prix_testes):
        if prix < prix_min:
            continue
        simulee, decision, valide = evaluer(prix)
        if valide:
            retenue = prix, simulee, decision
            break
    if retenue is None:
        resultat.update(statut="non_atteignable", raisons=[
            f"Aucun prix plausible ne réunit le seuil pépite et l’objectif de {objectif:g} €/mois de cash-flow prudent."])
        return resultat

    plafond, simulee, decision = retenue
    ouverture = max(minimum, math.floor(plafond * (1 - cfg.get("marge_ouverture_pct", 3) / 100) / pas) * pas)
    ouverture = min(plafond, ouverture)
    simulee_ouverture, _, ouverture_valide = evaluer(ouverture)
    if not ouverture_valide:
        ouverture = plafond
        simulee_ouverture = simulee
    remise = round((1 - plafond / a.prix) * 100, 1)
    resultat.update({"statut": "deja_cible" if plafond == a.prix else "a_negocier",
                     "raisons": [], "prix_plafond": plafond, "prix_ouverture": ouverture,
                     "remise_pct": remise, "remise_euros": a.prix - plafond,
                     "score_cible": simulee.score, "score_ouverture": simulee_ouverture.score,
                     "rendement_cible_pct": simulee.rendement_brut_pct,
                     "rendement_simule_eleve": "rendement_eleve_si_negocie" in simulee.flags,
                     "cashflow_cible": decision["cashflow_prudent"], "stress_cible": decision["cashflow_stress"],
                     "cout_total": round(plafond * 1.08 + (a.honoraires or 0)),
                     "apport_reference": round((plafond * 1.08 + (a.honoraires or 0)) * decision["apport_pct"] / 100),
                     "taxe_estimee": exploitation["taxe_estimee"], "taxe_annuelle_retenue": exploitation["taxe_annuelle_retenue"],
                     "pas_euros": pas, "marge_ouverture_pct": cfg.get("marge_ouverture_pct", 3),
                     "selection": plafond < a.prix and remise <= cfg.get("remise_selection_max_pct", 35)
                        and relocation["niveau"] != "vigilance",
                     "hypotheses": {k: decision[k] for k in ["apport_pct", "taux_pct", "duree_ans", "vacance_pct", "charges_pct"]}})
    return resultat
