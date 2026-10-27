"""Données JSON-LD de la fiche courante, jamais celles d'une liste de recommandations.

Contrat floorSize/QuantitativeValue : https://schema.org/floorSize
Seuls les mètres carrés explicites et les prix en euros sont retenus.
"""
from __future__ import annotations

import json
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from pipeline.fiabilite import nombre_positif, noter_preuve
from pipeline.modeles import Annonce


def _cle_url(url: str) -> tuple:
    u = urlsplit(url)
    return u.netloc.lower().removeprefix("www."), u.path.rstrip("/")


def extraire_structure(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    objets = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            donnees = json.loads(script.string or script.get_text())
        except (ValueError, TypeError):
            continue
        for item in donnees if isinstance(donnees, list) else [donnees]:
            if isinstance(item, dict):
                graph = item.get("@graph", [item])
                if isinstance(graph, list):
                    objets.extend(graph)
    objets = [o for o in objets if isinstance(o, dict)]
    index = {o["@id"]: o for o in objets if isinstance(o.get("@id"), str)}

    def resoudre(o):
        return index.get(o.get("@id"), o) if isinstance(o, dict) else {}

    candidats = []
    for objet in objets:
        if objet.get("@type") in ["ItemList", "BreadcrumbList", "Organization", "WebSite"]:
            continue
        principal = resoudre(objet.get("mainEntity", {}))
        objet = principal if principal else objet
        bien = resoudre(objet.get("itemOffered", objet))
        if bien.get("floorSize") or objet.get("offers"):
            candidats.append((objet, bien))
    exacts = [(o, b) for o, b in candidats if any(
        isinstance(lien, str) and _cle_url(urljoin(url, lien)) == _cle_url(url)
        for lien in [o.get("url"), b.get("url"), o.get("@id"), b.get("@id")])]
    sans_url = [(o, b) for o, b in candidats if not any(
        isinstance(lien, str) and lien for lien in [o.get("url"), b.get("url"), o.get("@id"), b.get("@id")])]
    uniques = list({json.dumps(c, sort_keys=True): c for c in (exacts or sans_url)}.values())
    if len(uniques) != 1:
        return {}
    objet, bien = uniques[0]
    resultat = {}
    surface = bien.get("floorSize")
    if isinstance(surface, dict):
        unite = str(surface.get("unitCode") or surface.get("unitText", "")).lower()
        if unite in {"mtk", "m2", "m²", "square meter", "square meters"}:
            resultat["surface_m2"] = nombre_positif(surface.get("value"))
    offres = objet.get("offers", bien.get("offers", {}))
    if isinstance(offres, list):
        offres = offres[0] if len(offres) == 1 else {}
    if isinstance(offres, dict):
        if str(offres.get("availability", "")).rsplit("/", 1)[-1] in {"SoldOut", "Discontinued", "OutOfStock"}:
            resultat["retiree"] = True
        fonction = str(offres.get("businessFunction", "")).lower()
        specification = offres.get("priceSpecification") or {}
        specification = specification if isinstance(specification, dict) else {}
        if not any(mot in fonction for mot in ["lease", "rent"]) and not any(
            cle in specification for cle in ["unitCode", "billingDuration", "billingIncrement", "referenceQuantity"]):
            if offres.get("priceCurrency", specification.get("priceCurrency")) == "EUR":
                resultat["prix"] = nombre_positif(offres.get("price", specification.get("price")))
    adresse = bien.get("address", {})
    if isinstance(adresse, dict):
        cp = str(adresse.get("postalCode", ""))
        if len(cp) == 5 and cp.isdigit():
            resultat["code_postal"] = cp
    description = bien.get("description") or objet.get("description")
    if isinstance(description, str):
        resultat["description"] = BeautifulSoup(description, "html.parser").get_text(" ", strip=True)[:12000]
    images = bien.get("image") or objet.get("image") or []
    images = images if isinstance(images, list) else [images]
    liens = [i.get("url") if isinstance(i, dict) else i for i in images]
    resultat["images"] = [urljoin(url, i) for i in liens if isinstance(i, str) and i][:12]
    return {k: v for k, v in resultat.items() if v is not None and v != ""}


def appliquer_structure(a: Annonce, donnees: dict, quand: str) -> list[str]:
    appris = []
    for champ in ["prix", "surface_m2", "code_postal"]:
        valeur = donnees.get(champ)
        if valeur is None:
            continue
        noter_preuve(a, champ, valeur, "fiche:jsonld", quand)
        courant = getattr(a, champ)
        tolerance = .01 if champ == "prix" else .05
        contradictoire = (str(valeur) != str(courant)) if champ == "code_postal" else (
            courant is not None and abs(float(valeur) - float(courant)) > tolerance * max(float(valeur), float(courant)))
        if courant and contradictoire:
            if champ not in a.conflits_donnees:
                a.conflits_donnees.append(champ)
        else:
            a.conflits_donnees = [c for c in a.conflits_donnees if c != champ]
            if not courant:
                setattr(a, champ, valeur)
                if champ == "code_postal":
                    a.departement = valeur[:2]
                appris.append(champ)
    for image in donnees.get("images", []):
        if image.startswith("https://") and image not in a.images:
            a.images.append(image)
    a.images = a.images[:16]
    if not a.image_url and a.images:
        a.image_url = a.images[0]
    return appris
