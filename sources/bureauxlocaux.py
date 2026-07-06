"""bureauxlocaux.com — vente de locaux commerciaux, Île-de-France.

Validation robots.txt (relevé du 2026-07-07) : permissif — le sous-arbre
/immobilier-d-entreprise/annonces/ n'apparaît dans aucun Disallow, et aucun
Crawl-delay n'est fixé (le délai poli habituel du client s'applique). Une
page par département IdF (URLs dédiées, ex. « seine-saint-denis-93 »,
vérifiées une à une), paginée par /page/N ; une page au-delà du nombre réel
de pages renvoie proprement un 404 (pas de contenu dupliqué à filtrer).

Structure NETTEMENT plus riche qu'un scraping HTML classique : chaque page
de listing embarque, dans <script type="text/json" id="react-context">, un
JSON directement exploitable (pas d'échappement à défaire) sous
global.results.items. Plusieurs champs structurés évitent de deviner :
- is_occupied -> type de murs, sans heuristique de mots-clés ;
- is_sale_of_business_assets -> fonds de commerce déguisé, signalé de façon
  FIABLE par l'annonceur (relayé dans la description pour que le filtre
  anti-piège existant, textuel, l'attrape comme les autres sources) ;
- has_extraction / is_on_street_angle -> traduits en phrase française pour
  que caracteristiques_depuis_texte() (pipeline/enrichissement.py) les
  détecte comme n'importe quelle autre source, sans code dédié.
"""
from __future__ import annotations

import json
import re
from urllib.parse import urljoin

from pipeline.modeles import AnnonceBrute, TypeMurs
from sources.base import SourceHtml
from sources.extraction import deviner_type_murs, loyer_mensuel_depuis_texte
from sources.http import SourceBloqueeErreur

_SLUGS = {
    "75": "paris-75", "92": "hauts-de-seine-92", "93": "seine-saint-denis-93",
    "94": "val-de-marne-94", "95": "val-d-oise-95", "78": "yvelines-78",
    "91": "essonne-91", "77": "seine-et-marne-77",
}
_CONTEXTE = re.compile(
    r'<script type="text/json" id="react-context">(.*?)</script>', re.DOTALL
)
_BALISE = re.compile(r"<[^>]+>")


def _texte_propre(html: str | None) -> str:
    return re.sub(r"\s+", " ", _BALISE.sub(" ", html or "")).strip()


class SourceBureauxLocaux(SourceHtml):
    nom = "bureauxlocaux"
    BASE = "https://www.bureauxlocaux.com"
    CATEGORIE = "/immobilier-d-entreprise/annonces/{slug}/vente-commerces"

    def __init__(
        self, client=None, departements: list[str] | None = None, max_pages: int = 5
    ) -> None:
        super().__init__(client)
        self.departements = departements or list(_SLUGS)
        self.max_pages = max_pages

    def collecter(self) -> list[AnnonceBrute]:
        annonces: dict[str, AnnonceBrute] = {}
        erreurs: list[Exception] = []
        for departement in self.departements:
            slug = _SLUGS.get(departement)
            if slug is None:
                continue
            base = self.CATEGORIE.format(slug=slug)
            total_pages = 1
            page = 1
            while page <= min(self.max_pages, total_pages):
                chemin = base if page == 1 else f"{base}/page/{page}"
                try:
                    html = self.client.obtenir(self.BASE + chemin)
                except SourceBloqueeErreur as exc:
                    erreurs.append(exc)
                    self.avertissements.append(f"{chemin} : {exc}")
                    return list(annonces.values()) if annonces else self._echec(erreurs)
                except Exception as exc:  # noqa: BLE001 — une page en échec n'arrête pas la source
                    erreurs.append(exc)
                    self.avertissements.append(f"{chemin} : {exc}")
                    break
                lot, total_pages_vues = self._extraire_page(html, departement)
                if page == 1:
                    total_pages = total_pages_vues or 1
                for annonce in lot:
                    annonces.setdefault(annonce.id_source, annonce)
                page += 1
        if not annonces and erreurs:
            raise erreurs[0]
        return list(annonces.values())

    def _echec(self, erreurs: list[Exception]):
        raise erreurs[0]

    def _extraire_page(self, html: str, departement: str) -> tuple[list[AnnonceBrute], int]:
        m = _CONTEXTE.search(html)
        if not m:
            raise ValueError("react-context introuvable : structure du site changée ?")
        data = json.loads(m.group(1))
        resultats = (data.get("global") or {}).get("results") or {}
        items = resultats.get("items") or []
        total_pages = ((resultats.get("pagination") or {}).get("total_pages")) or 1
        annonces = []
        for item in items:
            annonce = self._depuis_item(item, departement)
            if annonce is not None:
                annonces.append(annonce)
        return annonces, total_pages

    def _depuis_item(self, item: dict, departement: str) -> AnnonceBrute | None:
        id_source = item.get("id")
        url = item.get("url")
        if not id_source or not url:
            return None
        caract = item.get("characteristics_json") or {}
        description = _texte_propre(item.get("description"))

        # Traduit les booléens structurés en phrases françaises, pour que les
        # détecteurs textuels EXISTANTS (caractéristiques, filtre anti-piège)
        # les reconnaissent sans code dédié — une seule vérité, textuelle.
        ajouts = []
        if caract.get("is_sale_of_business_assets"):
            ajouts.append("Cession de fonds de commerce.")
        if caract.get("has_extraction"):
            ajouts.append("Extraction possible.")
        if caract.get("is_on_street_angle"):
            ajouts.append("Emplacement en angle de rue.")
        if ajouts:
            description = f"{description} {' '.join(ajouts)}".strip()

        titre = _texte_propre(item.get("label")) or f"Local commercial {item.get('city', '')}".strip()
        prix = _nombre(item.get("sale_price"))
        surface = _nombre(item.get("total_surface"))

        is_occupied = caract.get("is_occupied")
        if is_occupied is True:
            type_murs = TypeMurs.MURS_OCCUPES
        elif is_occupied is False:
            type_murs = TypeMurs.MURS_LIBRES
        else:  # champ absent : on retombe sur l'heuristique textuelle habituelle
            type_murs = deviner_type_murs(f"{titre} {description}")

        images_dict = item.get("images") or {}
        images = [u for u in (images_dict.get("normal") or []) if u]

        return AnnonceBrute(
            id_source=str(id_source),
            source=self.nom,
            url=urljoin(self.BASE, str(url)),
            titre=titre[:160],
            ville=_texte_propre(item.get("city")),
            code_postal=_texte_propre(item.get("zip_code")),
            type_murs=type_murs,
            prix=prix,
            surface_m2=surface,
            loyer_mensuel=loyer_mensuel_depuis_texte(description, prix),
            image_url=images[0] if images else None,
            images=images,
            description=description[:600],
        )


def _nombre(valeur) -> float | None:
    """« 350720.00 » (chaîne ou nombre JSON) -> 350720.0 ; 0 comptant pour absent."""
    try:
        f = float(valeur)
    except (TypeError, ValueError):
        return None
    return f if f > 0 else None
