"""Phase 4 : extraction des alertes email + contenu des emails de notification."""
from __future__ import annotations

from pathlib import Path

from pipeline.modeles import TypeMurs
from pipeline.notifications import notifier
from sources.imap_alertes import PORTAILS, extraire_annonces_html, identifier_portail
from tests.fabriques import faire_annonce

FIXTURES = Path(__file__).parent / "fixtures"


# --- Extraction d'un email d'alerte ---


def _leboncoin():
    return next(p for p in PORTAILS if p.nom == "leboncoin")


def test_identifier_portail():
    assert identifier_portail("LeBonCoin <noreply@leboncoin.fr>", "").nom == "leboncoin"
    assert identifier_portail("alertes@geolocaux.com", "").nom == "geolocaux"
    assert identifier_portail("inconnu@exemple.fr", "<html></html>") is None


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
    assert "https://exemple.fr/1" in html_pepite       # lien direct annonce

    sujet_quotidien, html_quotidien = envois[1]
    assert "2" in sujet_quotidien                      # 2 nouveautés
    assert "Murs corrects" in html_quotidien

    # Deuxième run : la pépite est mémorisée, pas de nouvel email pépite
    assert meta["pepites_notifiees"] == ["pep1"]
    envois.clear()
    rapport2 = notifier(annonces, [], meta, config)
    assert rapport2["pepites"] == 0
    assert envois == []                                # rien de nouveau -> aucun email
