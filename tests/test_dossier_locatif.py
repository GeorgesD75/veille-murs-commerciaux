from datetime import datetime

import pytest

from pipeline.dossier_locatif import analyser_dossier
from pipeline.decision import analyser_relocation
from pipeline.enrichissement import enrichir
from pipeline.fiabilite import diagnostiquer
from pipeline.comparables import LoyersComparables
from tests.fabriques import faire_annonce


def test_surfaces_distinctes_et_vitrine_avec_source():
    a=faire_annonce(description="Surface totale 40 m² dont 25 m² au RDC et 15 m² en sous-sol. Vitrine de 4,5 m.",surface_m2=40)
    d=analyser_dossier(a)
    assert d["champs"]["rdc_m2"]["valeur"]==25
    assert d["champs"]["sous_sol_m2"]["valeur"]==15
    assert d["champs"]["vitrine_m"]["valeur"]==4.5
    assert d["champs"]["rdc_m2"]["preuves"][0]["url"]==a.url
    assert not d["sous_sol_majoritaire"]


def test_reserve_ne_devient_pas_surface_de_vente_et_pas_de_deduction():
    d=analyser_dossier(faire_annonce(description="Réserve de 15 m² et surface de vente : 20 m², total 40 m²."))
    assert d["champs"]["vente_m2"]["valeur"]==20
    assert d["champs"]["reserve_m2"]["valeur"]==15
    assert "rdc_m2" not in d["champs"]


def test_vitrine_en_m2_et_extraction_potentielle_ne_sont_pas_affirmees():
    d=analyser_dossier(faire_annonce(description="Vitrine de 5 m². Avec une extraction à créer sous réserve de la copropriété."))
    assert "vitrine_m" not in d["champs"]
    assert "extraction" not in d["champs"]


def test_restriction_prime_sur_tous_commerces_et_absence_extraction():
    d=analyser_dossier(faire_annonce(description="Tous commerces sauf restauration, sans extraction."))
    assert d["champs"]["activites"]["valeur"].startswith("Restauration exclue")
    assert d["champs"]["extraction"]["valeur"].startswith("Absente")


def test_contradiction_entre_liste_et_fiche_non_masquee():
    a=faire_annonce(description="RDC de 30 m². Taxe foncière : 1200 €.",texte_detail="RDC de 20 m². Taxe foncière : 2400 €.")
    d=analyser_dossier(a)
    assert d["champs"]["rdc_m2"]["statut"]=="contradictoire"
    assert d["champs"]["taxe_annuelle"]["valeur"] is None
    assert len(d["champs"]["taxe_annuelle"]["preuves"])==2
    a.dossier_locatif=d
    assert diagnostiquer(a)["bloquant"]


def test_taxe_mensuelle_convertie_et_charges_totales_pas_inventees(config,benchmarks):
    a=faire_annonce(description="Taxe foncière : 100 €/mois. Charges : 500 €/an.")
    enrichir(a,benchmarks,20)
    assert a.taxe_fonciere_annuelle==1200
    assert "charges_bailleur_annuelles" not in a.dossier_locatif["champs"]
    a.description="Charges du propriétaire : 60 €/mois, hors taxe foncière."
    assert analyser_dossier(a)["champs"]["charges_bailleur_annuelles"]["valeur"]==720


@pytest.mark.parametrize("texte,valeur",[("1.200",1200),("1.585",1585),("1.200,50",1200.5),("1 200",1200)])
def test_milliers_francais_et_extrait_centre_sur_le_montant(texte,valeur):
    description="Présentation du bien et du quartier "*20+f"Taxe foncière : {texte} €/an"
    champ=analyser_dossier(faire_annonce(description=description))["champs"]["taxe_annuelle"]
    assert champ["valeur"] == valeur
    assert "taxe fonciere" in champ["preuves"][0]["extrait"].lower()


@pytest.mark.parametrize("texte",["Taxe foncière de 990 € et charges mensuelles de 250 €",
                                 "Taxe foncière : 990 euros / charges mensuelles de copropriété : 87 euros"])
def test_periodicite_des_charges_ne_change_pas_celle_de_la_taxe(texte):
    assert analyser_dossier(faire_annonce(description=texte))["champs"]["taxe_annuelle"]["valeur"] == 990


def test_surface_sous_sol_majoritaire_suspend_la_relocation_favorable():
    a=faire_annonce(description="RDC de 10 m² et sous-sol de 25 m².",surface_m2=35,rue_categorie="commercante")
    r=analyser_relocation(a)
    assert r["niveau"]=="vigilance"
    assert any("sous-sol" in s for s in r["vigilances"])


def test_cache_ne_partage_pas_les_preuves_entre_annonces():
    a=faire_annonce(id="a",url="https://exemple.fr/a",description="RDC de 25 m².")
    b=faire_annonce(id="b",url="https://exemple.fr/b",description=a.description)
    d=analyser_dossier(a);d["champs"]["rdc_m2"]["preuves"][0]["url"]="modifie"
    assert analyser_dossier(b)["champs"]["rdc_m2"]["preuves"][0]["url"]==b.url


def test_comparaison_exclut_soi_meme_et_urls_dupliquees():
    maintenant=datetime.fromisoformat("2026-10-29T12:00:00+01:00")
    def annonce(id,url,loyer):
        return faire_annonce(id=id,url=url,titre="Murs occupés",description="Vente des murs occupés, locataire en place.",
            surface_m2=30,loyer_mensuel=loyer,date_derniere_vue=maintenant.isoformat())
    a=annonce("a","https://exemple.fr/a",3000)
    b=annonce("b","https://exemple.fr/b",1000)
    c=annonce("c","https://exemple.fr/c",1200)
    doublon=annonce("d","https://exemple.fr/b?utm=x",1000)
    autres=[a,b,c,doublon]
    r=LoyersComparables.depuis(autres,maintenant).diagnostic(a)
    assert r["nombre"]==2 and r["mediane_m2_an"]==440
    assert all(o["id"]!="a" for o in r["references"])
    assert not LoyersComparables.depuis([a,b],maintenant).diagnostic(a)["exploitable"]
