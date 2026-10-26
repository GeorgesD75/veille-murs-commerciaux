"""Pas de recommandation immobilière sur un fonds, un bail ou un extrait muet."""
from copy import deepcopy
from datetime import datetime

import pytest

from pipeline.comparables import LoyersComparables
from dashboard.generer import preparer_payload
from dashboard.dossier_banque import generer_dossiers
from pipeline.contact import messages_contact
from pipeline.dedoublonnage import sont_similaires
from pipeline.decision import est_pepite
from pipeline.fiabilite import diagnostiquer
from pipeline.filtres import raison_exclusion
from pipeline.modeles import Annonce, AnnonceBrute, TypeMurs
from pipeline.negociation import plan_negociation
from pipeline.normalisation import normaliser
from pipeline.notifications import notifier
from pipeline.scoring import scorer
from pipeline.transaction import qualifier_transaction
from run import integrer
from sources.bureauxlocaux import SourceBureauxLocaux
from sources.imap_alertes import PORTAILS, extraire_annonces_html
from tests.fabriques import faire_annonce


@pytest.mark.parametrize("titre,description", [
    ("Vente des murs", "Local de 30 m², hors fonds de commerce et hors droit au bail."),
    ("Murs commerciaux libres", "Sans fonds de commerce, vente immobilière."),
    ("Local commercial", "Ce sont les murs qui sont à vendre et qui sont libres."),
    ("Murs occupés", "Un fonds de commerce est exploité par le locataire."),
    ("Vente des murs d’un fonds de commerce", "Locataire en place."),
    ("Local commercial", "Nous proposons la pleine propriété des locaux."),
])
def test_achat_des_murs_explicite_et_negations_respectees(titre, description):
    a = faire_annonce(titre=titre, description=description)
    q = qualifier_transaction(a)
    assert q["nature"] == "murs"
    assert q["origine"] and q["extrait"]


@pytest.mark.parametrize("texte,nature", [
    ("Fonds de commerce restaurant", "fonds"),
    ("Fond de commerce de pharmacie", "fonds"),
    ("Vente du fonds, clientèle et matériel", "fonds"),
    ("FDC opticien à reprendre", "fonds"),
    ("Droit au bail boutique", "bail"),
    ("Cession de bail commercial", "bail"),
    ("DAB emplacement numéro 1", "bail"),
    ("MURS ET FOND COIFFURE ESTHETIQUE", "mixte"),
    ("Fonds de commerce avec murs", "mixte"),
    ("Murs & fonds restaurant", "mixte"),
    ("Murs commerciaux en option", "mixte"),
    ("Possibilité d’achat des murs", "mixte"),
    ("Fonds, murs non compris", "fonds"),
    ("Cession restaurant sans achat des murs", "fonds"),
    ("Location pure local commercial", "location"),
    ("Location-gérance restaurant", "location"),
])
def test_activite_bail_et_vente_groupee_ne_sont_pas_des_murs_seuls(texte, nature):
    a = faire_annonce(titre=texte, description="Emplacement commercial.")
    assert qualifier_transaction(a)["nature"] == nature
    assert diagnostiquer(a)["bloquant"]


@pytest.mark.parametrize("titre,description", [
    ("Photo annonce", "145 600 € Hôtel / Restaurant 30 m² Paris 9e."),
    ("Vente Boutique/Local commercial", "30 m². Bail 3/6/9. Loyer mensuel 1 500 €."),
    ("Prix de cession opticien", "Clientèle fidèle et stock inclus."),
    ("Local commercial", "Belle boutique, murs en pierre, plafond neuf."),
    ("Local commercial", "Murs d’angle repeints et cuisine équipée."),
])
def test_intitule_generique_bail_et_murs_architecturaux_ne_prouvent_rien(titre, description):
    a = faire_annonce(titre=titre, description=description)
    assert qualifier_transaction(a)["nature"] == "a_confirmer"
    assert diagnostiquer(a)["bloquant"]


def test_entete_et_adresse_email_ne_sont_pas_des_mentions_du_bien(config):
    a = faire_annonce(source="alerte_seloger_bureaux", titre="Votre alerte murs commerciaux",
                      description="Votre recherche : Vente > Murs commerciaux > Paris > Maximum 300 000 € "
                                  "145 600 € Hôtel / Restaurant 30 m² Paris 9e. "
                                  "Cet e-mail a été envoyé à test+lesmurs@example.test",
                      ville="Paris", code_postal="75009", departement="75",
                      rendement_brut_pct=9, position_benchmark="decote_forte")
    assert qualifier_transaction(a)["nature"] == "a_confirmer"
    scorer(a, config)
    assert a.score < config.scoring["seuils"]["affichage"]
    assert "texte_partiel_alerte" in a.flags
    assert not est_pepite(a, config)


def test_champ_propre_a_annonce_et_contradictions_conserves():
    a = faire_annonce(titre="Boutique", description="30 m².", nature_transaction_source="murs")
    assert qualifier_transaction(a)["nature"] == "murs"
    a.preuves["nature_transaction"] = [{"valeur": "fonds", "origine": "source:autre"}]
    assert qualifier_transaction(a)["nature"] == "a_confirmer"
    a.nature_transaction_source = "fonds"
    a.titre = "Vente des murs"
    assert qualifier_transaction(a)["nature"] == "fonds"


def test_preuve_structuree_fusionnee_sans_champ_direct():
    a = faire_annonce(titre="Boutique", description="30 m².")
    a.preuves["nature_transaction"] = [{"valeur": "murs", "origine": "source:autre", "url": a.url}]
    q = qualifier_transaction(a)
    assert q["nature"] == "murs" and q["extrait"] == "murs"


def test_preuve_d_une_autre_annonce_ne_prouve_pas_les_murs_de_cette_offre(config):
    a = faire_annonce(titre="Boutique", description="30 m².")
    a.preuves["nature_transaction"] = [{"valeur": "murs", "origine": "source:autre", "url": "https://autre.test/2"}]
    assert qualifier_transaction(a)["nature"] == "a_confirmer"
    murs = faire_annonce(id="autre", source="autre", url="https://autre.test/2")
    a.image_url = murs.image_url = "https://images.test/boutique.jpg"
    assert not sont_similaires(a, murs, config)


def test_api_boolean_false_est_distinct_de_champ_absent_et_preuve_persiste():
    source = SourceBureauxLocaux()
    item = {"id": "123", "url": "/annonce/boutique-123", "label": "Boutique", "city": "Paris",
            "zip_code": "75018", "sale_price": 250000, "total_surface": 30, "description": "Local commercial."}
    inconnue = source._depuis_item(item, "75")
    assert inconnue.nature_transaction_source is None
    item["characteristics_json"] = {"is_sale_of_business_assets": False}
    brute = source._depuis_item(item, "75")
    a = normaliser(brute, "2026-10-26T12:00:00+01:00")
    assert a.nature_transaction_source == "murs"
    assert a.preuves["nature_transaction"][0]["valeur"] == "murs"
    assert Annonce.from_dict(a.to_dict()).nature_transaction_source == "murs"
    assert qualifier_transaction(a)["nature"] == "murs"
    item["characteristics_json"]["is_sale_of_business_assets"] = True
    a = normaliser(source._depuis_item(item, "75"), "2026-10-26T12:00:00+01:00")
    assert qualifier_transaction(a)["nature"] == "fonds"


def test_prix_de_cession_non_immobilier_ne_profite_pas_d_une_case_generique():
    a = faire_annonce(titre="Opticien", description="Prix de cession 170 000 €, clientèle et stock.",
                      nature_transaction_source="murs")
    assert qualifier_transaction(a)["nature"] == "a_confirmer"


def test_description_plus_courte_et_changement_de_nature_actualisent_le_stock(config):
    def brute(**kw):
        base = dict(id_source="1", source="test", url="https://exemple.test/1", titre="Murs occupés",
                    ville="Pantin", code_postal="93500", type_murs=TypeMurs.MURS_OCCUPES,
                    prix=250000, surface_m2=100, description="Murs commerciaux. " + "Ancien texte. " * 50)
        base.update(kw)
        return AnnonceBrute(**base)
    stock = {}
    integrer([brute()], stock, config, "2026-10-25T12:00:00+01:00")
    a = next(iter(stock.values()))
    a.texte_detail, a.approfondie, a.etat_detail = "Vente des murs occupés", True, "lu"
    integrer([brute(titre="Cession du fonds", description="Fonds de commerce uniquement.",
                   nature_transaction_source="fonds")], stock, config, "2026-10-26T12:00:00+01:00")
    assert a.description == "Fonds de commerce uniquement."
    assert a.titre == "Cession du fonds" and not a.texte_detail
    assert not a.approfondie and a.nature_transaction_source == "fonds"
    assert qualifier_transaction(a)["nature"] == "fonds"


def test_fonds_ou_ambigu_ni_offre_ni_notification_ni_comparable(config, monkeypatch):
    a = faire_annonce(titre="Local commercial", description="Prix de cession opticien.",
                      score=95, date_derniere_vue="2026-10-26T12:00:00+01:00")
    assert not est_pepite(a, config)
    assert plan_negociation(a, config, datetime.fromisoformat(a.date_derniere_vue))["prix_plafond"] is None
    assert "pleine propriété" in messages_contact(a)["court"]
    assert not LoyersComparables.depuis([a, deepcopy(a)]).par_code_postal
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.delenv("EMAIL_TO", raising=False)
    rapport = notifier({a.id: a}, [a.id], {}, config)
    assert rapport["pepites"] == rapport["quotidien"] == 0


def test_un_dossier_ambigu_ne_recoit_ni_rang_ni_excel_et_ne_gonfle_pas_les_comparables(config, tmp_path):
    quand = datetime.fromisoformat("2026-10-26T12:00:00+01:00")
    murs = faire_annonce(id="murs", titre="Murs occupés", score=70, date_derniere_vue=quand.isoformat())
    inconnu = faire_annonce(id="inconnu", titre="Photo annonce", description="Local commercial 30 m².",
                           score=90, date_derniere_vue=quand.isoformat())
    stock = {a.id: a for a in [murs, inconnu]}
    p = preparer_payload(stock, {}, config, quand, dossiers={"inconnu": "ancien.xlsx"})
    par_id = {a["id"]: a for a in p["retenues"]}
    assert par_id["inconnu"]["rang_score"] is None and par_id["inconnu"]["dossier"] is None
    assert par_id["murs"]["rang_score"] == 1 and p["stats"]["retenues"] == 1
    assert par_id["murs"]["nb_comparables_secteur"] == 0
    assert set(generer_dossiers(stock, config, tmp_path)) == {"murs"}


def test_meme_prix_surface_et_photo_ne_fusionnent_pas_un_fonds_avec_des_murs(config):
    murs = faire_annonce()
    fonds = faire_annonce(titre="Fonds de commerce", description="Restaurant à reprendre.", source="autre")
    assert not sont_similaires(murs, fonds, config)


def test_bloc_email_global_ne_vole_pas_le_prix_et_la_nature_d_autres_annonces():
    portail = next(p for p in PORTAILS if p.nom == "leboncoin")
    html = ('<html><body><div><p>Murs commerciaux 250 000 €</p>'
            '<a href="https://www.leboncoin.fr/ventes_immobilieres/2894561230.htm">A</a>'
            '<a href="https://www.leboncoin.fr/ventes_immobilieres/2894561231.htm">B</a>'
            '</div></body></html>')
    assert extraire_annonces_html(html, portail) == []


def test_description_email_conserve_une_cession_mentionnee_apres_400_caracteres():
    portail = next(p for p in PORTAILS if p.nom == "leboncoin")
    texte = "Local très bien situé dans le quartier. " * 20 + "Cession du fonds de commerce."
    html = ('<div><a href="https://www.leboncoin.fr/ventes_immobilieres/2894561230.htm">Boutique</a>'
            '<p>250 000 € Paris 75018 ' + texte + '</p></div>')
    brute = extraire_annonces_html(html, portail)[0]
    assert len(brute.description) > 400
    assert qualifier_transaction(normaliser(brute, "2026-10-26T12:00:00+01:00"))["nature"] == "fonds"
