"""Score /100 d'une annonce. Toute la formule est paramétrée par config.yaml."""
from __future__ import annotations

from pipeline.config import Config
from pipeline.geo import categorie_emplacement
from pipeline.modeles import Annonce
from pipeline.texte import cle_commune, normaliser_texte

# Enveloppe des bonus/malus (le poste vaut « 5 pts » dans la formule).
BONUS_MIN = -3.0
BONUS_MAX = 5.0


def _points_rendement(annonce: Annonce, cfg: dict, categorie: str) -> float:
    p = cfg["rendement"]
    r = annonce.rendement_brut_pct
    if r is None:
        return 0.0
    # Échelle PAR ZONE : un rendement se juge contre ce que son marché exige
    # (9 % en grande couronne est ordinaire, 8 % dans Paris est un trophée) —
    # sans quoi la périphérie truste mécaniquement le haut du classement.
    zone = (p.get("par_zone") or {}).get(categorie) or {}
    plancher = float(zone.get("plancher", p["pct_plancher"]))
    plafond = float(zone.get("plafond", p["pct_plafond"]))
    part = (r - plancher) / (plafond - plancher)
    points = max(0.0, min(1.0, part)) * p["points"]
    if annonce.loyer_estime:
        # Un loyer adossé à des baux RÉELS voisins est bien plus solide qu'une
        # moyenne de zone (ou qu'une promesse de vendeur) : pénalité réduite.
        if annonce.loyer_confiance == "comparables":
            penalite = cfg.get("penalite_loyer_estime_comparables", cfg["penalite_loyer_estime"])
        else:
            penalite = cfg["penalite_loyer_estime"]
        points = max(0.0, points - penalite)
    return points


def _points_emplacement(annonce: Annonce, cfg: dict, categorie: str) -> float:
    points = float(cfg["emplacement"][categorie])
    # Signal rue par rue (Base Adresse Nationale + OpenStreetMap), quand disponible :
    # ajuste le palier administratif sans jamais dépasser son enveloppe (25 pts).
    rue_cfg = cfg.get("rue") or {}
    if annonce.rue_categorie:
        points += float((rue_cfg.get("ajustement") or {}).get(annonce.rue_categorie, 0))
        seuil_vacance = rue_cfg.get("malus_vacance_seuil")
        if (
            seuil_vacance is not None
            and annonce.rue_nb_vacants is not None
            and annonce.rue_nb_vacants >= seuil_vacance
        ):
            points += float(rue_cfg.get("malus_vacance_points", 0))
    plafond = float(cfg["emplacement"]["paris"])  # enveloppe maximale de la catégorie
    return max(0.0, min(plafond, points))


def _points_benchmark(annonce: Annonce, cfg: dict) -> float:
    return float(cfg["prix_m2_vs_benchmark"].get(annonce.position_benchmark, 0))


def _points_proximite(annonce: Annonce, cfg: dict) -> float:
    t = annonce.temps_trajet_min
    if t is None:
        return 0.0
    p = cfg["proximite"]
    if t < 20:
        return float(p["moins_de_20_min"])
    if t <= 40:
        return float(p["de_20_a_40_min"])
    return float(p["de_40_a_60_min"])


def _points_quartier(annonce: Annonce, cfg: dict) -> float:
    """Attachement au quartier : bonus plein si le bien est dans le 18e."""
    q = cfg["quartier"]
    return float(q["points"]) if annonce.code_postal in q["codes_postaux"] else 0.0


def _points_bonus_malus(annonce: Annonce, cfg: dict) -> tuple[float, list[str]]:
    """Points bornés + noms des règles déclenchées (affichés comme faits sourcés)."""
    texte = normaliser_texte(annonce.texte_complet())
    total = 0.0
    detectes: list[str] = []
    for regle in cfg["bonus_malus"]:
        if any(normaliser_texte(mot) in texte for mot in regle["mots"]):
            total += regle["points"]
            detectes.append(regle["nom"])
    # Classe énergie (détectée par regex dans l'enrichissement, pas par mots-clés :
    # « DPE G » dans « DPE gratuit » ne doit jamais matcher). Une passoire F/G se
    # paie en charges du locataire, en décote de revente et en frilosité bancaire ;
    # l'absence de mention reste neutre — la plupart des annonces ne disent rien.
    dpe_cfg = cfg.get("dpe") or {}
    if annonce.dpe_classe in ("F", "G"):
        total += float(dpe_cfg.get("malus_passoire", 0))
        detectes.append("dpe_passoire")
    elif annonce.dpe_classe in ("A", "B"):
        total += float(dpe_cfg.get("bonus_vertueux", 0))
        detectes.append("dpe_vertueux")
    return max(BONUS_MIN, min(BONUS_MAX, total)), detectes


def _points_financement(annonce: Annonce, cfg: dict, config: Config) -> float:
    """Le bien s'autofinance-t-il à un apport et un taux DE RÉFÉRENCE (fixes,
    indépendants du profil personnel affiché sur le dashboard) ? Sans quoi
    deux visiteurs avec des profils différents verraient des scores différents
    pour la même annonce — le score doit rester comparable d'un bien à l'autre.
    """
    fcfg = cfg.get("financement") or {}
    plein = float(fcfg.get("points", 5))
    loyer = annonce.loyer_mensuel or annonce.loyer_mensuel_estime
    if not loyer or not annonce.prix:
        return 0.0
    financement = config["analyse"]["financement"]
    apport_pct = float(fcfg.get("apport_reference_pct", 20)) / 100
    cout_acte_en_main = annonce.prix * 1.08
    emprunt = cout_acte_en_main * (1 - apport_pct)
    if emprunt <= 0:
        cash_flow = loyer
    else:
        t = float(financement["taux_pct"]) / 100 / 12
        n = int(financement["duree_ans"]) * 12
        mensualite = emprunt * t / (1 - (1 + t) ** -n)
        cash_flow = loyer - mensualite
    if cash_flow >= 0:
        return plein
    # Léger déficit (< 10 % du loyer, par défaut) : encore finançable de justesse.
    tolerance = float(fcfg.get("tolerance_deficit_pct", 10)) / 100
    if cash_flow >= -loyer * tolerance:
        return round(plein * 0.6, 1)
    return 0.0


def _points_fiscalite(annonce: Annonce, cfg: dict) -> tuple[float, list[str]]:
    """Signaux fiscaux détectés dans l'annonce (souvent absents : neutre, ni
    bonus ni malus — une info manquante n'est pas une mauvaise nouvelle)."""
    fcfg = cfg.get("fiscalite") or {}
    plein = float(fcfg.get("points", 5))
    texte = normaliser_texte(annonce.texte_complet())
    total = float(fcfg.get("base_neutre", plein / 2))
    detectes: list[str] = []
    for regle in fcfg.get("regles", []):
        if any(normaliser_texte(mot) in texte for mot in regle["mots"]):
            total += regle["points"]
            detectes.append(regle["nom"])
    return max(0.0, min(plein, total)), detectes


def scorer(annonce: Annonce, config: Config) -> Annonce:
    cfg = config.scoring
    categorie = categorie_emplacement(
        annonce.ville, annonce.departement, annonce.texte_complet(), cfg["communes_dynamiques"]
    )
    points_bonus, annonce.bonus_detectes = _points_bonus_malus(annonce, cfg)
    points_fiscalite, annonce.fiscalite_detectes = _points_fiscalite(annonce, cfg)
    detail = {
        "rendement": round(_points_rendement(annonce, cfg, categorie), 1),
        "emplacement": round(_points_emplacement(annonce, cfg, categorie), 1),
        "prix_m2_vs_benchmark": round(_points_benchmark(annonce, cfg), 1),
        "financement": round(_points_financement(annonce, cfg, config), 1),
        "fiscalite": round(points_fiscalite, 1),
        "proximite": round(_points_proximite(annonce, cfg), 1),
        "quartier": round(_points_quartier(annonce, cfg), 1),
        "bonus_malus": round(points_bonus, 1),
    }
    annonce.detail_score = detail
    annonce.score = int(round(max(0.0, min(100.0, sum(detail.values())))))

    annonce.flags = []
    if annonce.departement == "75" and annonce.ville and cle_commune(annonce.ville) != "paris":
        # Ville de banlieue + code postal parisien : l'emplacement a été jugé
        # par la ville (voir geo.categorie_emplacement) — signalé à l'acheteur,
        # l'adresse réelle est à vérifier avant toute démarche.
        annonce.flags.append("localisation_incoherente")
    if annonce.loyer_estime:
        annonce.flags.append("loyer_estime")
    if "dette_copropriete" in annonce.bonus_detectes:
        # Information vitale, distincte d'un simple malus de score : l'acheteur
        # hérite de la dette au prorata — signalé en clair, jamais juste chiffré.
        annonce.flags.append("dette_copropriete")
    if (
        annonce.rendement_brut_pct is not None
        and annonce.rendement_brut_pct > cfg["seuil_alerte_rendement_pct"]
    ):
        # « Trop beau pour être vrai » : souvent une cession de bail ou un fonds
        # déguisé. Signalé ⚠️ ET plafonné sous le seuil d'affichage, pour qu'un
        # piège ne trône jamais en haut du panier ni ne déclenche l'email pépite.
        annonce.flags.append("rendement_anormalement_eleve")
        plafond = int(cfg["seuils"].get("affichage", cfg["seuils"]["orange"])) - 1
        annonce.score = min(annonce.score, plafond)

    rendement_min_vert = cfg["seuils"].get("rendement_minimum_vert")
    if rendement_min_vert is not None and (
        annonce.rendement_brut_pct is None
        or annonce.rendement_brut_pct < float(rendement_min_vert)
    ):
        # Garde-fou du haut du panier : le projet vit du CASH-FLOW. Un bien peut
        # briller partout (emplacement, décote, quartier) et rester incapable de
        # payer son crédit — les points d'emplacement ne remboursent rien. Sous
        # le rendement minimal, le score est plafonné juste sous « vert » : le
        # bien reste visible et bien classé, mais jamais trône ni email pépite.
        annonce.flags.append("rendement_sous_objectif")
        annonce.score = min(annonce.score, int(cfg["seuils"]["vert"]) - 1)
    return annonce
