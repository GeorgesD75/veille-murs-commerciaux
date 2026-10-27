"""Pagination réelle et contrôle de l'objet vendu, sans réseau en CI."""
from pathlib import Path

import pytest

from pipeline.approfondissement import approfondir_annonces, texte_de_page, est_page_de_liste
from pipeline.normalisation import normaliser
from pipeline.transaction import qualifier_transaction
from pipeline.dedoublonnage import sont_similaires
from pipeline.config import Config
from sources.cessionpme import SourceCessionPme
from sources.hektor import SourceFlagship
from sources.http import SourceBloqueeErreur
from sources.papcommerces import SourcePapCommerces
from sources.pointdevente import SourcePointDeVente
from sources.bienici import SourceBienici
from tests.fabriques import faire_annonce
from tests.test_approfondissement import ClientFactice, _config

FIXTURES = Path(__file__).parent / "fixtures"


class Pages:
    def __init__(self, reponses):
        self.reponses, self.urls = reponses, []

    def obtenir(self, url):
        self.urls.append(url)
        reponse = self.reponses[len(self.urls)-1]
        if isinstance(reponse, Exception):
            raise reponse
        return reponse


def carte(ref):
    return f'''<article class="annonce-card"><a class="annonce-card__link"
      href="/annonce,immo-entreprise-vente-local-commercial-paris-18e-75018,{ref},A,offre.html">Voir</a>
      <h2 class="annonce-card__title">Murs occupés</h2>
      <span class="annonce-card__price__value">200 000 €</span>
      <p class="annonce-card__description">Local de 30 m².</p></article>'''


def test_pagination_cessionpme_suit_le_lien_reel_et_dedoublonne():
    c=Pages([carte(1)+'<div class="pagination"><a href="?page=2">&gt;</a></div>',carte(1)+carte(2)])
    s=SourceCessionPme(client=c,max_pages=5)
    assert [a.id_source for a in s.collecter()]==['1','2']
    assert c.urls[1].endswith('?page=2')
    assert s.rapport_collecte=={'pages_lues':2,'annonces_uniques':2,'fin':'fin_listing'}


def test_pagination_vide_continue_et_boucle_ou_lien_externe_sarrete():
    for suivant in ['?page=2','https://autre.test/voler']:
        c=Pages(['<a rel="next" href="?page=2">Suivante</a>',carte(2)+f'<a rel="next" href="{suivant}">Suite</a>'])
        s=SourceCessionPme(client=c,max_pages=8)
        assert len(s.collecter())==1
        assert len(c.urls)==2
        assert s.rapport_collecte['fin']=='lien_invalide_ou_boucle'


def test_pagination_repetee_et_page_refusee_ne_font_pas_perdre_le_debut():
    page=carte(1)+'<a rel="next" href="?page=2">Suite</a>'
    for suite,fin in [(page,'page_repetee'),(SourceBloqueeErreur('HTTP 403'),'interrompue')]:
        c=Pages([page,suite]);s=SourceCessionPme(client=c,max_pages=8)
        assert len(s.collecter())==1
        assert s.rapport_collecte['fin']==fin and len(c.urls)==2


def test_limite_pages_annoncee_et_region_pap_reellement_idf():
    c=Pages(['<a rel="next" href="?page=2">Suivante</a>'])
    s=SourcePapCommerces(client=c,max_pages=1)
    assert s.collecter()==[]
    assert 'g471' in c.urls[0] and 'g439' not in c.urls[0]
    assert s.rapport_collecte['fin']=='limite_pages' and s.avertissements


def test_pointdevente_emploie_les_deux_rubriques_publiques_de_murs():
    h=(FIXTURES/'pointdevente_liste.html').read_text(encoding='utf-8')
    c=Pages([h,h])
    s=SourcePointDeVente(client=c,max_pages=2)
    assert len(s.collecter())==2
    assert c.urls[0].endswith('/murs-de-boutique-libres/murs-de-boutique/lf9')
    assert c.urls[1].endswith('/murs-de-boutique-occupes/murs-de-boutique/lf10')
    assert all('/produit.list' not in u for u in c.urls)
    assert s.rapport_collecte['pages_lues']==2


def test_slugs_cessionpme_sans_boutique_et_sans_code_postal_conservent_la_fiche():
    s=SourceCessionPme()
    a=s.extraire(carte(12))[0]
    assert a.code_postal=='75018' and a.ville=='Paris 18e'
    a=s.extraire(carte(13).replace('local-commercial-paris-18e-75018','locaux-commerciaux-louas-100'))[0]
    assert a.id_source=='13' and a.code_postal=='' # aucune adresse inventée


def test_hektor_ne_fabrique_pas_une_vente_des_murs():
    h=(FIXTURES/'hektor_vente.html').read_text(encoding='utf-8').replace('vente Murs - commerce','vente - commerce')
    a=next(a for a in SourceFlagship().extraire(h,None) if a.id_source=='uh1-9001')
    assert a.nature_transaction_source is None
    assert qualifier_transaction(normaliser(a,'2026-10-27T12:00:00+01:00'))['nature']=='a_confirmer'
    ancien=faire_annonce(source='iburoshop',titre='Murs occupés – Paris',description='Local vendu occupé avec un bail en place.')
    assert qualifier_transaction(ancien)['nature']=='a_confirmer'


@pytest.mark.parametrize('texte',[
    'Les murs ne sont pas vendus.', 'Le propriétaire ne vend pas les murs.',
    'Ce n’est pas une vente des murs.', 'Les murs ne seront pas compris dans la vente.',
])
def test_negation_de_vente_des_murs_prime_sur_un_titre_commercial(texte):
    a=faire_annonce(titre='Vente murs commerciaux',description=texte)
    assert qualifier_transaction(a)['nature']=='fonds'


def test_murs_a_louer_ne_sont_pas_des_murs_a_acheter():
    a=faire_annonce(titre='Murs commerciaux à louer',description='Local commercial de 30 m².')
    assert qualifier_transaction(a)['nature']=='location'


@pytest.mark.parametrize('titre,nature',[
    ('Vente murs-fonds restaurant','mixte'),('Murs / fonds pharmacie','mixte'),
    ('Fonds de restaurant à vendre','fonds'),('Fonds bar à reprendre','fonds'),
    ('Cession de contrat de bail','bail'),('Vente de bail commercial','bail'),
    ('Murs commerciaux et fonds de commerce','mixte'),('Vente des murs et du fonds de commerce','mixte'),
    ('Murs occupés - fonds de commerce','mixte'),
])
def test_variantes_de_fonds_et_baux_non_immobiliers(titre,nature):
    assert qualifier_transaction(faire_annonce(titre=titre,description='Local de 30 m².'))['nature']==nature


def test_titre_de_fiche_dans_header_est_conserve_pour_detecter_le_fonds(monkeypatch):
    h='<header><h1>Fonds de commerce</h1></header><main><p>'+('Boutique en activité. '*9)+'</p></main>'
    assert 'Fonds de commerce' in texte_de_page(h)
    c=ClientFactice(reponses={'https://exemple.fr/1':h})
    monkeypatch.setattr('pipeline.approfondissement.ClientPoli',lambda:c)
    a=faire_annonce(url='https://exemple.fr/1',titre='Boutique',description='Local de 30 m².')
    rapport=approfondir_annonces({'a':a},_config())
    assert qualifier_transaction(a)['nature']=='fonds'
    assert rapport['natures_apres_lecture']=={'fonds':1}


def test_lecture_repartie_et_adresse_inconnue_recuperable(monkeypatch):
    c=ClientFactice();monkeypatch.setattr('pipeline.approfondissement.ClientPoli',lambda:c)
    cfg=_config(max_par_run=4)
    cfg.donnees['analyse']['approfondissement'].update(repartir_sources=True,max_par_hote=2)
    annonces={str(i):faire_annonce(id=str(i),url=f'https://a.test/{i}',surface_m2=25,score=80) for i in range(5)}
    annonces['autre']=faire_annonce(id='autre',url='https://b.test/1',surface_m2=25,score=50)
    annonces['inconnu']=faire_annonce(id='inconnu',url='https://c.test/1',surface_m2=25,score=30,
        exclue=True,raison_exclusion='hors Île-de-France (département inconnu)')
    r=approfondir_annonces(annonces,cfg)
    assert c.urls[:3]==['https://a.test/0','https://b.test/1','https://c.test/1']
    assert r['par_hote']['a.test']==2 and r['tentees']==4


def test_clause_de_fonds_apres_deux_mille_caracteres_nest_pas_tronquee():
    description='Murs commerciaux. '+('Description détaillée de la boutique. '*75)+' Cession du fonds de commerce.'
    brute=SourceBienici().convertir({'realEstateAds':[{'id':'longue','adType':'buy','price':200000,
        'description':description,'title':'Local commercial','city':'Paris','postalCode':'75018'}]})[0]
    assert 'Cession du fonds' in brute.description
    assert qualifier_transaction(normaliser(brute,'2026-10-27T12:00:00+01:00'))['nature']=='mixte'


@pytest.mark.parametrize('champs',[{'code_postal':'75009'},{'surface_m2':800},{'prix':900000}])
def test_dedup_ne_relit_pas_les_textes_de_biens_incompatibles(monkeypatch,champs):
    def inutile(_):
        raise AssertionError('Analyse de texte inutile pour cette paire')
    monkeypatch.setattr('pipeline.dedoublonnage.qualifier_transaction',inutile)
    a=faire_annonce();b=faire_annonce(**champs)
    assert not sont_similaires(a,b,Config.charger())


def test_fiche_redirigee_vers_une_liste_ne_prouve_pas_la_nature_du_bien():
    h='<link rel="canonical" href="/annonces,vente-immobilier-entreprise,offres.html"><main><h1>Murs commerciaux</h1></main>'
    assert est_page_de_liste(h,'https://exemple.fr/annonce,ancien-bien,1,A,offre.html')
    assert not est_page_de_liste(h.replace('/annonces,vente-immobilier-entreprise,offres.html','/annonce,ancien-bien,1,A,offre.html'),
                               'https://exemple.fr/annonce,ancien-bien,1,A,offre.html')
