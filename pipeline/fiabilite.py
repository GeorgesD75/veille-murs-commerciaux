"""Provenance déclarative et contrôles explicables ; aucun document certifié."""
from __future__ import annotations

import math
import re

from pipeline.modeles import Annonce
from pipeline.texte import normaliser_texte


def nombre_positif(valeur) -> float | None:
    if isinstance(valeur, bool):
        return None
    try:
        nombre = float(valeur)
        return nombre if math.isfinite(nombre) and nombre > 0 else None
    except (ValueError, TypeError):
        return None


def noter_preuve(a: Annonce, champ: str, valeur, origine: str, quand: str, extrait: str = "") -> None:
    entrees = a.preuves.setdefault(champ, [])
    # Une origine est rafraîchie plutôt qu'empilée à chaque passage.
    entrees[:] = [e for e in entrees if e.get("origine") != origine]
    entrees.append({"valeur": valeur, "origine": origine, "url": a.url,
                    "observe_le": quand, "extrait": extrait[:220]})
    del entrees[:-4]


def diagnostiquer(a: Annonce) -> dict:
    texte = normaliser_texte(a.texte_complet())
    alertes = []
    if a.loyer_origine == "rendement":
        alertes.append({"code": "loyer_deduit", "niveau": "attention", "texte": "Loyer reconstitué à partir du rendement annoncé : montant et base de calcul à obtenir."})
    if a.etat_detail == "retiree":
        alertes.append({"code": "annonce_retiree", "niveau": "fort", "texte": "La fiche indique que l’annonce est retirée ou n’est plus accessible (404/410)."})
    if a.etat_detail == "redirection_liste":
        alertes.append({"code": "fiche_non_identifiee", "niveau": "fort", "texte": "L’ancienne fiche ouvre une page de résultats : disponibilité et informations à confirmer auprès de l’agence."})
    for champ in a.conflits_donnees:
        alertes.append({"code": "conflit_" + champ, "niveau": "fort",
                        "texte": {"prix": "Le prix de la liste et celui de la fiche diffèrent.",
                                  "surface_m2": "Les surfaces de la liste et de la fiche diffèrent.",
                                  "code_postal": "La localisation de la liste et de la fiche diffère."}.get(champ, f"Valeurs contradictoires : {champ}.")})
    for champ in ["prix", "surface_m2", "loyer_mensuel"]:
        valeur = getattr(a, champ)
        if valeur is not None and nombre_positif(valeur) is None:
            alertes.append({"code": "invalide_" + champ, "niveau": "fort", "texte": f"Valeur non exploitable : {champ}."})
    # Une surface totale incluant une cave ne décrit pas la surface commerciale utile.
    if re.search(r"sous[ -]sol|\bcave\b|\bmezzanine\b|surface ponderee|surface utile", texte):
        alertes.append({"code": "surface_a_ventiler", "niveau": "attention",
                        "texte": "Demander la ventilation rez-de-chaussée / réserve / sous-sol et la surface Carrez."})
    occupe = bool(re.search(r"murs occupes|vendu[es]* loue|locataire en place|bail en cours|occupe[es]* par", texte))
    libre = bool(re.search(r"murs libres|local (?:vide|libre)|libre de toute occupation|vendu[es]* libre", texte))
    if occupe and libre:
        alertes.append({"code": "occupation_contradictoire", "niveau": "fort", "texte": "L’annonce évoque à la fois un local libre et occupé : statut à confirmer."})
    statut = "occupe" if occupe and not libre else "libre" if libre and not occupe else "a_confirmer"
    if statut == "a_confirmer":
        alertes.append({"code": "occupation_a_confirmer", "niveau": "attention", "texte": "L’occupation n’est pas explicitement établie dans le texte disponible."})
    prix, loyer = nombre_positif(a.prix), nombre_positif(a.loyer_mensuel)
    if prix and loyer and loyer * 12 / prix > .20:
        alertes.append({"code": "loyer_incoherent", "niveau": "fort", "texte": "Loyer incompatible avec un rendement plausible : vérifier montant et périodicité."})
    if re.search(r"loyer[^.]{0,65}(?:/\s*m[2²]|par\s*m[2²])", texte):
        alertes.append({"code": "unite_loyer", "niveau": "attention", "texte": "Un loyer au m² figure dans le texte : confirmer le loyer annuel global HT/HC."})
    forts = sum(e["niveau"] == "fort" for e in alertes)
    # Ce compteur décrit la cohérence des données, pas une probabilité d'achat sûr.
    return {"alertes": alertes, "bloquant": forts > 0, "occupation": statut,
            "coherence": max(0, 100 - forts * 30 - (len(alertes) - forts) * 8),
            "preuves": a.preuves, "etat_detail": a.etat_detail,
            "date_detail_vue": a.date_detail_vue}
