"""Phase 4 : extraction des alertes email + contenu des emails de notification."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pipeline.modeles import TypeMurs
from pipeline.notifications import notifier, notifier_sante_sources
from sources.imap_alertes import PORTAILS, SourceImap, extraire_annonces_html, identifier_portail
from tests.fabriques import faire_annonce

FIXTURES = Path(__file__).parent / "fixtures"


# --- Extraction d'un email d'alerte ---


def _leboncoin():
    return next(p for p in PORTAILS if p.nom == "leboncoin")


def test_identifier_portail():
    assert identifier_portail("LeBonCoin <noreply@leboncoin.fr>", "").nom == "leboncoin"
    assert identifier_portail("alertes@geolocaux.com", "").nom == "geolocaux"
    assert identifier_portail("inconnu@exemple.fr", "<html></html>") is None


def test_identifier_portail_nouveaux_2026_08_22():
    assert identifier_portail("alertes@logic-immo.com", "").nom == "logic_immo"
    assert identifier_portail("noreply@reprise-entreprise.bpifrance.fr", "").nom == "bourse_des_locaux"
    assert identifier_portail("contact@avendrealouer.fr", "").nom == "avendrealouer"


def test_motif_lien_bourse_des_locaux_id_hexadecimal():
    portail = next(p for p in PORTAILS if p.nom == "bourse_des_locaux")
    href = ("https://reprise-entreprise.bpifrance.fr/locaux/annonce-locaux/"
            "vente-de-murs-de-boutique-yvelines-78-86ec40815c14bec3a9e53a6091e37970")
    trouve = portail.motif_lien.search(href)
    assert trouve and trouve.group(1) == "86ec40815c14bec3a9e53a6091e37970"


class _BoiteImapFactice:
    """Réponse `LIST` minimale : juste ce que `_dossier_a_chercher` regarde."""
    def __init__(self, lignes: list[bytes], statut: str = "OK"):
        self._lignes = lignes
        self._statut = statut

    def list(self):
        return self._statut, self._lignes


def test_dossier_a_chercher_trouve_all_mail_via_attribut_special_use():
    # Repéré par l'attribut IMAP \All (RFC 6154), pas par un nom fixe —
    # fonctionne donc aussi sur un compte Gmail en français.
    boite = _BoiteImapFactice([
        b'(\\HasNoChildren) "/" "INBOX"',
        b'(\\HasNoChildren \\All) "/" "[Gmail]/Tous les messages"',
        b'(\\HasNoChildren \\Trash) "/" "[Gmail]/Corbeille"',
    ])
    assert SourceImap()._dossier_a_chercher(boite) == "[Gmail]/Tous les messages"


def test_dossier_a_chercher_repli_sur_inbox_si_absent():
    boite = _BoiteImapFactice([b'(\\HasNoChildren) "/" "INBOX"'])
    assert SourceImap()._dossier_a_chercher(boite) == "INBOX"


def test_dossier_a_chercher_repli_sur_inbox_si_list_echoue():
    boite = _BoiteImapFactice([], statut="NO")
    assert SourceImap()._dossier_a_chercher(boite) == "INBOX"


def test_extraction_alerte_leboncoin():
    html = (FIXTURES / "alerte_leboncoin.html").read_text(encoding="utf-8")
    annonces = extraire_annonces_html(html, _leboncoin())
    assert len(annonces) == 2

    occ = next(a for a in annonces if a.id_source == "2801234567")
    assert occ.source == "alerte_leboncoin"
    assert occ.ville == "Saint-Denis"
    assert occ.code_postal == "93200"
    assert occ.prix == 235_000            # le prix, pas le loyer (max des montants €)
    assert occ.surface_m2 == 65
    assert occ.type_murs is TypeMurs.MURS_OCCUPES
    assert occ.loyer_mensuel == 1_600     # 19 200 € annuels / 12
    assert occ.image_url and "img.leboncoin.fr" in occ.image_url

    libre = next(a for a in annonces if a.id_source == "2809876543")
    assert libre.type_murs is TypeMurs.MURS_LIBRES
    assert libre.code_postal == "92700"


# --- Notifications ---


def _annonces_notification():
    pepite = faire_annonce(id="pep1", titre="Murs occupés en or", ville="Paris 18e",
                           code_postal="75018")
    pepite.score = 85
    pepite.rendement_brut_pct = 9.2
    pepite.lecture_prix = "Décote lisible : des travaux sont signalés dans l'annonce."
    pepite.bail_echeance_annee = datetime.now().year + 6
    banale = faire_annonce(id="ban1", titre="Murs corrects")
    banale.score = 55
    return {"pep1": pepite, "ban1": banale}


def test_notifications_non_configurees_sans_secrets(config, monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.delenv("EMAIL_TO", raising=False)
    meta: dict = {}
    rapport = notifier(_annonces_notification(), ["pep1", "ban1"], meta, config)
    assert rapport["statut"].startswith("non configurées")
    assert rapport["pepites"] == 1
    # rien n'est marqué notifié tant que rien n'est parti
    assert "pepites_notifiees" not in meta


def test_emails_construits_et_pepite_notifiee_une_seule_fois(config, monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "test-cle")
    monkeypatch.setenv("EMAIL_TO", "georgesdurand75@gmail.com")
    # email_quotidien est désactivé en production (l'utilisateur ne veut que
    # l'alerte pépite) : ce test vérifie explicitement le contenu de l'email
    # quotidien, donc on le réactive pour sa durée, indépendamment du réglage
    # courant de config.yaml.
    monkeypatch.setitem(config["notifications"], "email_quotidien", True)
    envois: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "pipeline.notifications._envoyer",
        lambda cle, dest, sujet, html: envois.append((sujet, html)),
    )

    annonces = _annonces_notification()
    meta: dict = {}
    rapport = notifier(annonces, ["pep1", "ban1"], meta, config)
    assert rapport["statut"] == "ok"
    assert len(envois) == 2  # pépite + quotidien

    sujet_pepite, html_pepite = envois[0]
    assert "🔥" in sujet_pepite and "85" in sujet_pepite
    assert "Murs occupés en or" in html_pepite
    assert "9,2 %" in html_pepite                      # rendement dans l'email
    assert "travaux" in html_pepite                    # lecture du prix incluse
    assert "Bail jusqu'en" in html_pepite and "~6 an" in html_pepite  # échéance de bail incluse
    assert "https://exemple.fr/1" in html_pepite       # lien direct annonce
    # Liens directs vers CETTE annonce sur le dashboard (pas juste l'accueil) :
    # raccourcit le trajet entre « pépite reçue » et « vous au téléphone ».
    assert f"{config['notifications']['url_dashboard'].rstrip('/')}/#annonce=pep1" in html_pepite
    assert "action=contactee" in html_pepite

    sujet_quotidien, html_quotidien = envois[1]
    assert "2" in sujet_quotidien                      # 2 nouveautés
    assert "Murs corrects" in html_quotidien

    # Deuxième run : la pépite est mémorisée, pas de nouvel email pépite
    assert meta["pepites_notifiees"] == ["pep1"]
    envois.clear()
    rapport2 = notifier(annonces, [], meta, config)
    assert rapport2["pepites"] == 0
    assert envois == []                                # rien de nouveau -> aucun email


# --- Alerte de source en panne ---


def _historique_panne(source: str = "imap", jours: int = 2) -> dict:
    return {source: [
        {"jour": f"2026-08-{10 + i:02d}", "statut": "erreur", "annonces": 0, "message": "AUTH"}
        for i in range(jours)
    ]}


def test_alerte_sante_non_configuree_sans_secrets(config, monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.delenv("EMAIL_TO", raising=False)
    meta: dict = {}
    rapport = notifier_sante_sources(_historique_panne(), meta, config)
    assert rapport["statut"].startswith("non configurées")
    assert rapport["nouvelles_alertes"] == 1
    # la panne est mémorisée même sans envoi, pour ne pas la perdre au run suivant
    assert meta["sources_en_alerte"] == ["imap"]


def test_alerte_sante_envoyee_une_seule_fois_puis_reinitialisee_si_resolue(config, monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "test-cle")
    monkeypatch.setenv("EMAIL_TO", "georgesdurand75@gmail.com")
    monkeypatch.setitem(config["notifications"]["alerte_source_en_panne"], "jours_consecutifs", 2)
    envois: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "pipeline.notifications._envoyer",
        lambda cle, dest, sujet, html: envois.append((sujet, html)),
    )

    meta: dict = {}
    rapport = notifier_sante_sources(_historique_panne(), meta, config)
    assert rapport["statut"] == "ok"
    assert len(envois) == 1
    sujet, html = envois[0]
    assert "1 source" in sujet
    assert "imap" in html and "AUTH" in html

    # Toujours en panne au run suivant : déjà alertée, pas de nouvel email
    envois.clear()
    rapport2 = notifier_sante_sources(_historique_panne(), meta, config)
    assert rapport2["nouvelles_alertes"] == 0
    assert envois == []

    # La source repart : elle sort de la mémoire, une rechute redéclenchera une alerte
    rapport3 = notifier_sante_sources({}, meta, config)
    assert meta["sources_en_alerte"] == []


def test_pas_de_panne_sous_le_seuil(config, monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "test-cle")
    monkeypatch.setenv("EMAIL_TO", "georgesdurand75@gmail.com")
    meta: dict = {}
    rapport = notifier_sante_sources(_historique_panne(jours=1), meta, config)
    assert rapport["statut"] == "rien à signaler"
    assert meta["sources_en_alerte"] == []


def test_source_sporadique_configuree_n_alerte_pas_a_zero_annonce(config, monkeypatch):
    # encheres_publiques est listée dans sources_volume_sporadique (config.yaml) :
    # 0 annonce plusieurs jours de suite ne doit pas déclencher d'alerte.
    monkeypatch.setenv("RESEND_API_KEY", "test-cle")
    monkeypatch.setenv("EMAIL_TO", "georgesdurand75@gmail.com")
    historique = {"encheres_publiques": [
        {"jour": "2026-08-15", "statut": "ok", "annonces": 0, "message": None},
        {"jour": "2026-08-16", "statut": "ok", "annonces": 0, "message": None},
    ]}
    meta: dict = {}
    rapport = notifier_sante_sources(historique, meta, config)
    assert rapport["statut"] == "rien à signaler"
    assert meta["sources_en_alerte"] == []
