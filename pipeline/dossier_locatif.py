"""Faits locatifs explicitement annoncés, avec extraits et contradictions."""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import re

from pipeline.texte import normaliser_texte

_NOMBRE = r"(?:\d{1,3}(?:[ .]\d{3})+|\d+)(?:[.,]\d+)?"
_RDC = r"(?:rez[- ]de[- ]chaussee|r\.?d\.?c\.?)"
_LIBELLES = {"rdc_m2": "Surface en rez-de-chaussée", "vente_m2": "Surface de vente",
             "sous_sol_m2": "Surface en sous-sol", "reserve_m2": "Surface de réserve",
             "vitrine_m": "Longueur de vitrine", "extraction": "Extraction",
             "activites": "Activités autorisées", "taxe_annuelle": "Taxe foncière annuelle",
             "charges_bailleur_annuelles": "Charges annuelles restant au bailleur"}


def _montant(s):
    s = s.replace(" ", "")
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", s):
        s = s.replace(".", "")
    return float(s.replace(",", "."))


@lru_cache(maxsize=4096)
def _extraire(titre: str, description: str, detail: str, total: float | None) -> dict:
    observations = {}

    def ajouter(cle, valeur, origine, extrait, position=0):
        liste = observations.setdefault(cle, [])
        if not any(e["valeur"] == valeur and e["origine"] == origine for e in liste):
            if len(extrait) > 240:
                debut = max(0, position-70)
                extrait = ("…" if debut else "") + normaliser_texte(extrait)[debut:debut+230]
            liste.append({"valeur": valeur, "origine": origine, "extrait": extrait.strip()[:240]})

    noms = {"rdc_m2": _RDC, "vente_m2": r"surface (?:de )?vente",
            "sous_sol_m2": r"sous[- ]sol", "reserve_m2": r"reserve"}
    for origine, source in [("titre", titre), ("description", description), ("fiche détaillée", detail)]:
        for phrase in re.split(r"[;\n]|(?<=[.!?])\s+", source):
            t = normaliser_texte(phrase)
            if not t:
                continue
            for cle, nom in noms.items():
                motifs = [rf"\b{nom}\s*(?:d'une surface de|d'environ|de|:|environ)?\s*({_NOMBRE})\s*m2\b",
                          rf"\b({_NOMBRE})\s*m2\s*(?:situes?\s*)?(?:en|au|de|du)?\s*{nom}\b"]
                for motif in motifs:
                    for m in re.finditer(motif, t):
                        valeur = _montant(m.group(1))
                        if 0 < valeur <= 10000:
                            ajouter(cle, valeur, origine, phrase, m.start())
            for motif in [rf"(?:vitrine|facade|lineaire de vitrine)\s*(?:de|:|d'environ)?\s*({_NOMBRE})\s*(?:metres?|m)\b(?!2)",
                          rf"\b({_NOMBRE})\s*(?:metres?|m)\s*(?:de )?(?:vitrine|facade)\b"]:
                for m in re.finditer(motif, t):
                    v = _montant(m.group(1))
                    if 0 < v < 150:
                        ajouter("vitrine_m", v, origine, phrase, m.start())
            if re.search(r"sans extraction|pas d['’]extraction|extraction (?:interdite|impossible|non autorisee)|absence d['’]extraction", t):
                ajouter("extraction", "Absente ou interdite selon l’annonce", origine, phrase)
            elif not re.search(r"a creer|a installer|possibilite|sous reserve", t) and re.search(r"extraction (?:existante|presente)|avec (?:une )?extraction|conduit d['’]extraction existant", t):
                ajouter("extraction", "Existante selon l’annonce", origine, phrase)
            if re.search(r"sauf restauration|hors restauration|restauration interdite|interdiction de restauration|pas de restauration", t):
                ajouter("activites", "Restauration exclue selon l’annonce", origine, phrase)
            elif re.search(r"sans nuisances?|hors nuisances?|activites limitees", t):
                ajouter("activites", "Activités restreintes selon l’annonce", origine, phrase)
            elif re.search(r"tous commerces|tout commerce|toutes activites", t):
                ajouter("activites", "Toutes activités annoncées, à vérifier au bail", origine, phrase)
            taxe = re.search(rf"taxe fonciere\s*(?:(?P<periode>annuelle|mensuelle)\s*)?(?:de|:|est de|s['’]eleve a)?\s*(?P<montant>{_NOMBRE})\s*(?:€|euros?)", t)
            if taxe:
                v = _montant(taxe.group("montant"))
                if taxe.group("periode") == "mensuelle" or re.match(r"\s*(?:/\s*mois\b|par mois\b|mensuelles?\b)", t[taxe.end():]):
                    v *= 12
                if 0 <= v <= 100000:
                    ajouter("taxe_annuelle", v, origine, phrase, taxe.start())
            charges = re.search(rf"charges\s+(?:non recuperables|(?:du )?(?:bailleur|proprietaire)|restant au proprietaire)\s*(?:annuelles\s*)?(?:de|:|est de)?\s*({_NOMBRE})\s*(?:€|euros?)\s*(/mois|par mois|mensuelles?|/an|par an|annuelles?)", t)
            if charges:
                v = _montant(charges.group(1)) * (12 if "mois" in charges.group(2) or "mensuel" in charges.group(2) else 1)
                ajouter("charges_bailleur_annuelles", v, origine, phrase, charges.start())
    champs, alertes = {}, []
    for cle, preuves in observations.items():
        valeurs = list(dict.fromkeys(p["valeur"] for p in preuves))
        # Les restrictions précisent souvent « toutes activités » dans l’extrait
        # de liste ; cela ne constitue pas une autorisation générale concurrente.
        if cle == "activites" and len(valeurs) > 1:
            valeurs = [v for v in valeurs if not v.startswith("Toutes activités")]
        conflit = len(valeurs) > 1
        champs[cle] = {"libelle": _LIBELLES[cle], "valeur": None if conflit else valeurs[0],
                       "statut": "contradictoire" if conflit else "annonce", "preuves": preuves[:4]}
        if conflit:
            alertes.append(f"{_LIBELLES[cle]} : plusieurs valeurs annoncées, à faire confirmer.")
    def valeur(cle):
        return champs.get(cle, {}).get("valeur")
    rdc, sous_sol = valeur("rdc_m2"), valeur("sous_sol_m2")
    if total and rdc and sous_sol and rdc+sous_sol > total*1.1:
        alertes.append("La somme rez-de-chaussée / sous-sol dépasse la surface totale annoncée.")
    return {"champs": champs, "alertes": alertes,
            "sous_sol_majoritaire": bool(rdc and sous_sol and sous_sol > rdc),
            "sous_sol_signale": bool(re.search(r"sous[- ]sol|\bcave\b", normaliser_texte(description+" "+detail)))}


def analyser_dossier(a) -> dict:
    resultat = deepcopy(_extraire(a.titre, a.description, a.texte_detail, a.surface_m2))
    for champ in resultat["champs"].values():
        for preuve in champ["preuves"]:
            preuve["url"] = a.url
            preuve["observe_le"] = a.date_detail_vue if preuve["origine"] == "fiche détaillée" else a.date_derniere_vue
    return resultat
