"""Niveau 2 — lecture des alertes email des grands portails via IMAP.

LeBonCoin, SeLoger Bureaux & Commerces, Geolocaux, BureauxLocaux bloquent le
scraping (DataDome…) MAIS envoient des alertes email gratuites : on lit ces
alertes dans une boîte Gmail dédiée. Identifiants attendus en variables
d'environnement (secrets GitHub Actions) :

    IMAP_USER      adresse de la boîte dédiée (ex. veille.murs.georges@gmail.com)
    IMAP_PASSWORD  « mot de passe d'application » Gmail (PAS le mot de passe
                   du compte : compte Google > Sécurité > Validation en 2 étapes
                   > Mots de passe des applications)

Sans ces variables, la source s'ignore proprement (avertissement en santé).
Seuls les messages NON LUS sont traités ; la lecture IMAP les marque lus,
ils ne seront donc pas retraités au run suivant.

Les extracteurs par portail sont volontairement génériques (lien d'annonce
reconnu par motif + lecture du bloc alentour : prix, surface, ville) : les
gabarits d'emails changent souvent et seront affinés sur les premiers vrais
messages reçus. Une annonce mal lue est ignorée, jamais bloquante.
"""
from __future__ import annotations

import email
import email.policy
import imaplib
import os
import re
from dataclasses import dataclass
from urllib.parse import unquote

from bs4 import BeautifulSoup
from bs4.element import Tag

from pipeline.modeles import AnnonceBrute
from sources.base import Source
from sources.extraction import (
    deviner_type_murs,
    extraire_nombre,
    extraire_surface,
    loyer_mensuel_depuis_texte,
)

_VILLE_CP = re.compile(r"([A-ZÀ-Ý][\wà-ÿ'’ -]{2,40}?)\s*\(?\b(\d{5})\)?")
_PRIX_EURO = re.compile(r"(\d[\d\s  .,]{2,})\s*€")


@dataclass(frozen=True)
class Portail:
    nom: str
    domaines: tuple[str, ...]           # reconnus dans l'expéditeur ou les liens
    motif_lien: re.Pattern              # groupe 1 = identifiant de l'annonce


PORTAILS: list[Portail] = [
    Portail(
        "leboncoin", ("leboncoin.fr",),
        re.compile(r"https?://(?:www\.)?leboncoin\.fr/[a-z_/]*?(\d{6,})"),
    ),
    Portail(
        "seloger_bureaux", ("seloger", "bureauxlocaux.com"),
        re.compile(r"https?://(?:www\.)?(?:seloger[a-z-]*\.com|bureauxlocaux\.com)/[^\s\"'<>]*?(\d{5,})"),
    ),
    Portail(
        "geolocaux", ("geolocaux.com",),
        re.compile(r"https?://(?:www\.)?geolocaux\.com/[^\s\"'<>]*?(\d{4,})"),
    ),
]


def identifier_portail(expediteur: str, html: str) -> Portail | None:
    texte = f"{expediteur} {html[:4000]}".lower()
    for portail in PORTAILS:
        if any(domaine in texte for domaine in portail.domaines):
            return portail
    return None


def _bloc_annonce(lien: Tag) -> Tag:
    """Remonte vers l'ancêtre qui contient le prix (max 5 niveaux)."""
    bloc: Tag = lien
    for _ in range(5):
        if bloc.parent is None or not isinstance(bloc.parent, Tag):
            break
        bloc = bloc.parent
        if "€" in bloc.get_text():
            return bloc
    return bloc


def extraire_annonces_html(html: str, portail: Portail) -> list[AnnonceBrute]:
    """Annonces contenues dans le HTML d'un email d'alerte."""
    soup = BeautifulSoup(html, "html.parser")
    annonces: dict[str, AnnonceBrute] = {}
    for lien in soup.find_all("a", href=True):
        # Les alertes passent par des liens de tracking : on cherche le motif
        # dans l'URL décodée (l'URL réelle y est souvent encapsulée).
        href = unquote(str(lien["href"]))
        trouve = portail.motif_lien.search(href)
        if not trouve:
            continue
        id_source = trouve.group(1)
        if id_source in annonces:
            continue

        bloc = _bloc_annonce(lien)
        texte = bloc.get_text(" ", strip=True)

        prix_candidats = [extraire_nombre(m.group(1)) for m in _PRIX_EURO.finditer(texte)]
        prix_candidats = [p for p in prix_candidats if p and p >= 10_000]
        prix = max(prix_candidats) if prix_candidats else None

        ville, code_postal = "", ""
        localisation = _VILLE_CP.search(texte)
        if localisation:
            ville, code_postal = localisation.group(1).strip(), localisation.group(2)

        image = bloc.find("img", src=True)
        titre = lien.get_text(" ", strip=True)
        if not titre and image is not None:
            titre = str(image.get("alt", "")).strip()
        if not titre:
            titre = f"Annonce {portail.nom}" + (f" – {ville}" if ville else "")

        annonces[id_source] = AnnonceBrute(
            id_source=id_source,
            source=f"alerte_{portail.nom}",
            url=trouve.group(0),
            titre=titre[:160],
            ville=ville,
            code_postal=code_postal,
            type_murs=deviner_type_murs(texte),
            prix=prix,
            surface_m2=extraire_surface(texte),
            loyer_mensuel=loyer_mensuel_depuis_texte(texte, prix),
            image_url=str(image["src"]) if image is not None else None,
            description=texte[:400],
        )
    return list(annonces.values())


class SourceImap(Source):
    nom = "imap"

    def __init__(self, hote: str = "imap.gmail.com", dossier: str = "INBOX") -> None:
        super().__init__()
        self.hote = hote
        self.dossier = dossier

    def extraire_message(self, message: email.message.EmailMessage) -> list[AnnonceBrute]:
        partie = message.get_body(preferencelist=("html", "plain"))
        if partie is None:
            return []
        html = partie.get_content()
        portail = identifier_portail(str(message.get("From", "")), html)
        if portail is None:
            return []
        return extraire_annonces_html(html, portail)

    def collecter(self) -> list[AnnonceBrute]:
        utilisateur = os.environ.get("IMAP_USER")
        mot_de_passe = os.environ.get("IMAP_PASSWORD")
        if not utilisateur or not mot_de_passe:
            self.avertissements.append(
                "IMAP_USER / IMAP_PASSWORD absents : alertes email ignorées "
                "(configuration au README, Phase 5)"
            )
            return []

        annonces: dict[str, AnnonceBrute] = {}
        with imaplib.IMAP4_SSL(self.hote) as boite:
            boite.login(utilisateur, mot_de_passe)
            boite.select(self.dossier)
            _, resultats = boite.search(None, "UNSEEN")
            numeros = resultats[0].split() if resultats and resultats[0] else []
            for numero in numeros:
                # fetch RFC822 pose le drapeau \\Seen : le message ne sera pas retraité
                _, contenu = boite.fetch(numero, "(RFC822)")
                if not contenu or contenu[0] is None:
                    continue
                message = email.message_from_bytes(
                    contenu[0][1], policy=email.policy.default
                )
                try:
                    for annonce in self.extraire_message(message):
                        annonces.setdefault(f"{annonce.source}:{annonce.id_source}", annonce)
                except Exception as exc:  # noqa: BLE001 — un email illisible n'arrête rien
                    self.avertissements.append(f"email illisible ({message.get('Subject')}) : {exc}")
        return list(annonces.values())
