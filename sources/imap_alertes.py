"""Niveau 2 — lecture des alertes email des grands portails via IMAP.

LeBonCoin, SeLoger Bureaux & Commerces, Geolocaux, BureauxLocaux bloquent le
scraping (DataDome…) MAIS envoient des alertes email gratuites : on lit ces
alertes dans la boîte Gmail de l'utilisateur. Identifiants attendus en
variables d'environnement (secrets GitHub Actions) :

    IMAP_USER      l'adresse Gmail qui reçoit les alertes
    IMAP_PASSWORD  « mot de passe d'application » Gmail (PAS le mot de passe
                   du compte : compte Google > Sécurité > Validation en 2 étapes
                   > Mots de passe des applications)

Boîte PERSONNELLE compatible : la recherche IMAP est restreinte aux expéditeurs
des portails connus — aucun autre email n'est lu ni marqué lu. Seules les
alertes NON LUES sont traitées ; leur lecture les marque lues, elles ne seront
donc pas retraitées au run suivant.

Sans ces variables, la source s'ignore proprement (avertissement en santé).

Les extracteurs par portail sont volontairement génériques (lien d'annonce
reconnu par motif + lecture du bloc alentour : prix, surface, ville) : les
gabarits d'emails changent souvent et seront affinés sur les premiers vrais
messages reçus. Une annonce mal lue est ignorée, jamais bloquante.
"""
from __future__ import annotations

import base64
import email
import email.policy
import imaplib
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable
from urllib.parse import unquote

import requests
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
    # True si les liens de CE portail passent par un redirecteur opaque
    # (Selligent/Adobe Campaign...) où seul un vrai aller-retour HTTP révèle
    # la destination — confirmé le 2026-08-29 par curl -I sur logic_immo et
    # iad (302 avec Location:, pas de trace de l'URL réelle dans le lien
    # lui-même). Voir SourceImap._resoudre_redirection.
    via_redirection: bool = False


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
    # Les deux ci-dessous restent NON VÉRIFIÉS (motifs de lien devinés faute
    # d'avoir reçu un vrai message) — recommandés le 2026-08-22 : gros volume
    # (Bpifrance) ou scraping direct bloqué (Bpifrance renvoie une page
    # d'erreur WAF, avendrealouer.fr refuse même robots.txt). Un premier
    # message réel forwardé permettra d'affiner motif_lien au besoin.
    Portail(
        # Diagnostiqué le 2026-08-29 (0 annonce, 6 j de suite, alors que des
        # mails arrivaient bien, non lus) via scripts/diagnostiquer_imap.py +
        # curl -I sur un vrai lien : tous les liens de l'email passent par
        # click.by.logic-immo.com/?qs=<jeton opaque>, AUCUNE trace de l'URL
        # réelle dedans (contrairement à Bien'ici, cf. bienici_alerte) — un
        # curl -I confirme un 302 vers www.logic-immo.com/detail-annonce/.../
        # <ID alphanumérique majuscule>, d'où via_redirection=True. L'ancien
        # motif (\d{5,}) ne collait de toute façon pas à cet ID réel.
        "logic_immo", ("logic-immo.com",),
        re.compile(r"https?://(?:www\.)?logic-immo\.com/[^\s\"'<>]*?([A-Z0-9]{8,})\b"),
        via_redirection=True,
    ),
    Portail(
        "bourse_des_locaux", ("reprise-entreprise.bpifrance.fr",),
        re.compile(r"https?://(?:www\.)?reprise-entreprise\.bpifrance\.fr/locaux/[^\s\"'<>]*-([a-f0-9]{8,})"),
    ),
    Portail(
        "avendrealouer", ("avendrealouer.fr",),
        re.compile(r"https?://(?:www\.)?avendrealouer\.fr/[^\s\"'<>]*?(\d{5,})"),
    ),
    # Idem non vérifiés — alertes créées par l'utilisateur le 2026-08-22.
    Portail(
        # Expéditeur réel (échantillon du 2026-08-23) : notif.iadinternational.com,
        # PAS iadfrance.fr — IAD envoie ses emails via un domaine transactionnel
        # distinct du site public. Les deux domaines sont reconnus par précaution
        # (site public + domaine d'envoi), le second retrouvé de justesse grâce à
        # un vrai message transféré (sans lui, ce portail n'aurait jamais rien
        # remonté malgré l'alerte bien créée). Seul l'EXPÉDITEUR avait été
        # vérifié à l'époque : les liens, eux, passent par le redirecteur
        # Selligent clic.iadinternational.com/f/a/<jeton>~~ — aussi opaque que
        # logic_immo (diagnostiqué le 2026-08-29, curl -I confirme un 302 vers
        # iadfrance.fr/redirect/property?propertyListingRef=<id numérique>,
        # que le motif ci-dessous reconnaît déjà une fois résolu).
        "iad", ("iadfrance.fr", "iadinternational.com"),
        re.compile(r"https?://(?:www\.)?(?:iadfrance\.fr|[a-z0-9.-]*iadinternational\.com)/[^\s\"'<>]*?(\d{5,})"),
        via_redirection=True,
    ),
    Portail(
        # Distinct de papcommerces.fr (déjà scrapé directement, source séparée) :
        # pap.fr est le site généraliste PAP, alertes propres.
        "pap", ("pap.fr",),
        re.compile(r"https?://(?:www\.)?pap\.fr/[^\s\"'<>]*?(\d{5,})"),
    ),
    Portail(
        # Expéditeur réel (2026-08-23) : no_reply@bienici.com. Probablement
        # redondant avec sources/bienici.py (API directe, déjà active) — gardé
        # quand même en filet de sécurité si l'API change un jour, coût nul
        # (le dédoublonnage cross-sources fusionne les doublons). Motif de
        # lien basé sur la vraie structure d'URL du site (bienici.py:87) —
        # mais la vraie URL n'apparaît en clair NULLE PART dans le lien
        # envoyé : Bien'ici emballe tout dans link.bienici.com/lnk/.../<n>/
        # <base64 de l'URL réelle> (diagnostiqué le 2026-08-29). Slug réel
        # observé "immo-facile-61351792" (tiret inclus, d'où [a-z0-9-] et
        # non [a-z0-9]) — voir _decoder_segment_base64, tenté avant toute
        # requête réseau puisque décodable localement, sans redirection.
        "bienici_alerte", ("bienici.com",),
        re.compile(r"https?://(?:www\.)?bienici\.com/annonce/([a-z0-9-]{5,})"),
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


def _decoder_segment_base64(href: str) -> str | None:
    """Certains redirecteurs (Selligent/Actito — ex. Bien'ici, cf. bienici_alerte)
    encodent la VRAIE destination en base64 dans le dernier segment du chemin :
    décodable localement, sans requête réseau, contrairement aux jetons
    opaques de logic_immo/iad (Portail.via_redirection). None si le segment
    n'est pas du base64 valide ou ne décode pas vers une URL http(s)."""
    segment = href.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1]
    if len(segment) < 8:
        return None
    manquant = -len(segment) % 4
    try:
        decode = base64.urlsafe_b64decode(segment + "=" * manquant).decode("utf-8")
    except Exception:  # noqa: BLE001 — segment pas du base64, ou pas de l'UTF-8
        return None
    return decode if decode.startswith("http") else None


def extraire_annonces_html(
    html: str, portail: Portail,
    resoudre_redirection: Callable[[str], str | None] | None = None,
) -> list[AnnonceBrute]:
    """Annonces contenues dans le HTML d'un email d'alerte.

    Trois façons de retrouver la vraie destination derrière un lien, essayées
    dans l'ordre (la première qui satisfait motif_lien l'emporte) :
    1. le lien brut, décodé %XX (cas simple, lien direct vers le portail) ;
    2. décodage base64 de son dernier segment (cf. _decoder_segment_base64) ;
    3. une vraie redirection HTTP via `resoudre_redirection`, fourni par
       l'appelant et budgété — seul recours pour un jeton opaque
       (portail.via_redirection ; voir SourceImap._resoudre_redirection).
    """
    soup = BeautifulSoup(html, "html.parser")
    annonces: dict[str, AnnonceBrute] = {}
    for lien in soup.find_all("a", href=True):
        href_brut = str(lien["href"])
        href = unquote(href_brut)
        trouve = portail.motif_lien.search(href)

        if not trouve:
            decode = _decoder_segment_base64(href_brut)
            if decode:
                trouve = portail.motif_lien.search(decode)

        if not trouve and portail.via_redirection and resoudre_redirection is not None:
            # Ces redirecteurs emballent TOUS les liens d'un email (logo,
            # réseaux sociaux, désabonnement...) dans le même format opaque,
            # indiscernables sans un vrai aller-retour HTTP — on ne le tente
            # donc que sur les liens dans un bloc à prix, pour ne pas cramer
            # le budget réseau plafonné (SourceImap.max_redirections) en pure perte.
            if "€" in _bloc_annonce(lien).get_text():
                reelle = resoudre_redirection(href_brut)
                if reelle:
                    trouve = portail.motif_lien.search(reelle)

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


# Mois IMAP (format RFC : indépendant de la langue du système)
_MOIS_IMAP = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


class SourceImap(Source):
    nom = "imap"

    def __init__(
        self, hote: str = "imap.gmail.com", dossier: str = "INBOX",
        jours_max: int = 14, max_redirections: int = 20,
    ) -> None:
        super().__init__()
        self.hote = hote
        self.dossier = dossier
        # Ne regarder que les alertes récentes : protège une boîte personnelle
        # pleine d'anciens non-lus (ils ne sont ni traités ni marqués lus).
        # Relevé à 14 j le 2026-08-23 (défaut précédent : 3 j) : une vraie
        # alerte Logic-immo, non lue, vieille de 6 jours, s'est révélée
        # invisible pour le robot à cause de cette fenêtre trop courte —
        # certains portails alertent par lots espacés, pas au quotidien.
        self.jours_max = jours_max
        # Plafond de vraies requêtes HTTP par tournée pour résoudre les jetons
        # opaques (portails via_redirection) — chaque appel coûte un aller-
        # retour réseau réel, contrairement au reste de cette source (pure
        # lecture IMAP). Décompté au fil des messages, jamais réinitialisé
        # en cours de run : voir _resoudre_redirection.
        self._redirections_restantes = max_redirections
        # Vrai si _resoudre_redirection a dû renoncer FAUTE de budget (pas
        # parce que le lien ne menait nulle part) pendant le message en
        # cours — remis à zéro par collecter() avant chaque message, lu juste
        # après pour décider s'il faut annuler le \Seen (cf. collecter()).
        self.budget_epuise = False

    def _depuis(self) -> str:
        quand = datetime.now() - timedelta(days=self.jours_max)
        return f"{quand.day}-{_MOIS_IMAP[quand.month - 1]}-{quand.year}"

    def _dossier_a_chercher(self, boite: imaplib.IMAP4_SSL) -> str:
        """Un filtre Gmail qui range une alerte (label + « ignorer la boîte de
        réception ») la fait disparaître d'INBOX sans que rien ne le signale —
        constaté le 2026-08-16 : authentification OK, 0 annonce, deux jours de
        suite. On cherche donc plutôt le dossier « tous les messages », repéré
        par l'attribut IMAP standard \\All (RFC 6154) — robuste à son nom
        localisé (« All Mail » en anglais, « Tous les messages » en français…)
        plutôt que de deviner un nom fixe. Repli sur self.dossier si absent."""
        try:
            statut, dossiers = boite.list()
        except Exception:  # noqa: BLE001 — repli silencieux
            return self.dossier
        if statut != "OK":
            return self.dossier
        for ligne in dossiers or []:
            texte = ligne.decode("utf-8", errors="replace") if isinstance(ligne, bytes) else str(ligne)
            if "\\All" not in texte:
                continue
            noms = re.findall(r'"([^"]*)"', texte)
            if noms:
                return noms[-1]
        return self.dossier

    def _resoudre_redirection(self, href: str) -> str | None:
        """Suit UNE redirection HTTP (302 Selligent/Adobe Campaign) pour
        révéler la vraie destination d'un jeton opaque — cf. curl -I sur un
        vrai lien logic_immo/iad le 2026-08-29, Portail.via_redirection.
        Plafonné (self._redirections_restantes) : jamais réinitialisé en
        cours de run, jamais bloquant (erreur/timeout/budget épuisé → None,
        ce lien est ignoré, pas le message entier)."""
        if self._redirections_restantes <= 0:
            self.budget_epuise = True
            return None
        self._redirections_restantes -= 1
        try:
            reponse = requests.head(
                href, allow_redirects=False, timeout=8,
                headers={"User-Agent": "Mozilla/5.0 (compatible; VeilleMursCommerciaux/0.1)"},
            )
        except Exception:  # noqa: BLE001 — un lien mort n'arrête rien
            return None
        if reponse.status_code in (301, 302, 303, 307, 308):
            return reponse.headers.get("Location")
        return None

    def extraire_message(self, message: email.message.EmailMessage) -> tuple[Portail | None, list[AnnonceBrute]]:
        partie = message.get_body(preferencelist=("html", "plain"))
        if partie is None:
            return None, []
        html = partie.get_content()
        portail = identifier_portail(str(message.get("From", "")), html)
        if portail is None:
            return None, []
        return portail, extraire_annonces_html(html, portail, resoudre_redirection=self._resoudre_redirection)

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
        # Un message lu mais qui n'en tire aucune annonce est un signal muet :
        # motif_lien qui ne correspond plus à la vraie structure des liens du
        # portail (plusieurs sont encore non vérifiés sur un message réel).
        # Sans ce compteur, "0 annonce" est indiscernable de "aucun mail reçu".
        portails_sans_extraction: dict[str, int] = {}
        with imaplib.IMAP4_SSL(self.hote) as boite:
            boite.login(utilisateur, mot_de_passe)
            dossier = self._dossier_a_chercher(boite)
            # Un nom de dossier avec espaces (ex. « [Gmail]/Tous les messages »
            # en français) doit être une chaîne IMAP entre guillemets — sans
            # ça le serveur refuse la commande (« Could not parse command »,
            # constaté le 2026-08-22 juste après l'ajout de cette recherche).
            boite.select(f'"{dossier}"')
            # Boîte personnelle oblige : on ne cherche QUE les emails des
            # portails connus — le reste de la boîte n'est ni lu ni marqué lu.
            numeros: list[bytes] = []
            depuis = self._depuis()
            for portail in PORTAILS:
                for domaine in portail.domaines:
                    _, resultats = boite.search(
                        None, f'(UNSEEN SINCE {depuis} FROM "{domaine}")'
                    )
                    if resultats and resultats[0]:
                        numeros.extend(
                            n for n in resultats[0].split() if n not in numeros
                        )
            for numero in numeros:
                # fetch RFC822 pose le drapeau \\Seen : le message ne sera pas retraité
                _, contenu = boite.fetch(numero, "(RFC822)")
                if not contenu or contenu[0] is None:
                    continue
                message = email.message_from_bytes(
                    contenu[0][1], policy=email.policy.default
                )
                self.budget_epuise = False
                try:
                    portail, trouvees = self.extraire_message(message)
                    if portail is not None and not trouvees:
                        portails_sans_extraction[portail.nom] = portails_sans_extraction.get(portail.nom, 0) + 1
                        if self.budget_epuise:
                            # Le lien existait (un bloc à prix a bien tenté une
                            # résolution) mais le budget réseau était à sec —
                            # remettre \Seen à zéro pour retenter au run
                            # suivant, sinon cette annonce est perdue pour
                            # toujours (fetch RFC822 l'a déjà marqué lu).
                            boite.store(numero, "-FLAGS", "\\Seen")
                    for annonce in trouvees:
                        annonces.setdefault(f"{annonce.source}:{annonce.id_source}", annonce)
                except Exception as exc:  # noqa: BLE001 — un email illisible n'arrête rien
                    self.avertissements.append(f"email illisible ({message.get('Subject')}) : {exc}")
        for nom_portail, total in portails_sans_extraction.items():
            self.avertissements.append(
                f"{nom_portail} : {total} email(s) lu(s) mais aucune annonce reconnue "
                "(motif de lien probablement à revoir sur un vrai message)"
            )
        return list(annonces.values())
