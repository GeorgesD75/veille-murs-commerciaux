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
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable
from urllib.parse import unquote, urlparse

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
    # Note : il n'y a plus de drapeau « ce portail passe par un redirecteur ».
    # Il fallait le renseigner d'avance, donc avoir déjà disséqué un vrai
    # message — impossible pour un portail qui ne remonte justement rien.
    # La résolution est désormais tentée dès que le motif direct échoue sur un
    # lien à prix (voir extraire_annonces_html) : la question se tranche à
    # l'exécution, pas par hypothèse.


PORTAILS: list[Portail] = [
    Portail(
        "leboncoin", ("leboncoin.fr",),
        re.compile(r"https?://(?:www\.)?leboncoin\.fr/[a-z_/]*?(\d{6,})"),
    ),
    Portail(
        "seloger_bureaux", ("seloger", "bureauxlocaux.com"),
        re.compile(r"https?://(?:www\.)?(?:seloger[a-z-]*\.com|bureauxlocaux\.com)/[^\s\"'<>]*(?<!\d)(\d{5,})(?!\d)"),
    ),
    Portail(
        "geolocaux", ("geolocaux.com",),
        re.compile(r"https?://(?:www\.)?geolocaux\.com/[^\s\"'<>]*(?<!\d)(\d{4,})(?!\d)"),
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
        # <ID alphanumérique majuscule>. L'ancien motif (\d{5,}) ne collait de
        # toute façon pas à cet ID réel. Les liens sont donc opaques : la
        # résolution automatique s'en charge.
        "logic_immo", ("logic-immo.com",),
        re.compile(r"https?://(?:www\.)?logic-immo\.com/[^\s\"'<>]*?([A-Z0-9]{8,})\b"),
    ),
    Portail(
        "bourse_des_locaux", ("reprise-entreprise.bpifrance.fr",),
        re.compile(r"https?://(?:www\.)?reprise-entreprise\.bpifrance\.fr/locaux/[^\s\"'<>]*-([a-f0-9]{8,})"),
    ),
    Portail(
        "avendrealouer", ("avendrealouer.fr",),
        re.compile(r"https?://(?:www\.)?avendrealouer\.fr/[^\s\"'<>]*(?<!\d)(\d{5,})(?!\d)"),
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
        re.compile(r"https?://(?:www\.)?(?:iadfrance\.fr|[a-z0-9.-]*iadinternational\.com)/[^\s\"'<>]*(?<!\d)(\d{5,})(?!\d)"),
    ),
    Portail(
        # Distinct de papcommerces.fr (déjà scrapé directement, source séparée) :
        # pap.fr est le site généraliste PAP, alertes propres.
        "pap", ("pap.fr",),
        re.compile(r"https?://(?:www\.)?pap\.fr/[^\s\"'<>]*(?<!\d)(\d{5,})(?!\d)"),
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


def _mene_a_une_annonce(lien: Tag) -> bool:
    """Ce lien est-il DANS un bloc à prix, donc probablement une annonce ?

    Le test naïf « € dans _bloc_annonce(lien) » ne marche pas : un lien SANS
    prix voisin (logo, désabonnement, réseaux sociaux) fait remonter jusqu'à
    <body>, qui contient les prix des AUTRES annonces — et répond donc vrai
    pour tout le monde. Mesuré le 2026-09-05 sur un email type : 5 liens sur 5
    passaient le garde-fou alors que 2 seulement étaient des annonces, d'où un
    budget de redirection brûlé aux deux tiers en pure perte (le retard
    grimpait : 35 -> 73 messages reportés en cinq jours).

    Exiger un ancêtre PLUS ÉTROIT que <body> suffit à trancher : un vrai bloc
    d'annonce est toujours un conteneur local (div, td, table...).
    """
    bloc = _bloc_annonce(lien)
    return bloc.name not in ("body", "html") and "€" in bloc.get_text()


def _decoder_segment_base64(href: str) -> str | None:
    """Certains redirecteurs (Selligent/Actito — ex. Bien'ici, cf. bienici_alerte)
    encodent la VRAIE destination en base64 dans le dernier segment du chemin :
    décodable localement, sans requête réseau, contrairement aux jetons
    opaques de logic_immo/iad. None si le segment
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
       (tentée dès que le motif direct échoue ; voir SourceImap._resoudre_redirection).
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

        if not trouve and resoudre_redirection is not None:
            # Tenté pour TOUT portail, plus seulement ceux marqués d'avance
            # (ancien via_redirection). Savoir à l'avance qu'un portail emballe
            # ses liens supposait d'avoir déjà disséqué un vrai message : c'est
            # exactement ce qui manquait pour seloger_bureaux (10 alertes lues,
            # 0 annonce, motif direct incapable de matcher un jeton opaque).
            # Ici la question se tranche à l'exécution : si le motif direct a
            # échoué, le lien est peut-être opaque — on regarde, au lieu de
            # supposer. Deux garde-fous rendent l'essai sûr : seulement les
            # liens d'un bloc à PRIX (les redirecteurs emballent aussi logo,
            # désabonnement, réseaux sociaux — indiscernables autrement), et le
            # budget temps de _resoudre_redirection. Coût nul pour un portail à
            # liens directs : son motif matche, on n'arrive jamais ici.
            if _mene_a_une_annonce(lien):
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
        jours_max: int = 14, max_redirections: int = 400,
        budget_redirection_s: float = 240.0, timeout_redirection_s: float = 5.0,
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
        # Budget de résolution des jetons opaques :
        # chaque lien coûte un vrai aller-retour réseau, contrairement au reste
        # de cette source (pure lecture IMAP).
        #
        # Un simple COMPTEUR ne suffisait pas. Il doit être calibré sur le pire
        # cas (tout part en timeout), donc rester bas — 60 auparavant — alors
        # qu'en régime normal une résolution prend ~200-400 ms. Résultat mesuré
        # les 2026-08-30 → 09-01 : le budget partait à sec chaque tournée et le
        # retard s'accumulait au lieu de se résorber (15 → 16 → 37 emails
        # reportés en trois jours, sur logic_immo surtout).
        #
        # Le vrai plafond à respecter est le TEMPS (tournée CI ~20 min), pas le
        # nombre de liens. Un budget en secondes s'adapte tout seul : liens
        # rapides -> des centaines résolus et le retard se résorbe ; liens
        # lents -> on s'arrête tôt, borné. Le compteur ne sert plus que de
        # garde-fou absolu. Pire cas ≈ budget + un appel en vol ≈ 4 min.
        self._redirections_restantes = max_redirections
        self._budget_redirection_s = budget_redirection_s
        self._timeout_redirection_s = timeout_redirection_s
        self._debut_redirections: float | None = None
        # Vrai si _resoudre_redirection a dû renoncer FAUTE de budget (pas
        # parce que le lien ne menait nulle part) pendant le message en
        # cours — remis à zéro par collecter() avant chaque message, lu juste
        # après pour décider s'il faut annuler le \Seen (cf. collecter()).
        self.budget_epuise = False
        # Hôtes des liens du dernier message dont rien n'a pu être extrait :
        # renseigné par extraire_message, lu par collecter pour l'avertissement.
        self.liens_non_reconnus: list[str] = []

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

    def _temps_redirection_ecoule(self) -> bool:
        """Le chrono démarre à la PREMIÈRE résolution, pas au début du run :
        le temps passé en lecture IMAP pure ne doit pas grignoter le budget
        réseau. Jamais réinitialisé ensuite (comme le compteur)."""
        if self._debut_redirections is None:
            self._debut_redirections = time.monotonic()
            return False
        return (time.monotonic() - self._debut_redirections) >= self._budget_redirection_s

    def _resoudre_redirection(self, href: str) -> str | None:
        """Suit UNE redirection HTTP (302 Selligent/Adobe Campaign) pour
        révéler la vraie destination d'un jeton opaque — cf. curl -I sur un
        vrai lien logic_immo/iad le 2026-08-29.
        Plafonné (self._redirections_restantes) : jamais réinitialisé en
        cours de run, jamais bloquant (erreur/timeout/budget épuisé → None,
        ce lien est ignoré, pas le message entier)."""
        if self._redirections_restantes <= 0 or self._temps_redirection_ecoule():
            self.budget_epuise = True
            return None
        self._redirections_restantes -= 1
        try:
            reponse = requests.head(
                href, allow_redirects=False, timeout=self._timeout_redirection_s,
                headers={"User-Agent": "Mozilla/5.0 (compatible; VeilleMursCommerciaux/0.1)"},
            )
        except Exception:  # noqa: BLE001 — un lien mort n'arrête rien
            return None
        if reponse.status_code in (301, 302, 303, 307, 308):
            return reponse.headers.get("Location")
        return None

    def diagnostiquer_liens(self, html: str, maximum: int = 3) -> list[str]:
        """Hôtes des liens situés dans un bloc à prix — donc les liens qui
        MÈNENT probablement à une annonce.

        Sert à diagnostiquer un motif_lien caduc sans devoir se faire
        transférer un vrai message : la tournée suivante dit d'elle-même à
        quoi ressemblent les liens. Deviner un motif sans preuve a déjà coûté
        cher (domaine IAD inventé le 2026-08-29, faux jusqu'au premier vrai
        message reçu) — ici la preuve vient toute seule. Un hôte de tracking
        (click.…, mail.…, redirect.…) au lieu du domaine du portail signe un
        lien opaque — désormais résolu automatiquement ; si le compte reste
        à 0, c'est le motif_lien lui-même qui ne colle pas à l'URL résolue.
        """
        soup = BeautifulSoup(html, "html.parser")
        hotes: dict[str, int] = {}
        for lien in soup.find_all("a", href=True):
            # Même règle que l'extraction (_mene_a_une_annonce) : le diagnostic
            # doit décrire EXACTEMENT les liens sur lesquels le budget part,
            # sinon il envoie chercher au mauvais endroit.
            if not _mene_a_une_annonce(lien):
                continue
            hote = urlparse(str(lien["href"])).netloc.lower()
            if hote:
                hotes[hote] = hotes.get(hote, 0) + 1
        classes = sorted(hotes.items(), key=lambda kv: (-kv[1], kv[0]))
        return [f"{hote} ×{n}" for hote, n in classes[:maximum]]

    def extraire_message(self, message: email.message.EmailMessage) -> tuple[Portail | None, list[AnnonceBrute]]:
        partie = message.get_body(preferencelist=("html", "plain"))
        if partie is None:
            return None, []
        html = partie.get_content()
        portail = identifier_portail(str(message.get("From", "")), html)
        if portail is None:
            return None, []
        trouvees = extraire_annonces_html(
            html, portail, resoudre_redirection=self._resoudre_redirection
        )
        # Rien extrait : on garde à quoi ressemblaient les liens, pour que
        # l'avertissement de la tournée dise QUOI corriger (cf. diagnostiquer_liens).
        self.liens_non_reconnus = self.diagnostiquer_liens(html) if not trouvees else []
        return portail, trouvees

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
        # Distingué du cas "budget de redirection à sec" (portails_budget_epuise) :
        # ce dernier n'a rien à voir avec un motif_lien caduc, le message est
        # simplement reporté au run suivant — un vrai "0 annonce" mérite une
        # alerte, un budget à sec non (constaté le 2026-08-29 : logic_immo a
        # signalé 7 échecs le jour même où il fonctionnait déjà par ailleurs).
        portails_sans_extraction: dict[str, int] = {}
        portails_budget_epuise: dict[str, int] = {}
        # Portail -> hôtes des liens vus dans ses messages illisibles : c'est
        # la PREUVE de ce qu'il faut corriger, remontée dans l'avertissement.
        portails_liens_vus: dict[str, dict[str, None]] = {}
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
                        if self.budget_epuise:
                            portails_budget_epuise[portail.nom] = portails_budget_epuise.get(portail.nom, 0) + 1
                            # Le lien existait (un bloc à prix a bien tenté une
                            # résolution) mais le budget réseau était à sec —
                            # remettre \Seen à zéro pour retenter au run
                            # suivant, sinon cette annonce est perdue pour
                            # toujours (fetch RFC822 l'a déjà marqué lu).
                            boite.store(numero, "-FLAGS", "\\Seen")
                        else:
                            portails_sans_extraction[portail.nom] = portails_sans_extraction.get(portail.nom, 0) + 1
                            # Message d'un portail CONNU dont aucun lien n'a été
                            # reconnu : motif_lien à corriger, pas un message
                            # vide. Le laisser marqué lu le perdrait POUR
                            # TOUJOURS — alors que c'est précisément le message
                            # qui contient l'annonce ratée, et celui qui
                            # permettra de corriger le motif. Constaté le
                            # 2026-09-01 : seloger_bureaux consommait ainsi 3 à
                            # 6 alertes par jour, définitivement perdues. On
                            # remet donc \Seen à zéro : le jour où le motif est
                            # corrigé, toutes les alertes encore dans la
                            # fenêtre (jours_max) repassent d'elles-mêmes. Pas
                            # d'accumulation sans fin : cette fenêtre les fait
                            # sortir naturellement au bout de jours_max.
                            boite.store(numero, "-FLAGS", "\\Seen")
                            vus = portails_liens_vus.setdefault(portail.nom, {})
                            for hote in self.liens_non_reconnus:
                                vus.setdefault(hote, None)
                    for annonce in trouvees:
                        annonces.setdefault(f"{annonce.source}:{annonce.id_source}", annonce)
                except Exception as exc:  # noqa: BLE001 — un email illisible n'arrête rien
                    self.avertissements.append(f"email illisible ({message.get('Subject')}) : {exc}")
        for nom_portail, total in portails_sans_extraction.items():
            # Les hôtes réellement rencontrés valent mieux qu'un « à revoir »
            # sans piste : un hôte de tracking (click.…, mail.…) au lieu du
            # domaine du portail = liens opaques (résolus automatiquement).
            liens = list(portails_liens_vus.get(nom_portail, {}))
            piste = f" — liens vus : {', '.join(liens)}" if liens else ""
            self.avertissements.append(
                f"{nom_portail} : {total} email(s) lu(s) mais aucune annonce reconnue "
                f"(motif de lien à revoir){piste}"
            )
        for nom_portail, total in portails_budget_epuise.items():
            self.avertissements.append(
                f"{nom_portail} : {total} email(s) reportés au run suivant "
                "(budget de redirection épuisé ce run-ci, rien à corriger)"
            )
        return list(annonces.values())
