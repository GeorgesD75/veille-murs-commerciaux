"""Score /100 d'une annonce. Toute la formule est paramétrée par config.yaml."""
from __future__ import annotations

from pipeline.config import Config
from pipeline.geo import categorie_emplacement
from pipeline.modeles import Annonce
from pipeline.texte import normaliser_texte

# Enveloppe des bonus/malus (le poste vaut « 5 pts » dans la formule).
BONUS_MIN = -3.0
BONUS_MAX = 5.0


def _points_rendement(annonce: Annonce, cfg: dict) -> float:
    p = cfg["rendement"]
    r = annonce.rendement_brut_pct
    if r is None:
        return 0.0
    part = (r - p["pct_plancher"]) / (p["pct_plafond"] - p["pct_plancher"])
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


def _points_emplacement(annonce: Annonce, cfg: dict) -> float:
    categorie = categorie_emplacement(
        annonce.ville, annonce.departement, annonce.texte_complet(), cfg["communes_dynamiques"]
    )
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
    return max(BONUS_MIN, min(BONUS_MAX, total)), detectes


def scorer(annonce: Annonce, config: Config) -> Annonce:
    cfg = config.scoring
    points_bonus, annonce.bonus_detectes = _points_bonus_malus(annonce, cfg)
    detail = {
        "rendement": round(_points_rendement(annonce, cfg), 1),
        "emplacement": round(_points_emplacement(annonce, cfg), 1),
        "prix_m2_vs_benchmark": round(_points_benchmark(annonce, cfg), 1),
        "proximite": round(_points_proximite(annonce, cfg), 1),
        "quartier": round(_points_quartier(annonce, cfg), 1),
        "bonus_malus": round(points_bonus, 1),
    }
    annonce.detail_score = detail
    annonce.score = int(round(max(0.0, min(100.0, sum(detail.values())))))

    annonce.flags = []
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
    return annonce
