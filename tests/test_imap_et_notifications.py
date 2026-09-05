"""Phase 4 : extraction des alertes email + contenu des emails de notification."""
from __future__ import annotations

import base64
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

from pipeline.modeles import TypeMurs
from pipeline.notifications import notifier, notifier_sante_sources
from sources.imap_alertes import (
    PORTAILS,
    SourceImap,
    _decoder_segment_base64,
    extraire_annonces_html,
    identifier_portail,
)
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
    assert identifier_portail("alertes@pap.fr", "").nom == "pap"


def test_logic_immo_matche_le_domaine_d_envoi_reel():
    # Échantillon réel du 2026-08-23 : "LogicImmo <annonces@alertes.logic-immo.com>"
    assert identifier_portail("LogicImmo <annonces@alertes.logic-immo.com>", "").nom == "logic_immo"


def test_iad_matche_le_vrai_domaine_d_envoi_pas_le_site_public():
    # Échantillon réel du 2026-08-23 : "iad France <no-reply@notif.iadinternational.com>" —
    # PAS iadfrance.fr (le site public), la première hypothèse était fausse.
    assert identifier_portail(
        "iad France <no-reply@notif.iadinternational.com>", ""
    ).nom == "iad"
    assert identifier_portail("alertes@iadfrance.fr", "").nom == "iad"  # gardé par précaution


def test_bienici_alerte_matche_le_domaine_reel():
    # Échantillon réel du 2026-08-23 : "Bien'ici <no_reply@bienici.com>"
    assert identifier_portail("Bien'ici <no_reply@bienici.com>", "").nom == "bienici_alerte"


def test_tous_les_expediteurs_reellement_recus_sont_reconnus():
    """Les 6 expéditeurs RÉELS relevés dans la boîte de l'utilisateur
    (2026-09-01). Deviner un domaine a déjà coûté cher (iadfrance.fr inventé,
    faux) : cette liste est une vérité constatée, pas une hypothèse — elle
    garde la reconnaissance d'expéditeur à l'abri d'une régression.

    Elle prouve aussi où N'EST PAS le problème : SeLoger Bureaux est bien
    identifié, donc ses alertes sont lues — si rien n'en sort, c'est le motif
    de LIEN qui est en cause, jamais l'expéditeur.
    """
    attendus = {
        "SeLoger Bureaux & Commerces <alertes@annonces.seloger-bureaux-commerces.com>": "seloger_bureaux",
        "SeLoger <annonces@alertes.seloger.com>": "seloger_bureaux",
        "Bien'ici <no_reply@bienici.com>": "bienici_alerte",
        "LogicImmo <annonces@alertes.logic-immo.com>": "logic_immo",
        "iad France <no-reply@notif.iadinternational.com>": "iad",
        "leboncoin <no.reply@leboncoin.fr>": "leboncoin",
    }
    for expediteur, portail_attendu in attendus.items():
        portail = identifier_portail(expediteur, "")
        assert portail is not None, f"expéditeur réel non reconnu : {expediteur}"
        assert portail.nom == portail_attendu, expediteur


def test_motif_lien_bienici_alerte_structure_reelle():
    portail = next(p for p in PORTAILS if p.nom == "bienici_alerte")
    href = "https://www.bienici.com/annonce/abc123def456"
    trouve = portail.motif_lien.search(href)
    assert trouve and trouve.group(1) == "abc123def456"


def test_echantillons_reels_2026_08_23_deja_couverts():
    # Les 4 adresses transférées par l'utilisateur le 2026-08-23 : 3 étaient
    # déjà reconnues avant tout changement de code (seloger en substring
    # large, pap.fr déjà ajouté), seul Bien'ici manquait.
    assert identifier_portail(
        "SeLoger Bureaux & Commerces <alertes@annonces.seloger-bureaux-commerces.com>", ""
    ).nom == "seloger_bureaux"
    assert identifier_portail("SeLoger <annonces@alertes.seloger.com>", "").nom == "seloger_bureaux"
    assert identifier_portail("PAP.fr <users-alertes@pap.fr>", "").nom == "pap"
    assert identifier_portail("Bien'ici <no_reply@bienici.com>", "").nom == "bienici_alerte"


def test_pap_ne_matche_pas_papcommerces():
    # pap.fr (alertes) est distinct de papcommerces.fr (déjà scrapé en direct,
    # source "papcommerces") : "pap.fr" n'est pas une sous-chaîne de
    # "papcommerces.fr" (le "." tombe après "commerces", pas après "pap").
    assert identifier_portail("contact@papcommerces.fr", "") is None


def test_motif_lien_bourse_des_locaux_id_hexadecimal():
    portail = next(p for p in PORTAILS if p.nom == "bourse_des_locaux")
    href = ("https://reprise-entreprise.bpifrance.fr/locaux/annonce-locaux/"
            "vente-de-murs-de-boutique-yvelines-78-86ec40815c14bec3a9e53a6091e37970")
    trouve = portail.motif_lien.search(href)
    assert trouve and trouve.group(1) == "86ec40815c14bec3a9e53a6091e37970"


# --- Diagnostic du 2026-08-29 : logic_immo/iad/bienici_alerte à 0 annonce ---
# malgré des mails réels non lus (cf. imap-alertes-diagnostic). curl -I sur un
# vrai lien a montré deux mécanismes distincts, testés ci-dessous.


def test_motif_lien_logic_immo_id_alphanumerique_reel():
    # Vrai lien résolu (curl -I, 2026-08-29) : l'ID n'est PAS numérique
    # (l'ancien motif \d{5,} ne l'aurait jamais reconnu).
    portail = next(p for p in PORTAILS if p.nom == "logic_immo")
    href = ("https://www.logic-immo.com/detail-annonce/vente/ile-de-france/paris-75/"
            "paris-75000/26JC84IUAZTN?utm_source=crm-b2c&utm_medium=email")
    trouve = portail.motif_lien.search(href)
    assert trouve and trouve.group(1) == "26JC84IUAZTN"


def test_motif_lien_bienici_alerte_slug_avec_tiret_reel():
    # Vrai slug décodé (base64, 2026-08-29) : contient un tiret, contrairement
    # au motif d'origine [a-z0-9] (jamais vérifié sur un vrai message).
    portail = next(p for p in PORTAILS if p.nom == "bienici_alerte")
    href = "https://www.bienici.com/annonce/immo-facile-61351792"
    trouve = portail.motif_lien.search(href)
    assert trouve and trouve.group(1) == "immo-facile-61351792"


def test_decoder_segment_base64_revele_l_url_bienici():
    reelle = "https://www.bienici.com/annonce/immo-facile-61351792?x=1"
    encode = base64.urlsafe_b64encode(reelle.encode()).decode().rstrip("=")
    href = f"https://link.bienici.com/lnk/AAA/8/token/{encode}"
    assert _decoder_segment_base64(href) == reelle


def test_decoder_segment_base64_renvoie_none_si_pas_du_base64():
    # Le "qs" de logic_immo n'est PAS l'URL réelle encodée (curl -I confirme
    # que le token est opaque, résolu seulement par une vraie redirection).
    href = "https://click.by.logic-immo.com/?qs=ABB7InYiOjEsImQiOjQ5ODN9AD"
    assert _decoder_segment_base64(href) is None


def test_extraction_bienici_via_base64_sans_reseau():
    # Bout en bout, sans mock réseau : le décodage base64 suffit.
    portail = next(p for p in PORTAILS if p.nom == "bienici_alerte")
    reelle = "https://www.bienici.com/annonce/immo-facile-61351792"
    encode = base64.urlsafe_b64encode(reelle.encode()).decode().rstrip("=")
    html = (
        "<html><body><div>"
        f'<a href="https://link.bienici.com/lnk/AAA/8/tok/{encode}">Voir</a>'
        "<p>Paris 75018 - 250 000 €</p>"
        "</div></body></html>"
    )
    annonces = extraire_annonces_html(html, portail)
    assert len(annonces) == 1
    assert annonces[0].id_source == "immo-facile-61351792"


def test_extraction_via_redirection_logic_immo_uniquement_dans_un_bloc_a_prix():
    portail = next(p for p in PORTAILS if p.nom == "logic_immo")
    appels: list[str] = []

    def resoudre_factice(href: str) -> str | None:
        appels.append(href)
        return ("https://www.logic-immo.com/detail-annonce/vente/ile-de-france/"
                 "paris-75/paris-75000/26JC84IUAZTN?utm_source=crm-b2c")

    html_avec_prix = (
        "<html><body><div>"
        '<a href="https://click.by.logic-immo.com/?qs=TOKEN1">Voir l\'annonce</a>'
        "<p>Local commercial Paris 75018 - 250 000 €</p>"
        "</div></body></html>"
    )
    annonces = extraire_annonces_html(html_avec_prix, portail, resoudre_redirection=resoudre_factice)
    assert len(appels) == 1
    assert len(annonces) == 1
    assert annonces[0].id_source == "26JC84IUAZTN"
    assert annonces[0].source == "alerte_logic_immo"

    # Un lien hors bloc à prix (logo, désabonnement...) partage le MÊME
    # redirecteur opaque — sans ce garde-fou, on cramerait le budget réseau
    # (SourceImap.max_redirections) sur du bruit plutôt que sur de vraies annonces.
    appels.clear()
    html_sans_prix = (
        "<html><body><div>"
        '<a href="https://click.by.logic-immo.com/?qs=LOGOTOKEN">Logo</a>'
        "</div></body></html>"
    )
    annonces_logo = extraire_annonces_html(html_sans_prix, portail, resoudre_redirection=resoudre_factice)
    assert appels == []
    assert annonces_logo == []


def test_bilan_budget_distingue_les_deux_plafonds():
    """« Budget épuisé » ne disait pas LEQUEL des deux plafonds avait mordu —
    or le remède diffère : plafond de TEMPS = serveurs lents (baisser le
    timeout), plafond de NOMBRE = liens rapides mais trop nombreux (relever le
    compteur). Question posée le 2026-09-05, sans réponse possible jusqu'ici."""
    lent = SourceImap(budget_redirection_s=240.0)
    lent.redirections_tentees, lent.redirections_reussies = 48, 31
    lent.redirections_echouees, lent.secondes_redirections = 17, 238.4
    lent.limite_atteinte = "temps"
    bilan = lent.bilan_budget()
    assert "48 liens" in bilan and "238 s sur 240 s" in bilan
    assert "5.0 s/lien" in bilan            # révèle des timeouts
    assert "plafond atteint : temps" in bilan

    rapide = SourceImap(budget_redirection_s=240.0)
    rapide.redirections_tentees, rapide.redirections_reussies = 400, 388
    rapide.redirections_echouees, rapide.secondes_redirections = 12, 121.7
    rapide.limite_atteinte = "nombre de liens"
    bilan = rapide.bilan_budget()
    assert "0.3 s/lien" in bilan            # serveurs rapides
    assert "plafond atteint : nombre de liens" in bilan


def test_limite_atteinte_nomme_le_plafond_du_nombre(monkeypatch):
    source = SourceImap(max_redirections=0)          # compteur à sec d'emblée
    assert source._resoudre_redirection("https://x") is None
    assert source.limite_atteinte == "nombre de liens"


def test_limite_atteinte_nomme_le_plafond_du_temps(monkeypatch):
    source = SourceImap(max_redirections=1000, budget_redirection_s=5.0)
    source._debut_redirections = 0.0                  # chrono déjà démarré
    monkeypatch.setattr("sources.imap_alertes.time.monotonic", lambda: 10.0)  # 10 s > 5 s
    assert source._resoudre_redirection("https://x") is None
    assert source.limite_atteinte == "temps"


def test_un_echec_compte_son_temps_car_c_est_le_cas_le_plus_cher(monkeypatch):
    """Un lien qui expire coûte le timeout ENTIER : l'ignorer dans le bilan
    ferait croire à un budget bien plus rapide qu'il ne l'est."""
    def leve(url, **kw):
        raise OSError("timeout")

    monkeypatch.setattr("sources.imap_alertes.requests.head", leve)
    horloge = iter([0.0, 100.0, 105.0])   # démarrage chrono, début appel, fin appel
    monkeypatch.setattr("sources.imap_alertes.time.monotonic", lambda: next(horloge))
    source = SourceImap()
    assert source._resoudre_redirection("https://x") is None
    assert source.redirections_echouees == 1
    assert source.secondes_redirections == 5.0


def test_garde_fou_budget_ecarte_les_liens_de_service():
    """Le garde-fou « ce lien est-il dans un bloc à PRIX ? » était inopérant.

    Un lien SANS prix voisin (logo, désabonnement, réseaux sociaux) fait
    remonter _bloc_annonce jusqu'à <body> — qui contient les prix des AUTRES
    annonces, et répondait donc vrai pour tout le monde. Mesuré le 2026-09-05
    sur un email type : 5 liens sur 5 passaient, alors que 2 seulement étaient
    des annonces. Le budget de redirection partait aux deux tiers en pure
    perte, d'où un retard qui grimpait au lieu de se résorber (35 -> 73
    messages reportés en cinq jours).
    """
    from bs4 import BeautifulSoup

    from sources.imap_alertes import _mene_a_une_annonce

    html = (
        "<html><body>"
        '<div><a href="https://click.tracker/?qs=LOGO">logo</a></div>'
        '<div><a href="https://click.tracker/?qs=A1">Annonce A</a><p>250 000 €</p></div>'
        '<div><a href="https://click.tracker/?qs=A2">Annonce B</a><p>310 000 €</p></div>'
        '<div><a href="https://click.tracker/?qs=DESABO">Se désabonner</a></div>'
        "</body></html>"
    )
    liens = BeautifulSoup(html, "html.parser").find_all("a", href=True)
    retenus = [str(a["href"]) for a in liens if _mene_a_une_annonce(a)]
    assert retenus == [
        "https://click.tracker/?qs=A1",
        "https://click.tracker/?qs=A2",
    ], "seuls les liens d'un VRAI bloc à prix doivent consommer du budget"


def test_identifiant_extrait_n_est_jamais_le_code_postal():
    """Un code postal français fait EXACTEMENT 5 chiffres, et les URLs immo le
    portent presque toujours dans leur slug, AVANT l'identifiant. Les motifs
    non gourmands `[^…]*?(\\d{5,})` retenaient donc le premier groupe trouvé —
    le code postal — au lieu de l'annonce.

    Conséquence, silencieuse et grave : id_source devenait le code postal, donc
    toutes les annonces d'un même secteur s'écrasaient les unes les autres
    (l'extraction déduplique par id_source). Un quartier entier se serait
    réduit à une seule annonce, sans erreur ni avertissement.
    """
    attendus = [
        ("seloger_bureaux",
         "https://www.seloger-bureaux-commerces.com/annonce/local-75018-987654321", "987654321"),
        ("pap",
         "https://www.pap.fr/annonce/locaux-commerciaux-paris-18e-75018-r123456789", "123456789"),
        ("avendrealouer",
         "https://www.avendrealouer.fr/local/paris-18-75018/vente-654321987.html", "654321987"),
    ]
    for nom, url, identifiant in attendus:
        portail = next(p for p in PORTAILS if p.nom == nom)
        trouve = portail.motif_lien.search(url)
        assert trouve is not None, f"{nom} ne reconnaît plus une URL valide"
        assert trouve.group(1) == identifiant, f"{nom} : code postal pris pour l'identifiant"


def test_deux_annonces_du_meme_code_postal_ne_s_ecrasent_pas():
    """Conséquence concrète du test précédent, bout en bout."""
    portail = next(p for p in PORTAILS if p.nom == "seloger_bureaux")
    html = (
        "<html><body>"
        '<div><a href="https://www.seloger.com/annonce/local-75018-111111111">A</a>'
        "<p>Local Paris 75018 - 250 000 €</p></div>"
        '<div><a href="https://www.seloger.com/annonce/local-75018-222222222">B</a>'
        "<p>Local Paris 75018 - 310 000 €</p></div>"
        "</body></html>"
    )
    annonces = extraire_annonces_html(html, portail)
    assert {a.id_source for a in annonces} == {"111111111", "222222222"}


def test_liens_opaques_resolus_pour_un_portail_non_marque_d_avance():
    """LE correctif du 2026-09-02. Auparavant la résolution n'était tentée que
    pour les portails cochés `via_redirection=True` — un drapeau qu'il fallait
    renseigner À L'AVANCE, donc après avoir disséqué un vrai message. Impasse
    exacte de seloger_bureaux : 10 alertes lues, 0 annonce, et aucun moyen de
    savoir pourquoi sans échantillon. Désormais l'essai est fait dès que le
    motif direct échoue : la question se tranche à l'exécution.

    Ce test reproduit le cas SeLoger : lien de tracking opaque, portail jamais
    marqué comme redirigé. Avant le correctif il rendait 0 annonce.
    """
    portail = next(p for p in PORTAILS if p.nom == "seloger_bureaux")
    appels: list[str] = []

    def resoudre_factice(href: str) -> str | None:
        appels.append(href)
        return "https://www.seloger.com/annonces/locaux-commerciaux/vente/paris-18/123456789.htm"

    html = (
        "<html><body><div>"
        '<a href="https://click.email.seloger.com/?qs=JETON_OPAQUE">Voir l\'annonce</a>'
        "<p>Local commercial Paris 75018 - 250 000 €</p>"
        "</div></body></html>"
    )
    annonces = extraire_annonces_html(html, portail, resoudre_redirection=resoudre_factice)
    assert appels == ["https://click.email.seloger.com/?qs=JETON_OPAQUE"]
    assert len(annonces) == 1
    assert annonces[0].id_source == "123456789"
    assert annonces[0].source == "alerte_seloger_bureaux"


def test_lien_direct_ne_declenche_aucune_resolution():
    """Contrepartie du test précédent : rendre la résolution universelle ne
    doit RIEN coûter aux portails à liens directs — leur motif matche, on
    n'atteint jamais l'appel réseau."""
    portail = next(p for p in PORTAILS if p.nom == "leboncoin")
    appels: list[str] = []

    html = (
        "<html><body><div>"
        '<a href="https://www.leboncoin.fr/ventes_immobilieres/2894561230.htm">Voir</a>'
        "<p>Local commercial Paris 75018 - 250 000 €</p>"
        "</div></body></html>"
    )
    annonces = extraire_annonces_html(
        html, portail, resoudre_redirection=lambda h: appels.append(h) or None
    )
    assert appels == []               # aucun aller-retour réseau gaspillé
    assert len(annonces) == 1


def test_extraction_sans_resoudre_redirection_ne_plante_pas():
    # Portail à liens opaques mais appelant qui ne fournit pas de résolveur
    # (ex. anciens tests, ou futur appelant) : dégrade proprement à 0 annonce.
    portail = next(p for p in PORTAILS if p.nom == "logic_immo")
    html = (
        "<html><body><div>"
        '<a href="https://click.by.logic-immo.com/?qs=TOKEN1">Voir</a>'
        "<p>250 000 €</p>"
        "</div></body></html>"
    )
    assert extraire_annonces_html(html, portail) == []


def test_resoudre_redirection_suit_le_302_et_respecte_le_budget(monkeypatch):
    appels: list[str] = []

    class _ReponseFactice:
        def __init__(self, statut: int, location: str | None = None) -> None:
            self.status_code = statut
            self.headers = {"Location": location} if location else {}

    def head_factice(url: str, **kwargs):
        appels.append(url)
        return _ReponseFactice(302, "https://www.logic-immo.com/detail-annonce/x/26JC84IUAZTN")

    monkeypatch.setattr("sources.imap_alertes.requests.head", head_factice)

    source = SourceImap(max_redirections=2)
    assert source._resoudre_redirection("https://click.by.logic-immo.com/?qs=A") == \
        "https://www.logic-immo.com/detail-annonce/x/26JC84IUAZTN"
    assert source._resoudre_redirection("https://click.by.logic-immo.com/?qs=B") == \
        "https://www.logic-immo.com/detail-annonce/x/26JC84IUAZTN"
    # Budget épuisé (2) : le 3e appel ne fait même plus de requête réseau.
    assert source._resoudre_redirection("https://click.by.logic-immo.com/?qs=C") is None
    assert len(appels) == 2


def test_resoudre_redirection_s_arrete_sur_le_budget_de_TEMPS(monkeypatch):
    """Le compteur seul devait être calibré sur le pire cas (tout en timeout),
    donc rester bas — d'où un retard qui s'accumulait (15 -> 37 emails reportés
    en 3 jours). Le budget en secondes borne le pire cas sans brider le cas
    normal : ici le compteur est large, c'est le chrono qui coupe."""
    appels: list[str] = []

    class _ReponseFactice:
        status_code = 302
        headers = {"Location": "https://www.logic-immo.com/detail-annonce/x/AB"}

    monkeypatch.setattr("sources.imap_alertes.requests.head",
                        lambda url, **kw: (appels.append(url), _ReponseFactice())[1])

    # Horloge pilotée à la main plutôt qu'une liste de valeurs : le code lit
    # monotonic() plusieurs fois par résolution (chrono + mesure), et compter
    # ces appels rendrait le test cassant au moindre ajout de mesure.
    horloge = {"t": 0.0}
    monkeypatch.setattr("sources.imap_alertes.time.monotonic", lambda: horloge["t"])

    source = SourceImap(max_redirections=1000, budget_redirection_s=5.0)
    assert source._resoudre_redirection("https://click.by.logic-immo.com/?qs=A") is not None
    horloge["t"] = 10.0                       # 10 s écoulées > budget de 5 s
    assert source._resoudre_redirection("https://click.by.logic-immo.com/?qs=B") is None
    assert len(appels) == 1              # le 2e n'a fait aucune requête réseau
    assert source.budget_epuise is True  # -> le message sera retenté au run suivant


def test_budget_de_temps_demarre_a_la_premiere_resolution(monkeypatch):
    """Le temps passé en lecture IMAP pure ne doit pas grignoter le budget
    réseau : le chrono ne démarre qu'au premier lien réellement résolu."""
    source = SourceImap(budget_redirection_s=5.0)
    assert source._debut_redirections is None
    monkeypatch.setattr("sources.imap_alertes.time.monotonic", lambda: 1000.0)
    assert source._temps_redirection_ecoule() is False  # démarre le chrono, ne coupe pas
    assert source._debut_redirections == 1000.0


def test_diagnostiquer_liens_revele_un_routeur_de_tracking():
    """Sans preuve, on ne peut pas savoir POURQUOI un motif ne matche pas.
    Ce diagnostic remonte les hôtes des liens situés dans un bloc à prix :
    un hôte de tracking au lieu du domaine du portail = liens opaques, donc
    via_redirection=True à activer. La preuve arrive ainsi toute seule, sans
    devoir se faire transférer un vrai message."""
    html = """<html><body>
      <div><a href="https://click.email.seloger.com/?qs=OPAQUE1">Voir</a><p>250 000 €</p></div>
      <div><a href="https://click.email.seloger.com/?qs=OPAQUE2">Voir</a><p>310 000 €</p></div>
      <div><a href="https://www.seloger.com/mentions-legales">Mentions</a></div>
    </body></html>"""
    hotes = SourceImap().diagnostiquer_liens(html)
    # Le lien hors bloc à prix (mentions légales) est ignoré : on ne veut que
    # les liens qui mènent PROBABLEMENT à une annonce.
    assert hotes == ["click.email.seloger.com ×2"]


def test_diagnostiquer_liens_vide_si_aucun_lien_a_prix():
    assert SourceImap().diagnostiquer_liens("<html><body>rien</body></html>") == []


def test_resoudre_redirection_renvoie_none_hors_redirection(monkeypatch):
    class _ReponseFactice:
        status_code = 200
        headers: dict = {}

    monkeypatch.setattr("sources.imap_alertes.requests.head", lambda url, **kw: _ReponseFactice())
    assert SourceImap()._resoudre_redirection("https://x") is None


def test_resoudre_redirection_jamais_bloquant_sur_erreur_reseau(monkeypatch):
    def leve(url: str, **kwargs):
        raise OSError("timeout")

    monkeypatch.setattr("sources.imap_alertes.requests.head", leve)
    assert SourceImap()._resoudre_redirection("https://x") is None


def test_collecter_remet_non_lu_si_le_budget_de_redirection_est_a_sec(monkeypatch):
    # Sans ça, un message dont l'annonce n'a pas pu être résolue faute de
    # budget reste marqué \Seen (fetch RFC822 le fait dès la lecture) et
    # l'annonce est perdue pour toujours, jamais retentée.
    monkeypatch.setenv("IMAP_USER", "test@exemple.fr")
    monkeypatch.setenv("IMAP_PASSWORD", "x")

    message = EmailMessage()
    message["From"] = "LogicImmo <annonces@alertes.logic-immo.com>"
    message["Subject"] = "1 nouvelle annonce : 75018"
    message.set_content(
        '<html><body><div><a href="https://click.by.logic-immo.com/?qs=TOKEN1">Voir</a>'
        "<p>250 000 €</p></div></body></html>",
        subtype="html",
    )

    class _BoiteFactice:
        def __init__(self) -> None:
            self.flags_retires: list[tuple] = []

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def login(self, *a, **kw):
            pass

        def list(self):
            return "OK", [b'(\\HasNoChildren \\All) "/" "[Gmail]/Tous les messages"']

        def select(self, *a, **kw):
            pass

        def search(self, charset, criteres):
            if "logic-immo.com" in criteres:
                return "OK", [b"1"]
            return "OK", [b""]

        def fetch(self, numero, quoi):
            return "OK", [(b"1 (RFC822 {...})", message.as_bytes())]

        def store(self, numero, drapeau, valeur):
            self.flags_retires.append((numero, drapeau, valeur))
            return "OK", [b""]

    boite = _BoiteFactice()
    monkeypatch.setattr("sources.imap_alertes.imaplib.IMAP4_SSL", lambda hote: boite)

    source = SourceImap(max_redirections=0)  # budget déjà à sec avant même le 1er lien
    resultat = source.collecter()

    assert resultat == []
    assert boite.flags_retires == [(b"1", "-FLAGS", "\\Seen")]
    # Distingué du "motif de lien à revoir" (cf. test suivant) : un budget à
    # sec n'a rien à voir avec un motif_lien caduc, ne doit jamais s'afficher
    # comme tel (constaté le 2026-08-29 sur le tout premier run réel — un
    # faux positif aurait fait chercher un bug inexistant dans la regex).
    assert not any("motif de lien" in a for a in source.avertissements)
    assert any("budget de redirection épuisé" in a for a in source.avertissements)


def test_collecter_signale_motif_a_revoir_seulement_hors_budget_epuise(monkeypatch):
    # Un lien réellement non reconnu (motif_lien caduc), budget dispo par
    # ailleurs : doit rester signalé comme "à revoir", pas comme un problème
    # de budget.
    monkeypatch.setenv("IMAP_USER", "test@exemple.fr")
    monkeypatch.setenv("IMAP_PASSWORD", "x")

    message = EmailMessage()
    message["From"] = "LogicImmo <annonces@alertes.logic-immo.com>"
    message["Subject"] = "1 nouvelle annonce : 75018"
    message.set_content(
        '<html><body><div><a href="https://click.by.logic-immo.com/?qs=TOKEN1">Voir</a>'
        "<p>250 000 €</p></div></body></html>",
        subtype="html",
    )

    class _BoiteFactice:
        def __init__(self) -> None:
            self.flags_retires: list[tuple] = []

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def login(self, *a, **kw):
            pass

        def list(self):
            return "OK", [b'(\\HasNoChildren \\All) "/" "[Gmail]/Tous les messages"']

        def select(self, *a, **kw):
            pass

        def search(self, charset, criteres):
            if "logic-immo.com" in criteres:
                return "OK", [b"1"]
            return "OK", [b""]

        def fetch(self, numero, quoi):
            return "OK", [(b"1 (RFC822 {...})", message.as_bytes())]

        def store(self, numero, drapeau, valeur):
            self.flags_retires.append((numero, drapeau, valeur))
            return "OK", [b""]

    boite = _BoiteFactice()
    monkeypatch.setattr("sources.imap_alertes.imaplib.IMAP4_SSL", lambda hote: boite)
    # Budget largement dispo, mais la redirection ne mène nulle part de
    # reconnaissable : un vrai échec de motif, pas un problème de budget.
    monkeypatch.setattr("sources.imap_alertes.requests.head",
                         lambda url, **kw: type("R", (), {"status_code": 200, "headers": {}})())

    source = SourceImap(max_redirections=20)
    resultat = source.collecter()

    assert resultat == []
    assert any("motif de lien" in a for a in source.avertissements)
    assert not any("budget de redirection épuisé" in a for a in source.avertissements)
    # Le message reste NON LU : un motif_lien caduc ne doit pas consommer
    # définitivement l'alerte qu'il n'a pas su lire (seloger_bureaux en perdait
    # 3 à 6 par jour). Une fois le motif corrigé, elle repasse toute seule.
    assert boite.flags_retires == [(b"1", "-FLAGS", "\\Seen")]


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


def test_extraire_message_portail_identifie_mais_aucun_lien_reconnu():
    # Cas suspecté sur logic_immo (motif_lien jamais vérifié sur un vrai
    # message, cf. imap-alertes-diagnostic) : si les liens passent par une
    # plateforme d'emailing avec des URLs de tracking opaques (aucune trace du
    # domaine du portail dedans), motif_lien ne matche rien. Ce cas doit rester
    # distinguable d'un message qui n'appartient à aucun portail connu — c'est
    # ce que `collecter()` utilise pour signaler un motif à corriger plutôt que
    # de rendre "0 annonce" indiscernable de "aucun mail reçu".
    message = EmailMessage()
    message["From"] = "LogicImmo <annonces@alertes.logic-immo.com>"
    message.set_content(
        "<html><body><a href='https://click.some-esp.example/t/abc123'>Voir l'annonce</a></body></html>",
        subtype="html",
    )
    portail, annonces = SourceImap().extraire_message(message)
    assert portail is not None and portail.nom == "logic_immo"
    assert annonces == []


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
