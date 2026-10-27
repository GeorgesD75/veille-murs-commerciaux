"""Collecte bornée sans emails : python scripts/actualiser_ciblee.py --pages 1 --details 8.

Ne lit pas la boîte IMAP et ne déclenche aucune notification. Conserve l'état
de la dernière tournée complète, avec un rapport distinct de collecte ciblée.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from pipeline.approfondissement import approfondir_annonces
from pipeline.config import Config
from pipeline.filtres import raison_exclusion
from pipeline.geo import Trajets
from pipeline.normalisation import maintenant_iso
from pipeline.stockage import Stockage
from run import integrer
from sources.bienici import SourceBienici
from sources.bureauxlocaux import SourceBureauxLocaux
from sources.pointdevente import SourcePointDeVente
from sources.cessionpme import SourceCessionPme
from sources.papcommerces import SourcePapCommerces
from pipeline.transaction import qualifier_transaction
from scripts.regenerer_dashboard import main as regenerer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pages", type=int, default=1, choices=range(1, 21))
    parser.add_argument("--details", type=int, default=8, choices=range(0, 121))
    parser.add_argument("--budget-details", type=int, default=150, choices=range(30, 901))
    parser.add_argument("--sources", nargs="+", choices=["pointdevente","bureauxlocaux","bienici","cessionpme","papcommerces"],
                        default=["pointdevente","bureauxlocaux","bienici"])
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    config = Config.charger()
    stockage = Stockage(RACINE / "data/annonces.json")
    annonces, meta = stockage.charger()
    quand = maintenant_iso()
    rapport = {"date": quand, "sources": {}, "nouvelles": 0}
    # Les deux départements les plus proches d'abord ; cette collecte est volontairement partielle.
    fabriques = {"pointdevente": lambda: SourcePointDeVente(max_pages=args.pages),
                 "bureauxlocaux": lambda: SourceBureauxLocaux(departements=["75","92","93","94"],max_pages=args.pages),
                 "bienici": lambda: SourceBienici(max_pages=args.pages),
                 "cessionpme": lambda: SourceCessionPme(max_pages=args.pages),
                 "papcommerces": lambda: SourcePapCommerces(max_pages=args.pages)}
    sources = [fabriques[nom]() for nom in dict.fromkeys(args.sources)]
    for source in sources:
        try:
            brutes = source.collecter()
            nouveaux = integrer(brutes, annonces, config, quand)
            rapport["nouvelles"] += len(nouveaux)
            rapport["sources"][source.nom] = {"statut": "ok", "annonces": len(brutes),
                                                 "nouvelles": len(nouveaux), "partielle": True,
                                                 "avertissements": source.avertissements}
            rapport["sources"][source.nom]["collecte"] = dict(source.rapport_collecte)
            logging.info("%s : %s annonces, %s nouveaux identifiants, %s",source.nom,len(brutes),len(nouveaux),source.rapport_collecte)
        except Exception as exc:
            rapport["sources"][source.nom] = {"statut": "erreur", "message": str(exc), "partielle": True}
    trajets = Trajets.charger(RACINE / "data/trajets.json")
    for a in annonces.values():
        a.raison_exclusion = raison_exclusion(a, config, trajets)
        a.exclue = a.raison_exclusion is not None
    config.donnees["analyse"]["approfondissement"].update(max_par_run=args.details, budget_secondes=args.budget_details)
    rapport["details"] = approfondir_annonces(annonces, config)
    rapport["natures_stock"] = {}
    for a in annonces.values():
        a.raison_exclusion = raison_exclusion(a, config, trajets)
        a.exclue = a.raison_exclusion is not None
        if a.exclue:
            continue
        nature = qualifier_transaction(a)["nature"]
        rapport["natures_stock"][nature] = rapport["natures_stock"].get(nature,0)+1
    meta["collecte_ciblee"] = rapport
    historique = meta.setdefault("historique_collectes_ciblees", [])
    historique.append(rapport)
    del historique[:-10]
    stockage.sauvegarder(annonces, meta)
    regenerer(persister=True)
    print(rapport)


if __name__ == "__main__":
    main()
