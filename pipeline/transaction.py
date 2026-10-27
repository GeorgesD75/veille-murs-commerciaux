"""Distinguer l'achat immobilier des murs de l'achat d'une activité ou d'un bail.

Une catégorie générique « local commercial », un prix et un bail ne prouvent
pas la vente du local. Le type libre/occupé inféré n'est jamais une preuve.
"""
from __future__ import annotations

import re
from urllib.parse import unquote, urlsplit

from pipeline.modeles import Annonce
from pipeline.texte import normaliser_texte

_FONDS = r"(?:fonds?\s+(?:de\s+commerces?|commercial|artisanal|(?:de\s+)?(?:restaurant|bar|cafe|boulangerie|coiffure|pizzeria|optique|boucherie))|f[. ]?d[. ]?c\.?)"
_BAIL = r"(?:droit\s+(?:au|de)\s+bail|(?:cession|vente)\s+(?:du\s+|de\s+)?(?:contrat\s+de\s+)?bail|d[. ]?a[. ]?b\.?)"
_MURS = re.compile(
    r"\bmurs\s+(?:commercia(?:ux|l)|occupes|libres|loues|seuls|a vendre|qui sont a vendre)"
    r"|\bmurs\s+(?:de\s+(?:(?:la|le|ce|cette)\s+)?|d[' ](?:un |une |l')?)(?:boutiques?|locaux|local|commerces?|bureaux?|magasins?|restaurants?)\b"
    r"|\b(?:vente|vendre|achat|acheter|acquisition|cession)\s+(?:(?:de|des|les|du)\s+){0,2}murs\b"
    r"|\b(?:pleine propriete|propriete des locaux|vente immobiliere)\b")
_MIXTE = re.compile(r"\bmurs(?:\s+(?:commerciaux|occupes|libres|loues))?\s*(?:et|&|\+|avec|/|[-—])\s*(?:(?:le|du|des|un)\s+)?fonds?\b|\bfonds?(?: de commerce)?\s*(?:et|&|\+|avec|/|[-—])\s*(?:les\s+)?murs\b")
_HORS_MURS = re.compile(
    r"\b(?:hors|sans)\s+(?:les\s+|achat (?:des|de)\s+)?murs\b"
    r"|\bmurs\s+(?:commerciaux\s+)?(?:non (?:compris|inclus|vendus)|exclus)\b"
    r"|\bmurs\s+(?:ne sont|ne seront|ne seraient)\s+pas\s+(?:compris|inclus|vendus|a vendre)\b"
    r"|\b(?:ne vend(?:ons)? pas|ne cede pas)\s+(?:les |ses )?murs\b"
    r"|\b(?:pas|aucune)\s+(?:une |de )?(?:vente|acquisition|achat)\s+(?:des |de |de ces )murs\b")
_OPTION_MURS = re.compile(
    r"\bmurs\s+(?:commerciaux\s+)?(?:en option|en supplement|en sus)\b"
    r"|\b(?:possibilite|possibilites|option)\s+(?:d[' ](?:achat|acquisition)|d[' ]acheter|acheter)\s+(?:des |les )?murs\b")


def _nettoyer(texte: str, alerte: bool = False) -> str:
    t = normaliser_texte(texte).replace("’", "'").replace("–", "-")
    # Ce préfixe est ajouté par le parseur : il ne prouve pas l'objet vendu.
    t = re.sub(r"information contradictoire entre le titre/la case structuree.*?avant toute offre\.\s*", "", t)
    if alerte:
        if "votre recherche" in t:
            fin = re.search(r"votre recherche.*?maximum\s+[\d\s.,]+\s*(?:€|euros?)", t)
            # Sans séparation fiable, ne pas utiliser les critères de recherche
            # de l'utilisateur comme une déclaration de l'annonceur.
            t = t[fin.end():] if fin else ""
        t = re.split(r"se desinscrire|cet e-mail|cet email|nous contacter", t, maxsplit=1)[0]
    # Une vente de murs « hors fonds » ne doit pas être éliminée sur ce mot.
    t = re.sub(r"\b(?:hors|sans|excluant|aucun|ni)\s+(?:(?:le|du|de|la|un|une)\s+){0,2}(?:" + _FONDS + "|" + _BAIL + r")\b", "", t)
    t = re.sub(r"\b(?:ne comprend pas|ne concerne pas|n'est pas)\s+(?:la vente d[' ]un |une vente de |un |le |de )?(?:" + _FONDS + "|" + _BAIL + r")\b", "", t)
    return t


def qualifier_transaction(a: Annonce) -> dict:
    """Nature annoncée et motif vérifiable ; « murs » ne certifie aucun acte."""
    alerte = a.source.startswith("alerte_")
    titre = _nettoyer(a.titre)
    if a.source in {"iburoshop", "flagship"}:
        # Ancienne présentation du parseur : le type libre/occupé était
        # injecté dans le titre et ne prouve pas ce que l'annonceur vend.
        titre = re.sub(r"^murs (?:occupes|libres)\s*[-—]\s*", "", titre)
    if alerte and re.search(r"nouvelle[s]? annonce|votre recherche|votre alerte|photo annonce", titre):
        titre = ""
    description = _nettoyer(a.description, alerte)
    detail = _nettoyer(a.texte_detail)
    champs = [("titre", titre), ("description", description), ("fiche", detail)]
    texte = " ".join(t for _, t in champs)
    murs = next(((origine, m.group(0)) for origine, t in champs if (m := _MURS.search(t))), None)

    def verdict(nature, motif, origine="texte", extrait=""):
        return {"nature": nature, "motif": motif, "origine": origine, "extrait": extrait[:180]}

    if m := _HORS_MURS.search(texte):
        return verdict("fonds", "Les murs sont explicitement exclus de la vente.", extrait=m.group(0))
    if m := _MIXTE.search(texte):
        return verdict("mixte", "Vente groupée de murs et fonds : le prix des murs seuls n’est pas établi.", extrait=m.group(0))
    if m := _OPTION_MURS.search(texte):
        return verdict("mixte", "L’achat des murs est une option distincte : le prix affiché ne prouve pas leur vente seule.", extrait=m.group(0))
    if re.search(r"\ba louer\b|\blocation\b", titre) and not re.search(r"\bvente|vendre|achat|acheter\b", titre):
        return verdict("location", "L’intitulé propre à l’annonce propose une location, sans achat des murs.", "titre", titre)
    if re.search(r"\b(?:location[- ]gerance|location pure)\b|^\s*(?:a louer|location\b)", titre + " " + description):
        return verdict("location", "Offre de location ou de location-gérance, sans acquisition des murs.")

    declaree = a.nature_transaction_source
    preuves = a.preuves.get("nature_transaction", [])
    valeurs = {e.get("valeur") for e in preuves} | ({declaree} if declaree else set())
    if "murs" in valeurs and valeurs.intersection({"fonds", "bail", "mixte", "location"}):
        return verdict("a_confirmer", "Les sources se contredisent sur la nature de la transaction.", "sources")
    if declaree in {"fonds", "bail", "mixte", "location"}:
        return verdict(declaree, "La catégorie propre à cette annonce ne correspond pas à la vente des murs seuls.", "champ source", declaree)

    chemin = normaliser_texte(unquote(urlsplit(a.url).path)).replace("-", " ").replace("_", " ")
    lien_non_immo = re.search(r"\b(?:fonds de commerce|cession fonds|droit au bail|cession bail|location gerance)\b", chemin)
    fonds_titre = re.search(r"\b(?:" + _FONDS + r")\b", titre)
    bail_titre = re.search(r"\b(?:" + _BAIL + r"|pas[- ]de[- ]porte)\b", titre)
    # Une mention de fonds exploité par le locataire ne signifie pas qu'il
    # est vendu ; une action explicite de cession, elle, concerne l'acquéreur.
    cession_fonds = re.search(
        r"\b(?:vente|vendre|cede|ceder|cession|reprise)\s+(?:(?:de|du|des|le|les|un|une|plusieurs|d[' ])\s*){0,3}(?:" + _FONDS + r"|fonds?\b)"
        r"|\b(?:" + _FONDS + r")\s+(?:a vendre|a ceder|a reprendre)\b", texte)
    cession_bail = re.search(r"\b(?:" + _BAIL + r")\b", texte)
    fonds_texte = re.search(r"\b(?:" + _FONDS + r")\b", texte)
    murs_titre = _MURS.search(titre)
    if fonds_titre and murs_titre and murs_titre.start() < fonds_titre.start() and not cession_fonds and re.search(
        r"\b(?:d[' ](?:un|une)?|du|des|de)\s*$",titre[murs_titre.end():fonds_titre.start()]):
        # « Vente des murs d'un fonds de commerce » vend l'immobilier,
        # contrairement à « Vente du fonds avec possibilité d'achat des murs ».
        fonds_titre = None
    if fonds_titre or bail_titre or cession_fonds or lien_non_immo or cession_bail:
        nature = "bail" if bail_titre or cession_bail else "fonds"
        if murs:
            return verdict("mixte", "Cession de fonds de commerce ou de droit au bail mentionnée : le prix des murs seuls n’est pas isolé.")
        return verdict(nature, "Cession de fonds de commerce ou de droit au bail ; achat du local non établi.",
                       "URL" if lien_non_immo else "texte", (fonds_titre or bail_titre or cession_fonds or lien_non_immo or cession_bail).group(0))
    if fonds_texte and not murs:
        return verdict("fonds", "L’annonce décrit un fonds de commerce, sans vente explicite des murs.", extrait=fonds_texte.group(0))
    if murs:
        return verdict("murs", "Vente immobilière des murs annoncée ; à confirmer auprès du vendeur.", *murs)
    if re.search(r"\b(?:prix de cession|cession d[' ]activite)\b", texte):
        return verdict("a_confirmer", "Un prix de cession est annoncé sans confirmation du prix immobilier des murs seuls.")
    preuve_propre = any(e.get("valeur") == "murs" and e.get("url") == a.url for e in preuves)
    if declaree == "murs" or preuve_propre:
        return verdict("murs", "Vente des murs indiquée par un champ propre à l’annonce.", "champ source", declaree or "murs")
    if re.search(r"\b(?:prix de cession|cession d[' ]activite|vente de commerce|chiffre d[' ]affaires|clientele|ebe\b|licence iv)\b", texte):
        return verdict("a_confirmer", "L’annonce décrit une activité ou une cession, sans établir que le prix achète le local.")
    return verdict("a_confirmer", "Vente des murs non établie : un intitulé « local commercial », un prix ou un bail ne suffisent pas.")
