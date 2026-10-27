# Refonte de la recherche — 25 octobre 2026

## Rendement à chaque prix proposé (27 octobre)

- Rendement brut annuel affiché avec le prix à tenter et le plafond sur les
  annonces, ainsi qu’à chacun des trois prix de la fenêtre de proposition.
- Dans « Réponses », recalcul avec le loyer retenu du vendeur au prix demandé
  et au prix cible. Formule explicitée : loyer annuel divisé par ce prix,
  avant frais, charges, financement et impôt ; absent si le revenu est inconnu.

## Prix de discussion et cash-flow au même prix (27 octobre)

- Sur les annonces, prix de départ et cash-flow correspondant affichés côte
  à côte, puis plafond du modèle et cash-flow à ce plafond. Les montants
  utilisent le financement personnel, y compris l’apport fixe en euros.
- La fenêtre de proposition compare prix demandé, prix à tenter et plafond,
  chacun avec son propre cash-flow. Les scores restent liés au prix simulé
  de référence, distinct du calcul de trésorerie personnel.
- Dans « Réponses », le prix maximal à obtenir affiche maintenant son
  cash-flow prudent et dégradé recalculés à ce prix, avec la baisse à obtenir.
  Les chiffres au prix demandé restent identifiés séparément.

## Premier contact léger et analyse des réponses vendeur (26 octobre)

- Premier message limité à cinq points : murs seuls/disponibilité, occupation
  et bail, loyer HT/HC, charges bailleur et taxe, paiements et impayés. Les
  pièces, diagnostics et restrictions détaillées restent dans la seconde étape.
- Nouvel onglet « Réponses », accessible aussi depuis une annonce ou la fenêtre
  de contact. Chaque réponse est associée à une annonce et conservée localement,
  avec un instantané si elle disparaît du stock. Export/import de sauvegardes.
- Réponses complémentaires consolidées sans perdre les informations déjà
  reçues ; corrections prises en compte et inconnues explicites invalidant les
  anciennes valeurs. Dix derniers échanges conservés et relances personnalisées
  sauvegardées tant que les questions restent pertinentes.
- Lecture déterministe du texte dans le navigateur : extraits conservés,
  périodes explicites, conversion annuel/mensuel, conflits à départager et
  champs corrigibles. Les questions citées ne deviennent pas des affirmations.
- Analyse après relecture : inconnues, nature de la vente, bail, impayés,
  cash-flow prudent/dégradé au profil personnel et seuil financier de discussion.
  Charges taxe comprise non comptées deux fois ; réserves de prudence conservées.
- Pas de feu vert sur un loyer estimé/TTC, une occupation libre ou inconnue,
  des impayés, une échéance problématique ou un signal de relocation à risque.
  Une relance courte propose jusqu’à trois questions sur les réponses manquantes.
- Les réponses privées ne sont pas envoyées à un serveur et ne remplacent pas
  le score de l’annonce. Chiffres vendeur déclaratifs, justificatifs à vérifier.
- Validation : 493 tests dont le moteur JavaScript (27 scénarios), parcours
  navigateur complets, sauvegarde/restauration et affichage de 320 à 1 440 px.

## Un prix d’achat explicite et une relocation à qualifier (26 octobre)

- Les annonces indiquent un prix maximal d’achat, le cash-flow prudent à ce
  prix, le score simulé et le score actuel, avec les hypothèses de financement.
  Objectif configurable fixé à +100 €/mois après provisions : un gain de
  quelques euros correspondait à l’équilibre, pas à une marge d’achat utile.
- Si le cash-flow cible est calculable mais les critères pépite ne sont pas
  réunis, affichage d’un « seuil financier seul », avec score simulé plafonné
  et bouton de simulation. Ce repère ne déclenche ni promotion ni alerte.
- Rendement élevé distingué selon le contexte : anomalie au prix observé
  toujours bloquante, hausse mécanique due à un prix proposé plus bas signalée
  dans la simulation. Loyer constant, origine du dossier contrôlée, planchers
  de prix et contrôle absolu de cohérence conservés ; score réel inchangé.
- Les potentiels négociés peuvent remonter dans la sélection si leur prix
  cible atteint aussi l’objectif au profil personnel. Sinon, l’écart est
  signalé sur la carte ; le simulateur permet de tester le financement.
  Plage de discussion élargie jusqu’à 35 % de baisse, explicitement affichée
  comme une baisse à obtenir, sans estimation de probabilité d’acceptation.
- Diagnostic de relocation distinct du score : signaux de rue favorables,
  inconnus ou de vigilance, avec motifs et vérifications. Le métro et la note
  d’une commune ne prouvent pas une demande locative. Les signaux défavorables
  empêchent la promotion et les alertes pépite, sans effacer le scénario financier.
- Sans loyer réel, occupation claire ou données cohérentes, aucun prix cible
  d’achat n’est inventé : le motif à résoudre apparaît directement sur la fiche.
- Messages vendeur complétés sur les activités autorisées, les restrictions,
  les travaux et les éléments justifiant un loyer/délai de relocation.
- Validation : tests des seuils de trésorerie, de la sélection négociée, des
  risques de relocation et des alertes, plus contrôles navigateur sur mobile.

## Financement cohérent et brouillons conservés (26 octobre)

- Même exploitation prudente pour le financement du score, l’analyse et les
  prix cibles : vacance et charges provisionnées, taxe foncière annoncée ou
  provision d’un mois de loyer si inconnue. Zéro déclaré reste distinct d’une
  donnée absente ; la provision ne remplace jamais la valeur vendeur en stock.
- La trésorerie visible sur les cartes suit désormais le profil personnel,
  comme le filtre de trésorerie positive, le comparateur et le simulateur.
  Le score et le prix plafond gardent leur financement de référence explicite.
- Simulateur : résultat prudent et dégradé mis en avant, détail du crédit
  repliable, loyer/taxe/vacance/charges ajustables sans modifier le stock.
  Passage direct du prix plafond à un essai avec son propre financement.
- Taux zéro pris en charge ; hypothèses invalides refusées. Le stress reste
  plus défavorable si la vacance prudente dépasse déjà deux mois par an.
- Brouillons enregistrés localement par annonce et étape, y compris la
  négociation. Réouverture, changement d’étape et rechargement préservent les
  textes ; retour au modèle limité à l’étape active, sans marquer un envoi.
- Validation : 478 tests Python et contrôles navigateur des calculs Python/JS,
  profils, brouillons et écrans de 320 à 1 440 px.

## Déplier les pépites à contacter en priorité (26 octobre)

- Analyse ouverte automatiquement pour les pépites détectées depuis moins de
  48 heures, sans alerte bloquante, tant que le premier contact reste à faire.
- Même règle pour le conseil de contact et le dépliage ; les scores simulés
  après négociation, annonces retirées ou abandonnées ne créent pas d'urgence.
- Le dépliage reste contrôlable manuellement. Les autres analyses restent fermées.

## Acheter les murs, sans confusion avec le fonds (26 octobre)

- Qualification commune de la transaction : murs, fonds, droit au bail, offre
  groupée, location ou nature à confirmer. Une catégorie « local commercial »,
  un bail et un type libre/occupé inféré ne prouvent plus la vente immobilière.
- Détection des prix de cession, FDC/DAB, murs en option ou non compris et des
  lots « murs et fonds ». Les mentions « hors fonds » et un fonds exploité par
  le locataire sont distingués d'une cession de l'activité elle-même.
- Les critères de recherche, l'adresse de réception et le pied d'un email ne
  comptent plus comme déclarations du vendeur. Les blocs globaux ou regroupant
  plusieurs annonces ne fournissent plus leur prix/nature à un lien individuel.
- Champs propres aux annonces BureauxLocaux et Point de Vente conservés avec
  provenance ; absence de booléen distincte de « false ». Une preuve structurée
  reste liée à l’URL de l’offre ; les contradictions restent bloquantes. Une
  annonce ambiguë ne récupère plus la preuve immobilière d’une autre offre
  par simple photo commune, même à prix/surface semblables.
- Dossiers ambigus hors recommandations, alertes, prix d'offre, comparables de
  loyers et exports bancaires. Ils restent consultables dans le volet à confirmer.
- Titres/descriptions rafraîchis même lorsqu'ils raccourcissent ; changement de
  nature déclenchant une nouvelle lecture de fiche. Un fonds et des murs ne se
  fusionnent plus sur leur seul prix/surface/secteur.
- Nettoyage du stock existant, sans suppression des annonces ni notification.
  Collecte ciblée bornée pour rafraîchir les déclarations des sources.
- Contrôle réel : 94 annonces reçues de trois sources, 10 nouvelles fiches,
  4 pages détaillées lues et 2 annonces retirées identifiées. Deux refus d’accès
  sont conservés comme tels, sans être interprétés comme une vente du bien.

## Un classement cohérent avec le score affiché (26 octobre)

- Les potentiels après négociation ne passent plus dans le groupe des scores
  élevés sur la seule base de leur simulation. Le tri par défaut classe les
  scores actuels décroissants, puis l’adéquation personnelle à égalité.
- Le badge du score indique « actuel /100 ». La ligne d’offre affiche
  explicitement le score simulé et le prix négocié nécessaire pour l’atteindre.
- Les potentiels restent visibles, y compris hors surface/trajet souhaités
  lorsque l’option est active, et accessibles via le filtre de négociation.
- Les occasions aux enchères suivent le classement classique sous un intitulé
  distinct, leur score d’intérêt n’étant pas comparable au score économique.

## Un bouton visible pour les filtres (26 octobre)

- Déclencheur présenté comme un bouton vert avec une icône de réglages dorée,
  un chevron et un état ouvert distinct. Rappel des critères placé à côté.
- Ouverture native au clic et au clavier conservée ; réglages repliés au départ.

## Retrouver l’identité de l’enseigne (26 octobre)

- Retour du header vert profond, du filet et du soulignement dorés, du logo
  plus généreux et du store de devanture. Typographie de caractère pour les
  onglets et les titres de section.
- Hauteur contenue sur ordinateur et mobile : filtres toujours repliés et
  premières annonces au premier écran. L’introduction et les compteurs restent
  retirés ; les informations de collecte restent accessibles en pied de page.

## Prix cible pour une pépite à négocier (26 octobre)

- Nouveau calcul de négociation : recherche du prix maximal sur une grille de
  1 000 € qui satisfait le barème pépite existant ET une trésorerie prudente
  positive ou nulle. Le revenu reste constant ; le score, le rendement, le prix
  au m², la décote et le financement sont recalculés sur des copies indépendantes.
- Les contrôles d’anomalies restent actifs : pas de baisse infinie pour fabriquer
  une pépite. Annonce récente, occupation claire et loyer déclaré non estimé
  exigés ; contradictions et risques non clarifiés suspendent la proposition.
- Taxe foncière inconnue : provision annuelle d’un mois de loyer, signalée comme
  hypothèse et remplaçable par le montant réel. Honoraires séparés renseignés
  intégrés au financement et aux scénarios, y compris au simulateur personnel.
- Prix plafond, point de départ de discussion (marge de 3 % si les contrôles
  restent satisfaits), score simulé, effort d’apport, trésorerie et scénario
  dégradé accessibles dans une fenêtre dédiée. Le score réel reste affiché.
- Potentiels demandant au plus 25 % de baisse promus dans la sélection, y compris
  hors surface/trajet souhaités si l’option est active. Au-delà, le scénario reste
  consultable dans la recherche élargie, sans promotion. Un écart de prix n’est
  jamais présenté comme une probabilité d’acceptation du vendeur.
- Brouillon chiffré à personnaliser, sans envoi automatique. Demande de validation
  du bail, loyers, charges, travaux, honoraires et TVA avant de se positionner.
  Références Service Public sur charges commerciales et offre d’achat dans l’aide.
- Suppression des anciennes consignes de négociation forfaitaire de 7 % et des
  affirmations « jouable » : une seule méthode chiffrée pour les repères d’offre.
- Médiane exacte du référentiel conservée pour les contre-simulations et la jauge
  de marché ; elle n’est plus assimilée au milieu de la fourchette.

## Pépites au-delà des préférences (26 octobre)

- Moins de 40 m² reste la recherche principale ; une option active par défaut
  laisse passer les pépites plus grandes ou au-delà du trajet souhaité.
  Le texte recherché, le secteur, le type, les seuils et les autres filtres
  restent appliqués. Le budget et la zone de collecte restent inchangés.
- Le signal exige le seuil pépite existant, un revenu déclaré non estimé,
  une occupation explicite, des chiffres renseignés et sans contradiction,
  ainsi qu'une observation dans les 14 derniers jours. Il ne certifie pas
  les documents du vendeur. Aucun seuil économique abaissé.
- Les pépites remontent dans le tri par critères personnels. Un badge discret
  et la surface/le trajet dépassés expliquent leur présence sur la fiche.
  L'option de filtre strict est mémorisée sur l'appareil.
- Lecture détaillée : alternance de deux petites surfaces et d'une annonce
  prometteuse hors surface cible, dans les mêmes budgets de temps/requêtes.
  Un revenu déclaré intéressant peut ouvrir cette exploration avant le score ;
  cela ne qualifie pas encore une pépite.
- Tests des exceptions, limites strictes, fiches anciennes, loyers estimés,
  contradictions, masquage manuel, persistance et affichage mobile. Les exemples
  synthétiques restent en mémoire des tests, sans ajout au stock publié.

## Présentation épurée (26 octobre)

- Suppression du bloc d'introduction, des compteurs et des raccourcis en haut
  de page : les meilleures annonces arrivent directement après la navigation.
- Filtres repliés par défaut avec un rappel discret de la surface et du trajet.
- Fiches allégées : chiffres essentiels, contact et financement ; analyse et
  actions complémentaires accessibles à la demande.
- État de collecte et informations techniques déplacés dans le pied de page,
  sous « À propos de la veille ».
- Contrôle du premier écran sur ordinateur et mobile, des panneaux repliables,
  des interactions et de l'absence de débordement horizontal.

## Deuxième passe (25–26 octobre) : collecte, qualité et démarches

- Collecte régulière élargie : 5 pages Point de Vente, 8 pages par département
  sur BureauxLocaux, jusqu'à 3 pages de 100 annonces sur Bien’ici, budget
  Geolocaux de 110 requêtes avec rotation des communes secondaires ; 24 fiches
  détaillées maximum par tournée (180 secondes). Délai poli maintenu.
- Exploration dès 50 000 € uniquement pour les surfaces connues de moins de
  40 m² ; plafond existant inchangé. Il s'agit d'un filtre de découverte.
- Lecture JSON-LD de la fiche courante : prix, surface avec unité explicite,
  code postal et photos ; origines datées et contradictions conservées.
  Une page de résultats obtenue à la place d'une fiche est rejetée.
- Contrôle réel sur trois sources : 306 annonces collectées lors de la passe
  élargie ; deux nouvelles fiches ajoutées pendant la première passe. Ce
  volume compte les sources séparément et ne désigne pas 306 nouveaux biens.
- Nettoyage du stock : 33 fiches provenant de pages de résultats identifiées,
  21 loyers retirés ou corrigés ; leurs anciens textes et critiques sont retirés.
  Trois fiches supplémentaires ont été nettoyées après intégration de la
  tournée nocturne (36 au total). 46 loyers reconstitués depuis un rendement
  d'agence sont désormais marqués estimés, y compris sur des murs occupés.
  Une fiche Orpi renvoyant HTTP 410 est signalée indisponible. Les refus 403
  restent des refus d'accès, sans être assimilés à une vente.
- Scoring : contradictions fortes plafonnées sous le seuil de recommandation,
  occupation incertaine incompatible avec une alerte pépite. Simulation
  suspendue si les chiffres se contredisent. Aucun rendement ancien conservé
  lorsqu'un revenu disparaît. Fusion de doublons avec corroboration (liens,
  photo commune ou description substantielle), au-delà du prix/surface/CP.
- Scénario dégradé explicite : loyer −10 %, deux mois sans revenu, charges
  provisionnées ; effort annuel, rendement après provisions et couverture
  du crédit. Ces chiffres restent des simulations avant impôt et assurance.
- Contact en trois étapes : premier message, demande de pièces, relance.
  Messages adaptés au local libre/occupé/incertain, sans affirmer une valeur
  de marché ou une disponibilité personnelle. Aucun envoi automatique.
  Les modèles partagés évitent de répéter des milliers de longs messages
  dans le HTML ; une édition manuelle n'est pas écrasée sans confirmation.
- Recherche textuelle, filtres de baisse de prix, de cohérence et de trésorerie
  prudente, raccourcis et espace distinct pour les chiffres à vérifier.
- Résolution des chaînes d'alertes avec limite de quatre sauts et cache par
  tournée. Sauvegarde du stock par remplacement atomique : un échec d'écriture
  ne détruit pas le fichier précédent.

Outils complémentaires (sans lecture IMAP ni notifications) :

```powershell
python scripts/actualiser_ciblee.py --pages 3 --details 16
python scripts/nettoyer_fiches.py
```

La réparation des redirections d'alertes est testée sans accès à la boîte email.
Les sites refusant la collecte ou ne fournissant pas de fiche exploitable
restent signalés ; aucune couverture exhaustive ni disponibilité n'est garantie.

## Première passe

- Vue initiale sur les surfaces strictement inférieures à 40 m². Proximité depuis
  le domicile déjà configuré, rue Francoeur, Paris 18e. Temps de trajet indicatifs.
  Tous les biens restent accessibles en retirant les filtres.
- Deux notes distinctes : qualité économique existante /100 et adéquation /100
  (surface /40, trajet /30, économie /30). Les préférences ne rendent pas une
  mauvaise opération rentable. Tri personnalisable, filtres mémorisés.
- Scénario prudent : frais d'achat 8 %, financement de référence 20 % d'apport,
  durée/taux configurés ; provisions de vacance 8 % et charges 10 % du loyer,
  taxe foncière connue déduite. Avant impôt, assurance emprunteur et travaux
  exceptionnels. Hypothèses modifiables dans `recherche` de `config.yaml`.
  Le prix d'équilibre simulé n'est ni une valeur de marché ni un conseil d'offre.
- Questions de qualification et complétude de cinq champs : aucun document
  (bail, quittance, comptabilité) n'est vérifié automatiquement.
- Comparables locatifs : loyers déclaratifs de locaux occupés de même code
  postal, surface comprise entre la moitié et le double, au moins deux annonces
  revues dans les 30 jours. Repli au benchmark si l'échantillon ne suffit pas.
  Aucun loyer estimé ne suffit désormais à déclencher une alerte pépite.
- Suppression du bonus attribué à la simple mention de l'article 606 et correction
  de la checklist : [règles officielles sur les charges du bail commercial](https://entreprendre.service-public.gouv.fr/vosdroits/F32336).
- Collecte : petites surfaces prioritaires à approfondir ; communes proches
  prioritaires sur Geolocaux ; recommandations exclues du texte de détail ;
  conservation du stock si une page suivante devient illisible ; prix absent
  préservé, surface corrigée rafraîchie. Robots/5xx/429 : pause par hôte jusqu'à
  la prochaine tournée, sans marquer une indisponibilité temporaire comme définitive.
  Référence : [RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html).
- État de la collecte visible, archives non revues depuis 14 jours masquées par
  défaut, distinction entre date de génération et date de dernière collecte.
  Les sources en panne ou partielles ne sont pas réparées par la refonte seule :
  les diagnostics sont affichés. Aucun contournement de blocage.
- Responsive et navigation clavier ; financement/fiscalité repliés pour alléger
  la lecture. Les suivis existants et leurs identifiants sont conservés.

## Vérifier

```powershell
python -m pytest -q
python scripts/regenerer_dashboard.py
python scripts/verifier_interactions.py  # optionnel : Playwright + Chrome installé
```

La régénération est hors ligne : elle ne lit pas les emails, n'envoie aucune
notification et ne change pas la date de dernière collecte. Elle réutilise les
dossiers Excel existants. Le prochain run normal recalculera et persistera le
stock et régénérera les dossiers avec les nouvelles règles.
