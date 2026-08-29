"""Diagnostic local et LECTURE SEULE des alertes email (ne marque rien comme lu).

À lancer en local (jamais en CI), avec le même compte Gmail que IMAP_USER :

    python scripts/diagnostiquer_imap.py

Le mot de passe d'application est demandé de façon interactive (getpass) : il
reste sur cette machine, jamais envoyé nulle part, jamais collé dans un chat.

Affiche, pour chaque email des portails connus (lu ou non lu, 14 derniers
jours) : l'expéditeur, l'objet, et les liens bruts trouvés dans le corps —
avec un repère [OK]/[??] selon que motif_lien du portail les reconnaît déjà.
Sert à corriger motif_lien pour les portails jamais vérifiés sur un vrai
message (logic_immo notamment, cf. imap-alertes-diagnostic).
"""
from __future__ import annotations

import email
import email.policy
import getpass
import imaplib
import os
import sys
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bs4 import BeautifulSoup  # noqa: E402

from sources.imap_alertes import PORTAILS, identifier_portail  # noqa: E402

HOTE = "imap.gmail.com"
JOURS_MAX = 14
MAX_LIENS_PAR_MESSAGE = 8


def dossier_all_mail(boite: imaplib.IMAP4_SSL) -> str:
    statut, dossiers = boite.list()
    if statut == "OK":
        for ligne in dossiers or []:
            texte = ligne.decode("utf-8", errors="replace") if isinstance(ligne, bytes) else str(ligne)
            if "\\All" in texte:
                import re
                noms = re.findall(r'"([^"]*)"', texte)
                if noms:
                    return noms[-1]
    return "INBOX"


def main() -> None:
    utilisateur = os.environ.get("IMAP_USER") or input("Adresse Gmail (IMAP_USER) : ").strip()
    mot_de_passe = os.environ.get("IMAP_PASSWORD") or getpass.getpass(
        "Mot de passe d'application (IMAP_PASSWORD, invisible) : "
    )

    from datetime import datetime, timedelta
    depuis = (datetime.now() - timedelta(days=JOURS_MAX))
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

            soup = BeautifulSoup(html, "html.parser")
            hrefs = [str(a["href"]) for a in soup.find_all("a", href=True)]
            print(f"Liens trouvés : {len(hrefs)} (affichage des {MAX_LIENS_PAR_MESSAGE} premiers pertinents)")
            affiches = 0
            for href in hrefs:
                if affiches >= MAX_LIENS_PAR_MESSAGE:
                    break
                decode = unquote(href)
                marque = "[??]"
                if portail is not None and portail.motif_lien.search(decode):
                    marque = "[OK]"
                # Ignore les liens évidemment hors-sujet (désabonnement, logos, pixels de tracking).
                if any(mot in href.lower() for mot in ("unsubscribe", "desabon", "logo", "pixel", ".png", ".gif")):
                    continue
                print(f"  {marque} {href}")
                affiches += 1
            print()


if __name__ == "__main__":
    main()
