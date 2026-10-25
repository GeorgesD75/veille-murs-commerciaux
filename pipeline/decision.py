"""Adéquation à la recherche et hypothèses prudentes, séparées du score du bien."""
from __future__ import annotations

from pipeline.config import Config
from pipeline.modeles import Annonce
from pipeline.fiabilite import diagnostiquer


def priorite_recherche(a: Annonce, config: Config) -> dict:
    recherche = config.donnees.get("recherche", {})
    limite = float(recherche.get("surface_max_m2", 40))
    proche = int(recherche.get("trajet_cible_min", 30))
    surface = a.surface_m2
    # < 40 est une préférence, jamais une exclusion : les autres biens restent accessibles.
    petit = surface is not None and 0 < surface < limite
    surface_pts = 40 if petit else (15 if surface and 0 < surface <= limite * 1.25 else 0)
    t = a.temps_trajet_min
    trajet_pts = (30 if t <= 20 else 24 if t <= proche else 12 if t <= 40 else 3) if t is not None else 0
    economie = round(max(0, min(100, a.score or 0)) * .3, 1)
    return {"score": round(surface_pts + trajet_pts + economie), "petite_surface": petit,
            "proche": t is not None and t <= proche,
            "detail": {"surface": surface_pts, "proximite": trajet_pts, "economie": economie}}


def analyser_decision(a: Annonce, config: Config) -> dict:
    """Chiffres avant impôt ; provisions explicites, aucune donnée manquante inventée."""
    cfg = config.donnees.get("recherche", {})
    diagnostic = diagnostiquer(a)
    loyer = a.loyer_mensuel or a.loyer_mensuel_estime
    manquants = []
    if not a.surface_m2:
        manquants.append("Surface privative et surface de vente en rez-de-chaussée")
    if not a.texte_detail:
        manquants.append("Contenu complet de l’annonce et confirmation de la vente des murs seuls")
    if a.loyer_estime or not a.loyer_mensuel:
        manquants.append("Bail signé et loyer réellement encaissé, hors charges et hors taxes")
    else:
        manquants.append("Bail et quittances : le loyer annoncé reste à justifier")
    if a.taxe_fonciere_annuelle is None:
        manquants.append("Montant de la taxe foncière et répartition prévue au bail")
    manquants.extend(["Charges non récupérables, procès-verbaux d’AG et travaux votés"])
    if diagnostic["occupation"] == "libre":
        manquants.append("Dernier bail, date de libération et loyer précédemment encaissé ; travaux de remise en location")
    else:
        manquants.append("Solvabilité du locataire, impayés et prochaine échéance du bail")
    if diagnostic["bloquant"]:
        manquants = [e["texte"] for e in diagnostic["alertes"] if e["niveau"] == "fort"] + manquants
    documente = sum([bool(a.surface_m2), bool(a.texte_detail),
                    bool(a.loyer_mensuel and not a.loyer_estime),
                    a.taxe_fonciere_annuelle is not None, a.bail_echeance_annee is not None])
    risques = [f for f in a.flags if f in {"localisation_incoherente", "dette_copropriete",
              "rendement_anormalement_eleve", "prix_m2_anormalement_bas", "texte_partiel_alerte"}]
    resultat = {"documentation": documente * 20, "questions": manquants, "diagnostic": diagnostic,
                "risques": risques, "loyer_estime": bool(a.loyer_estime or not a.loyer_mensuel),
                "cashflow_prudent": None, "prix_equilibre": None}
    if diagnostic["bloquant"] or not loyer or not a.prix:
        return resultat
    f = config["analyse"]["financement"]
    apport = float(config.scoring.get("financement", {}).get("apport_reference_pct", 20)) / 100
    n = int(f["duree_ans"]) * 12
    t = float(f["taux_pct"]) / 1200
    coefficient = t / (1 - (1 + t) ** -n) if t else 1 / n
    vacance = float(cfg.get("vacance_prudente_pct", 8)) / 100
    charges = float(cfg.get("provision_charges_pct", 10)) / 100
    # Taxe déduite par prudence même si refacturation annoncée : à vérifier au bail.
    taxe = (a.taxe_fonciere_annuelle or 0) / 12
    revenu = loyer * (1 - vacance - charges) - taxe
    mensualite = a.prix * 1.08 * (1-apport) * coefficient
    # Stress explicite : loyer -10 %, deux mois de vacance, mêmes charges en %.
    stress = loyer * .9 * (10/12 - charges) - taxe
    resultat.update({"cashflow_prudent": round(revenu - a.prix * 1.08 * (1-apport) * coefficient),
                     "prix_equilibre": round(max(0, revenu) / ((1-apport)*1.08*coefficient)),
                     "vacance_pct": vacance * 100, "charges_pct": charges * 100,
                     "apport_pct": apport * 100, "taux_pct": f["taux_pct"], "duree_ans": f["duree_ans"],
                     "cashflow_stress": round(stress - mensualite),
                     "rendement_net_prudent": round(revenu * 12 / (a.prix * 1.08) * 100, 2),
                     "couverture_dette": round(revenu / mensualite, 2) if mensualite else None,
                     "effort_annuel_stress": round(max(0, mensualite - stress) * 12)})
    return resultat
