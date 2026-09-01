"""Diagnostic local et LECTURE SEULE des alertes email (ne marque rien comme lu).

À lancer en local (jamais en CI), avec le même compte Gmail que IMAP_USER :

    python scripts/diagnostiquer_imap.py

Le mot de passe d'application est demandé de façon interactive (getpass) : il
reste sur cette machine, jamais envoyé nulle part, jamais collé dans un chat.

Rejoue EXACTEMENT la même extraction que sources.imap_alertes (base64 local +
vraie redirection HTTP budgétée) sur les emails déjà reçus (lus ou non, 14
derniers jours) : affiche les annonces réellement extraites, et pour les
messages identifiés mais à 0 annonce, les liens bruts avec un repère
[OK]/[REDIRECTION]/[??] pour corriger motif_lien au besoin (cf.
imap-alertes-diagnostic).
"""
from __future__ import annotations

import email
import email.policy
import getpass
import imaplib
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402

from sources.imap_alertes import (  # noqa: E402
    PORTAILS,
    _decoder_segment_base64,
    extraire_annonces_html,
    identifier_portail,
)

HOTE = "imap.gmail.com"
JOURS_MAX = 14
MAX_LIENS_AFFICHES = 8
MAX_REDIRECTIONS_TOTAL = 30  # même ordre de grandeur qu'en prod (config.yaml)


def dossier_all_mail(boite: imaplib.IMAP4_SSL) -> str:
    statut, dossiers = boite.list()
    if statut == "OK":
        for ligne in dossiers or []:
            texte = ligne.decode("utf-8", errors="replace") if isinstance(ligne, bytes) else str(ligne)
            if "\\All" in texte:
                noms = re.findall(r'"([^"]*)"', texte)
                if noms:
                    return noms[-1]
    return "INBOX"


def main() -> None:
    utilisateur = os.environ.get("IMAP_USER") or input("Adresse Gmail (IMAP_USER) : ").strip()
    mot_de_passe = os.environ.get("IMAP_PASSWORD") or getpass.getpass(
        "Mot de passe d'application (IMAP_PASSWORD, invisible) : "
    )

    redirections_restantes = [MAX_REDIRECTIONS_TOTAL]  # liste = mutable dans la closure

    def resoudre(href: str) -> str | None:
        if redirections_restantes[0] <= 0:
            return None
        redirections_restantes[0] -= 1
        try:
            reponse = requests.head(href, allow_redirects=False, timeout=8,
                                     headers={"User-Agent": "Mozilla/5.0"})
        except Exception:
            return None
        if reponse.status_code in (301, 302, 303, 307, 308):
            return reponse.headers.get("Location")
        return None

    depuis = datetime.now() - timedelta(days=JOURS_MAX)
    mois = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    depuis_imap = f"{depuis.day}-{mois[depuis.month - 1]}-{depuis.year}"

    with imaplib.IMAP4_SSL(HOTE) as boite:
        boite.login(utilisateur, mot_de_passe)
        dossier = dossier_all_mail(boite)
        print(f"→ dossier utilisé : {dossier}\n")
        boite.select(f'"{dossier}"', readonly=True)  # readonly=True : ne marque jamais \\Seen

        numeros: list[bytes] = []
        for portail in PORTAILS:
            for domaine in portail.domaines:
                _, resultats = boite.search(None, f'(SINCE {depuis_imap} FROM "{domaine}")')
                if resultats and resultats[0]:
                    numeros.extend(n for n in resultats[0].split() if n not in numeros)

        if not numeros:
            print("Aucun email des portails connus trouvé sur les 14 derniers jours.")
            print("→ vérifie le dossier Spam à la main : All Mail exclut Spam et Corbeille.")
            return

        print(f"{len(numeros)} email(s) trouvé(s) (lus ou non lus).\n")

        for numero in numeros:
            _, contenu = boite.fetch(numero, "(BODY.PEEK[])")  # PEEK : ne marque pas comme lu
            if not contenu or contenu[0] is None:
                continue
            message = email.message_from_bytes(contenu[0][1], policy=email.policy.default)
            expediteur = str(message.get("From", ""))
            sujet = str(message.get("Subject", ""))
            partie = message.get_body(preferencelist=("html", "plain"))
            html = partie.get_content() if partie else ""
            portail = identifier_portail(expediteur, html)

            print("=" * 70)
            print(f"De      : {expediteur}")
            print(f"Objet   : {sujet}")
            print(f"Portail : {portail.nom if portail else '(non reconnu — domaine absent de PORTAILS)'}")

            if portail is None:
                print()
                continue

            annonces = extraire_annonces_html(html, portail, resoudre_redirection=resoudre)
            if annonces:
                for a in annonces:
                    print(f"  ✓ {a.titre} — {a.ville or '?'} {a.code_postal or ''} — "
                          f"{a.prix or '?'} € — {a.url}")
                print()
                continue

            print("  0 annonce extraite. Liens bruts trouvés :")
            soup = BeautifulSoup(html, "html.parser")
            hrefs = [str(a["href"]) for a in soup.find_all("a", href=True)]
            affiches = 0
            for href in hrefs:
                if affiches >= MAX_LIENS_AFFICHES:
                    break
                if any(mot in href.lower() for mot in ("unsubscribe", "desabon", "logo", "pixel", ".png", ".gif")):
                    continue
                decode = unquote(href)
                marque = "[??]"
                if portail.motif_lien.search(decode):
                    marque = "[OK, mais pas extrait ?!]"
                elif _decoder_segment_base64(href):
                    marque = "[base64 décodable, motif_lien à vérifier]"
                else:
                    marque = "[lien opaque : résolu automatiquement ci-dessus, motif_lien à revoir si toujours 0]"
                print(f"    {marque} {href}")
                affiches += 1
            print()

        if redirections_restantes[0] <= 0:
            print(f"⚠ Budget de {MAX_REDIRECTIONS_TOTAL} redirections épuisé — relance si besoin.")


if __name__ == "__main__":
    main()
