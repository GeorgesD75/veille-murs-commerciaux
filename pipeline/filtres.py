"""Filtres d'exclusion, appliqués AVANT tout scoring."""
from __future__ import annotations

from pipeline.config import Config
from pipeline.geo import GRANDE_COURONNE, ILE_DE_FRANCE, PETITE_COURONNE, Trajets
from pipeline.modeles import Annonce
from pipeline.texte import normaliser_texte


def _mentionne_murs(texte_normalise: str) -> bool:
    return "murs" in texte_normalise


def detecter_fonds_de_commerce(annonce: Annonce, config: Config) -> str | None:
    """Piège n°1 du secteur : fonds de commerce ou droit au bail déguisé en murs."""
    texte = normaliser_texte(annonce.texte_complet())
    murs = _mentionne_murs(texte)
    for mot in config.filtres["mots_toujours_eliminatoires"]:
        if normaliser_texte(mot) in texte:
            return f"mot-clé éliminatoire « {mot} »"
    for mot in config.filtres["mots_eliminatoires_sauf_murs"]:
        if normaliser_texte(mot) in texte and not murs:
            return f"mot-clé « {mot} » sans mention explicite des murs"
    return None


def plancher_prix_m2(departement: str, config: Config) -> float | None:
    """Prix/m² plancher plausible du département, ou None hors zone connue.

    Partagé avec le scoring (pipeline/scoring.py) : un prix/m² sous ce seuil
    est TOUJOURS statistiquement improbable pour des murs commerciaux, que
    « murs » soit mentionné ou non dans l'annonce — seul le filtre d'EXCLUSION
    ci-dessous fait cette distinction (elle sert à démasquer un fonds de
    commerce déguisé, pas à juger la plausibilité générale du prix).
    """
    if departement == "75":
        return config.filtres["prix_m2_plancher_paris"]
    if departement in PETITE_COURONNE:
        return config.filtres["prix_m2_plancher_petite_couronne"]
    if departement in GRANDE_COURONNE:
        return config.filtres["prix_m2_plancher_grande_couronne"]
    return None


def controle_coherence_prix(annonce: Annonce, config: Config) -> str | None:
    """Un prix/m² anormalement bas trahit souvent un fonds ou un droit au bail."""
    if not annonce.prix or not annonce.surface_m2:
        return None
    plancher = plancher_prix_m2(annonce.departement, config)
    if plancher is None:
        return None
    prix_m2 = annonce.prix / annonce.surface_m2
    if prix_m2 < plancher and not _mentionne_murs(normaliser_texte(annonce.texte_complet())):
        return (
            f"suspect_fonds : {prix_m2:.0f} €/m² sous le plancher de {plancher} €/m² "
            "sans mention explicite des murs"
        )
    return None


def raison_exclusion(annonce: Annonce, config: Config, trajets: Trajets) -> str | None:
    """Retourne la raison d'exclusion, ou None si l'annonce passe tous les filtres.

    Effet de bord assumé : renseigne annonce.temps_trajet_min (réutilisé par le scoring).
    """
    if annonce.prix is None:
        return "prix non renseigné"
    b = config.budget
    if not (b["prix_min_filtre"] <= annonce.prix <= b["prix_max_filtre"]):
        return f"prix hors budget ({annonce.prix:,.0f} €)".replace(",", " ")

    if annonce.departement not in ILE_DE_FRANCE:
        return f"hors Île-de-France (département {annonce.departement or 'inconnu'})"
    temps = trajets.temps_depuis_paris18(annonce.ville, annonce.departement, annonce.code_postal)
    annonce.temps_trajet_min = temps
    if temps is not None and temps > config.zone["temps_trajet_max_min"]:
        return f"trop loin du domicile — rue Francoeur, 18e (~{temps} min de transport)"

    raison = detecter_fonds_de_commerce(annonce, config)
    if raison:
        return raison
    return controle_coherence_prix(annonce, config)
