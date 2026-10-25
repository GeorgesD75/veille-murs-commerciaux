"""Retire les anciens enrichissements issus de pages de résultats identifiées."""
import sys
import re
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from pipeline.stockage import Stockage
from pipeline.normalisation import maintenant_iso
from sources.extraction import loyer_mensuel_depuis_texte
from scripts.regenerer_dashboard import main as regenerer


def nettoyer(annonces):
    rapport = {"fiches_nettoyees": 0, "loyers_retires_ou_corriges": 0}
    for a in annonces.values():
        if not re.search(r"Vente commerces? .{0,80}?\d+\s+annonces?", a.texte_detail, re.I):
            continue
        # Garde le loyer si une source indépendante de la page de détail le déclare.
        source_loyer = any(p.get("origine", "").startswith("source:") and p.get("valeur") == a.loyer_mensuel
                            for p in a.preuves.get("loyer_mensuel", []))
        if not source_loyer:
            loyer = loyer_mensuel_depuis_texte(a.description, a.prix, a.surface_m2)
            if a.loyer_mensuel != loyer:
                rapport["loyers_retires_ou_corriges"] += 1
            a.loyer_mensuel = loyer
        for champ, preuves in list(a.preuves.items()):
            a.preuves[champ] = [p for p in preuves if not p.get("origine", "").startswith("fiche:")]
            if not a.preuves[champ]:
                del a.preuves[champ]
        a.texte_detail = ""
        a.etat_detail, a.approfondie = "redirection_liste", True
        a.date_detail_tentative, a.date_detail_vue = maintenant_iso(), None
        a.critique_ia, a.critique_ia_prix = None, None
        a.rue_evaluee = False
        for champ in ["rue_voie", "rue_nb_commerces", "rue_nb_vacants", "rue_categorie", "rue_distance_metro_m"]:
            setattr(a, champ, None)
        rapport["fiches_nettoyees"] += 1
    return rapport


if __name__ == "__main__":
    stockage = Stockage(RACINE / "data/annonces.json")
    annonces, meta = stockage.charger()
    rapport = nettoyer(annonces)
    cumul = meta.get("nettoyage_fiches", {})
    meta["nettoyage_fiches"] = {"date": maintenant_iso(),
        **{cle: cumul.get(cle, 0) + valeur for cle, valeur in rapport.items()},
        "dernier_passage": rapport}
    stockage.sauvegarder(annonces, meta)
    regenerer(persister=True)
    print(rapport)
