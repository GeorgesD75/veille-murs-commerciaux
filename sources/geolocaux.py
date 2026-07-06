"""geolocaux.com — vente de locaux commerciaux, Île-de-France.

Validation robots.txt (relevé du 2026-07-04) : permissif sur les listings —
seuls /api/, /ax/, le cache de recherche et quelques pages outillées sont
interdits.

Rendu serveur à GÉOMÉTRIE VARIABLE (constat du 2026-07-06) : seules les pages
de niveau ville/commune (/vente/local-commercial/issy-les-moulineaux-92130/,
paris-75…) contiennent les cartes div.annonce ; les pages département et
région sont hydratées côté client (la liste passe par /api/, interdit).

La collecte se fait donc en deux temps :
1. la page département livre, dans son payload Nuxt (__NUXT_DATA__, format
   « devalue » : tableau plat référencé par index), les communes ayant des
   annonces — avec le VRAI code postal dans l'URL, plus fiable que le titre ;
2. chaque page communale est collectée comme un listing classique. Paris est
   un listing direct, paginé par /page-N/ (61 annonces = 2 pages).

Budget requêtes : 7 pages département + ~40-60 pages communales par run,
espacées de 3-5 s comme partout (garde-fou MAX_REQUETES). Le paramètre
prix_max évite les communes dont l'annonce la moins chère dépasse le budget.
"""
from __future__ import annotations

import json
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from bs4.element import Tag

from pipeline.modeles import AnnonceBrute
from sources.base import SourceHtml
from sources.extraction import (
    deviner_type_murs,
    extraire_nombre,
    extraire_surface,
    loyer_mensuel_depuis_texte,
)
from sources.http import SourceBloqueeErreur

_SLUGS = {
    "75": "paris-75", "92": "hauts-de-seine-92", "93": "seine-saint-denis-93",
    "94": "val-de-marne-94", "95": "val-d-oise-95", "78": "yvelines-78",
    "91": "essonne-91", "77": "seine-et-marne-77",
}
# les titres du site mélangent « Paris 5 », « Paris 17e », « Paris 1er »…
_PARIS_ARRONDISSEMENT = re.compile(
    r"\bparis\s*(\d{1,2})(?:\s*(?:er|[eè]me|e))?\b", re.IGNORECASE
)
_MOTS_TYPE = re.compile(
    r"^(vente|achat|location)\s+(boutique|local commercial|local|commerce|murs)\s*",
    re.IGNORECASE,
)
# listing communal : slug + code postal complet (les pages département/région
# et les grandes villes hors IdF ne passent pas ce filtre)
_URL_COMMUNE = re.compile(r"^/vente/local-commercial/[a-z0-9-]+-(\d{5})/$")
_PAYLOAD_NUXT = re.compile(
    r'<script type="application/json"[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>',
    re.DOTALL,
)
# « Vente / achat local commercial Paris (75) - 61 annonces - Geolocaux »
_TOTAL_TITRE = re.compile(r"<title>[^<]*?(\d+)\s*annonces?\b", re.IGNORECASE | re.DOTALL)
# après ces sections, les cartes sont d'AUTRES communes (« à moins de 20
# minutes ») ou des annonces EXPIRÉES (« Précédemment sur Geolocaux »)
_FIN_LISTING = re.compile(
    r"<h2[^>]*>[^<]*(?:moins de \d+ minutes|c[ée]demment sur Geolocaux)",
    re.IGNORECASE,
)


def _texte(element: Tag | None) -> str:
    return element.get_text(" ", strip=True) if element else ""


class SourceGeolocaux(SourceHtml):
    nom = "geolocaux"
    BASE = "https://www.geolocaux.com"
    MAX_REQUETES = 90        # garde-fou de politesse par run
    MAX_PAGES_LISTING = 5    # 40 annonces/page : très large pour une commune

    def __init__(
        self,
        client=None,
        departements: list[str] | None = None,
        prix_max: int | None = None,
    ) -> None:
        super().__init__(client)
        self.departements = departements or list(_SLUGS)
        self.prix_max = prix_max
        self._requetes = 0
        self._bloquee = False
        self._erreurs: list[Exception] = []

    # --- collecte en deux temps -------------------------------------------

    def collecter(self) -> list[AnnonceBrute]:
        self._requetes, self._bloquee, self._erreurs = 0, False, []
        annonces: dict[str, AnnonceBrute] = {}
        for chemin, departement, ville, code_postal, total in self._decouvrir_listings():
            self._collecter_listing(chemin, departement, ville, code_postal, total, annonces)
            if self._bloquee:
                break
        if not annonces and self._erreurs:
            raise self._erreurs[0]
        if self._requetes >= self.MAX_REQUETES:
            self.avertissements.append(
                f"garde-fou de {self.MAX_REQUETES} requêtes atteint : collecte partielle"
            )
        return list(annonces.values())

    def _obtenir(self, chemin: str) -> str | None:
        """GET tolérant aux pannes : mêmes règles que collecter_pages."""
        if self._bloquee or self._requetes >= self.MAX_REQUETES:
            return None
        self._requetes += 1
        try:
            return self.client.obtenir(self.BASE + chemin)
        except SourceBloqueeErreur as exc:
            self._bloquee = True
            self._erreurs.append(exc)
            self.avertissements.append(f"{chemin} : {exc}")
        except Exception as exc:  # noqa: BLE001 — une page en échec ne bloque pas
            self._erreurs.append(exc)
            self.avertissements.append(f"{chemin} : {exc}")
        return None

    def _decouvrir_listings(
        self,
    ) -> list[tuple[str, str, str | None, str | None, int | None]]:
        """(chemin, département, ville, code postal, nb d'annonces) à collecter."""
        listings: list[tuple[str, str, str | None, str | None, int | None]] = []
        for departement in self.departements:
            if departement not in _SLUGS:
                continue
            chemin = f"/vente/local-commercial/{_SLUGS[departement]}/"
            if departement == "75":  # la page ville de Paris est déjà un listing
                listings.append((chemin, "75", None, None, None))
                continue
            html = self._obtenir(chemin)
            if html is None:
                if self._bloquee:
                    break
                continue
            listings.extend(self._communes_du_payload(html, departement))
        return listings

    def _communes_du_payload(
        self, html: str, departement: str
    ) -> list[tuple[str, str, str | None, str | None, int | None]]:
        """Listings communaux annoncés par le payload Nuxt d'une page département."""
        m = _PAYLOAD_NUXT.search(html)
        if not m:
            self.avertissements.append(f"{departement} : payload Nuxt introuvable")
            return []
        try:
            payload = json.loads(m.group(1))
        except ValueError:
            self.avertissements.append(f"{departement} : payload Nuxt illisible")
            return []

        def val(i):  # le format devalue référence les valeurs par index
            return payload[i] if isinstance(i, int) and 0 <= i < len(payload) else None

        communes: list[tuple[str, str, str | None, str | None, int | None]] = []
        vus: set[str] = set()
        for element in payload:
            if not (isinstance(element, dict)
                    and {"place", "nb_annonce", "url"} <= element.keys()):
                continue
            url = val(element["url"])
            nb = val(element["nb_annonce"])
            place = val(element["place"])
            if not isinstance(url, str) or not isinstance(nb, (int, float)) or nb <= 0:
                continue
            cp = _URL_COMMUNE.match(url)
            if not cp or not cp.group(1).startswith(departement) or url in vus:
                continue
            prix_min = val(element["price_min"]) if "price_min" in element else None
            if (self.prix_max and isinstance(prix_min, (int, float))
                    and prix_min > self.prix_max):
                continue  # tout y est hors budget : requête épargnée
            vus.add(url)
            ville = place.strip() if isinstance(place, str) else None
            communes.append((url, departement, ville or None, cp.group(1), int(nb)))
        return communes

    def _collecter_listing(
        self,
        chemin: str,
        departement: str,
        ville: str | None,
        code_postal: str | None,
        total: int | None,
        annonces: dict[str, AnnonceBrute],
    ) -> None:
        """Un listing = ses N premières cartes, dans l'ordre du DOM.

        Au-delà de ses propres annonces, la page enchaîne des sections « à
        moins de 20 minutes » (communes voisines, voire autre département) et
        « Précédemment sur Geolocaux » (annonces expirées) : les prendre
        attribuerait la mauvaise ville — ou ressusciterait un bien vendu. On
        coupe donc le HTML au premier de ces séparateurs, et on plafonne au
        compte officiel (payload du département, sinon <title>).
        """
        pris = 0
        for page in range(1, self.MAX_PAGES_LISTING + 1):
            chemin_page = chemin if page == 1 else f"{chemin}page-{page}/"
            html = self._obtenir(chemin_page)
            if html is None:
                return
            if page == 1 and total is None:
                m = _TOTAL_TITRE.search(html)
                total = int(m.group(1)) if m else None
            fin = _FIN_LISTING.search(html)
            try:
                lot = self.extraire(
                    html[:fin.start()] if fin else html,
                    departement, ville, code_postal,
                )
            except Exception as exc:  # noqa: BLE001
                self._erreurs.append(exc)
                self.avertissements.append(f"{chemin_page} : {exc}")
                return
            for annonce in lot:
                if total is not None and pris >= total:
                    break
                pris += 1
                annonces.setdefault(annonce.id_source, annonce)
            if total is not None and pris >= total:
                return
            if f'href="{chemin}page-{page + 1}/"' not in html:
                return

    # --- extraction d'un listing ------------------------------------------

    def _localiser(
        self,
        titre: str,
        departement: str,
        ville: str | None = None,
        code_postal: str | None = None,
    ) -> tuple[str, str]:
        """(ville, code postal) — l'URL communale fait foi hors Paris ;
        à Paris, l'arrondissement du titre ; sinon approximation."""
        arrondissement = _PARIS_ARRONDISSEMENT.search(titre)
        if arrondissement and departement == "75":
            n = int(arrondissement.group(1))
            if 1 <= n <= 20:
                return f"Paris {n}{'er' if n == 1 else 'e'}", f"750{n:02d}"
        if ville and code_postal:
            return ville[:40], code_postal
        reste = _MOTS_TYPE.sub("", titre)
        commune = reste.split(" - ")[0].split(",")[0].strip()
        return commune[:40], departement.ljust(5, "0")

    def extraire(
        self,
        html: str,
        departement: str,
        ville: str | None = None,
        code_postal: str | None = None,
    ) -> list[AnnonceBrute]:
        soup = BeautifulSoup(html, "html.parser")
        annonces: dict[str, AnnonceBrute] = {}
        for carte in soup.select("div.annonce"):
            annonce = self._extraire_carte(carte, departement, ville, code_postal)
            if annonce is not None:
                annonces.setdefault(annonce.id_source, annonce)
        return list(annonces.values())

    def _extraire_carte(
        self,
        carte: Tag,
        departement: str,
        ville: str | None,
        code_postal: str | None,
    ) -> AnnonceBrute | None:
        lien = carte.select_one("h3.title a")
        if lien is None:
            return None
        href = str(lien.get("href", ""))
        ref = re.search(r"-(\d+)\.html$", href)
        if not ref:
            return None
        titre = _texte(lien)
        description = _texte(carte.select_one(".accroche")).replace("Voir l'annonce", "").strip()
        prix = extraire_nombre(_texte(carte.select_one(".price .price_wrapper")))
        surface = extraire_surface(_texte(carte.select_one(".surface .surf")))

        images: list[str] = []
        for img in carte.select("img[src]"):
            src = str(img["src"]).replace("&amp;", "&")
            if "/photos/" in src and "default" not in src:
                absolue = urljoin(self.BASE, src)
                if absolue not in images:
                    images.append(absolue)

        commune, cp = self._localiser(titre, departement, ville, code_postal)
        return AnnonceBrute(
            id_source=ref.group(1),
            source=self.nom,
            url=urljoin(self.BASE, href),
            titre=titre,
            ville=commune,
            code_postal=cp,
            type_murs=deviner_type_murs(f"{titre} {description}"),
            prix=prix,
            surface_m2=surface,
            loyer_mensuel=loyer_mensuel_depuis_texte(description, prix),
            image_url=images[0] if images else None,
            images=images,
            description=description[:600],
        )
