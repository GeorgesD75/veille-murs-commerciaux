"""immobilier.notaires.fr — annonces des études notariales, API JSON publique.

Validation robots.txt (relevé du 2026-07-10) : permissif hors chemins
techniques Drupal ; le Crawl-delay de 10 s est respecté en réglant le délai
du client AU-DESSUS de cette consigne (10-12 s), et le volume est minuscule
(1 à 3 requêtes par tournée). L'API « pub-services » est celle qu'appelle le
propre frontend AngularJS du site (préfixe « pub » = public, aucune clé) :
JSON propre découvert en sondant le bundle de l'appli, paramètres validés en
direct contre l'API (le paramètre serveur de département s'est montré non
fiable lors du sondage — le filtrage Île-de-France se fait donc côté client).

Pourquoi cette source malgré un volume national faible (~250 annonces COM
toutes transactions, 2-3 ventes IdF un jour donné) :
- les études notariales publient RAREMENT sur les portails classiques — une
  annonce notariale est souvent introuvable ailleurs (quasi off-market) ;
- la donnée est de confiance par construction (prix réel du mandat, commune
  INSEE, drapeaux bienVendu/bienRetire assumés par l'étude) — exactement le
  niveau de fiabilité que vise l'outil.
"""
from __future__ import annotations

import json
import re

from pipeline.geo import ILE_DE_FRANCE
from pipeline.modeles import AnnonceBrute
from sources.base import Source
from sources.extraction import (
    deviner_type_murs,
    extraire_surface,
    loyer_mensuel_depuis_texte,
)
from sources.http import ClientPoli

# Transactions retenues : ventes classiques et ventes négociées immobilières
# (VNI, dites « immo interactif »). Les LOCATION sont hors sujet ; les VAE
# (enchères notariales) relèveraient de la section enchères, pas du pipeline.
_TRANSACTIONS_VENTE = {"VENTE", "VNI"}
_PAR_PAGE = 100


class SourceNotaires(Source):
    nom = "notaires"
    BASE = "https://www.immobilier.notaires.fr"
    API = "/pub-services/inotr-www-annonces/v1/annonces"

    def __init__(self, client: ClientPoli | None = None, max_pages: int = 5) -> None:
        super().__init__()
        # Crawl-delay 10 s au robots.txt : le délai du client est réglé au-dessus.
        self.client = client or ClientPoli(delai_min_s=10.0, delai_max_s=12.0)
        self.max_pages = max_pages

    def collecter(self) -> list[AnnonceBrute]:
        annonces: dict[str, AnnonceBrute] = {}
        page = 1
        nb_pages = 1
        while page <= min(self.max_pages, nb_pages):
            brut = self.client.obtenir(
                f"{self.BASE}{self.API}?typeBiens=COM&page={page}&parPage={_PAR_PAGE}"
            )
            donnees = json.loads(brut)
            nb_pages = donnees.get("nbPages") or 1
            for item in donnees.get("annonceResumeDto") or []:
                annonce = self._depuis_item(item)
                if annonce is not None:
                    annonces.setdefault(annonce.id_source, annonce)
            page += 1
        return list(annonces.values())

    def _depuis_item(self, item: dict) -> AnnonceBrute | None:
        if item.get("typeTransaction") not in _TRANSACTIONS_VENTE:
            return None
        if item.get("inseeDepartement") not in ILE_DE_FRANCE:
            return None
        # Drapeaux assumés par l'étude notariale : un bien vendu ou retiré ne
        # doit même pas entrer dans le pipeline.
        if item.get("bienVendu") == "OUI" or item.get("bienRetire") == "OUI":
            return None
        identifiant = item.get("annonceId") or item.get("id")
        url = item.get("urlDetailAnnonceFr")
        prix = item.get("prixTotal") or item.get("prixAffiche")
        if not identifiant or not url or not prix or prix <= 0:
            return None

        description = re.sub(r"\s+", " ", item.get("descriptionFr") or "").strip()
        ville = (item.get("communeNom") or "").strip()
        titre = f"Local commercial (notaire) – {ville}" if ville else "Local commercial (notaire)"

        return AnnonceBrute(
            id_source=str(identifiant),
            source=self.nom,
            url=str(url),
            titre=titre[:160],
            ville=ville,
            code_postal=str(item.get("codePostal") or ""),
            type_murs=deviner_type_murs(description),
            prix=float(prix),
            surface_m2=extraire_surface(description),
            loyer_mensuel=loyer_mensuel_depuis_texte(description, float(prix)),
            description=description[:600],
        )
