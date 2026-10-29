# Refonte de la recherche — 25 octobre 2026

## Qualification des biens et ordre d’étude (29 octobre)

- Score simulé directement visible dans « Prix à tenter en négociation »,
  calculé au prix de départ exact, avec rappel du score actuel. Le score du
  plafond reste distinct ; même repère visible dans l’étude de proposition.
- Extraction conservatrice du RDC, de la surface de vente, du sous-sol, de la
  réserve, de la vitrine, de l’extraction et des activités annoncées. Aucune
  surface de RDC déduite d’une soustraction. Extraits, origines et dates
  consultables dans les détails de relocation ; contradictions conservées.
- Taxe mensuelle convertie en montant annuel, séparateurs de milliers français
  préservés (`1.200 €` = 1 200 €) ; seules les charges explicitement
  attribuées au bailleur sont identifiées comme telles. Un conflit de taxe ou
  de charges suspend la simulation. Le sous-sol majoritaire et les contradictions
  de répartition deviennent des points de vigilance pour la relocation.
- Comparaison avec les loyers déclarés de murs occupés récents : même code
  postal, surfaces voisines, exclusion du bien et des URL dupliquées, au moins
  deux autres annonces, médiane et références datées. Ces déclarations ne
  prouvent ni le loyer de relocation, ni la demande locative.
- Lecture de détail priorisant les biens prometteurs et les informations utiles
  manquantes, en conservant la répartition entre sources et deux petites
  surfaces pour une opportunité plus grande. Relecture des dossiers incomplets
  après trois jours ; délais de refus et limites de collecte conservés.
- Géocodage migré vers le service Géoplateforme ; une adresse trouvée sur une
  fiche peut relancer une qualification auparavant impossible. Cache par voie
  et coordonnées, coordonnées des stations conservées dans la réponse OSM,
  un seul service public de secours sur panne Overpass. Aucun secours sur
  HTTP 403/429 et aucun comptage nul fabriqué depuis une réponse incomplète.
- Ordre des meilleures pistes explicite : retour vendeur favorable et relu,
  objectif atteint au prix demandé, puis négociation modérée ou exigeante.
  Le financement personnel et les risques restent pris en compte, les tris
  manuels restent disponibles. Les notes actuelles et hypothétiques ne changent
  pas ; un retour à négocier ne devient pas une pépite urgente.
- Dans Réponses, comparaison du précédent dossier relu avec le nouveau :
  verdict, cash-flow, limite financière et champs modifiés. Les deux scénarios
  utilisent le même financement courant. Les inconnues et risques suspendent
  la comparaison financière. Historique conservé sur l’appareil uniquement.
- Passe ciblée sans email : 24 fiches tentées, 20 lues, dont 16 annonçant des
  murs seuls ; trois refus respectés, une page de liste rejetée. Aucune nouvelle
  rue qualifiée pendant cette passe : les services OSM ont échoué. Les rues
  concernées restent à vérifier, sans précision inventée.
- Validation : 565 tests automatiques et parcours Chrome (classement,
  comparaison vendeur à financement identique, échappement des extraits,
  persistance et affichage de 320 à 1440 px).

## Prix personnel et suivi des démarches (27 octobre)

- Recherche du prix maximal compatible avec l’objectif mensuel et le financement
  personnel, sur une grille de 1 000 €. Prix demandé comme borne supérieure,
  apport fixe ou en pourcentage, taux nul et achat comptant pris en charge.
- Lorsque le plafond de référence ne suffit pas, affichage de cette limite,
  du cash-flow, du rendement et du repère d’équilibre ; ouverture directe du
  simulateur à ce prix. Seuil financier seul, score inchangé, pas de promotion
  en pépite sur cette seule base. Bornes de cohérence du prix conservées.
- « Suivre » directement sur les cartes, puis accès au dossier de suivi.
  Avancement, notes et date de prochaine action accessibles sans ouvrir la fiche.
- Rappels échus et du jour regroupés dans « À traiter », sans doublons ; dates
  calendaires locales, rappels suspendus pour les pistes abandonnées.
- Brouillon de relance ouvert directement pour une annonce contactée sans retour ;
  accès au dossier vendeur dès qu’une réponse est reçue. Statut jamais changé par
  la simple copie d’un message. Instantané conservé si le bien quitte le stock.
- Effort mensuel au prix demandé mis en couleur et revenus estimés signalés.
  Recherche vide récupérable en un clic. Navigation clavier du suivi conservée.
- Validation : 536 tests et parcours navigateur incluant prix personnel, taux nul,
  apport fixe, persistance des rappels/notes, relance et affichage 320–1440 px.

## Publication de la veille malgré une modification concurrente (27 octobre)

- Diagnostic des échecs des 26 et 27 octobre : collecte et contrôles réussis,
  mais conflit Git sur `docs/index.html` pendant la publication. Les trois
  tentatives de rebase répétaient le même conflit sans le résoudre.
- Publication extraite dans `scripts/publier_veille.py` : récupération du code
  distant, reconstruction hors ligne du HTML avec le stock collecté et le
  template courant, puis nouveaux tests, contrôle JavaScript et aperçu.
  Aucun push forcé. Un conflit sur le stock reste explicite, sans écrasement.
- Sauvegarde `data/` et `docs/` en artefact avant publication, conservée sept
  jours, pour récupérer une tournée même si les contrôles ou le push échouent.
- Mode manuel « collecter » désactivable : republication du stock sans réseau
  de collecte ni notifications, sans changer la date de dernière collecte.
- Demande explicite de build Pages après le push du bot : `GITHUB_TOKEN`
  ne déclenche pas automatiquement la construction d’un site publié par branche.
- Vérification : sept scénarios Git avec dépôt distant et clone superficiel,
  dont conflit HTML, code concurrent sans conflit HTML, deuxième push pendant
  les contrôles, refus des conflits de stock et arrêt sur validation en échec.
  Suite complète : 535 tests réussis.

## Une décision explicite sur chaque annonce (27 octobre)

- Encadré de décision avec motif et prochaine étape : contacter en vert,
  négocier en ambre, compléter ou lever un risque. Les pièces restent à vérifier.
- Lecture distincte du score : potentiel négocié, trésorerie avec le financement
  personnel, loyer estimé, occupation, disponibilité et risques de relocation.
  Le dossier vendeur relu prime sur les déclarations du stock.
- Trois chiffres regroupés : prix à tenter, cash-flow prudent à ce prix,
  rendement brut. Écart au prix demandé en euros et pourcentage ; une forte
  baisse nécessaire est signalée sans présumer l’accord du vendeur.
- Scénario dégradé visible au prix proposé et effort d’épargne annuel associé ;
  mêmes hypothèses et calculs que le budget et le simulateur. Appliqué aussi
  aux chiffres du vendeur et dans la fenêtre de proposition.
- Les anciennes propositions disparaissent pendant la relecture d’une réponse
  vendeur. Les métriques de l’annonce restent identifiées et le score inchangé.
- Sur mobile, photo et titre en tête, puis données et analyse sur toute la
  largeur. Chiffres plus lisibles, liens contrastés en mode sombre, filtres
  repliés et accès direct aux annonces conservés.
- Validation : 528 tests Python (dont sept scénarios JavaScript de décision),
  parcours navigateur complet, persistance des dossiers et vues 320–1440 px.

## Collecte élargie et qualification de la vente (27 octobre)

- Point de Vente : parcours des rubriques publiques lf9 (libres) et lf10
  (occupés), jusqu’à 12 pages chacune. La page SEO lf393 mélangeait locations,
  fonds et murs ; le libellé de chaque carte reste vérifié indépendamment.
- PAP : correction de g439 (Paris) vers g471 (Île-de-France), pagination
  réelle sur 10 pages maximum. CessionPME : jusqu’à 20 pages et identifiants
  reconnus malgré les slugs sans « boutique » ou sans code postal.
- Bien’ici : plafond porté de trois à cinq pages. Les autres sources restent
  actives ; aucune revendication de couverture exhaustive des portails.
- Pagination partagée : dédoublonnage, détection de boucle/page répétée,
  limites annoncées, erreurs partielles conservant les résultats déjà lus et
  refus des liens vers une autre origine. Compteurs de pages en rapport de santé.
- Lecture détaillée : jusqu’à 72 fiches / 480 secondes, répartition entre
  domaines et plafond de 18 par domaine. Priorité aux fiches encore non lues,
  récupération possible des adresses inconnues et soupçons fondés sur le prix.
- Anti-fonds : titres Hektor conservés tels qu’annoncés au lieu d’inventer
  « murs libres/occupés ». Les anciennes présentations synthétiques ne font
  plus preuve. Négations de vente, locations, murs-fonds et variantes de
  fonds/baux mieux reconnus ; titre de fiche conservé même dans un header.
- Descriptions gardées sur 6 000 caractères, détail sur 12 000 pour les
  clauses de cession tardives. Les recommandations d’autres annonces restent
  exclues du texte principal et les inconnues ne prouvent jamais les murs.
- Robots : correction du premier préfixe permissif de la stdlib ; règle la
  plus spécifique, jokers, groupes d’agents et ancre finale appliqués. Le moteur
  /produit.list de Point de Vente, interdit, n’est pas utilisé par le collecteur.
- Performance : code postal, surface et prix comparés avant l’analyse des
  textes au dédoublonnage. Les garde-fous de nature restent appliqués avant fusion.
- Passe complémentaire sans IMAP, IA ni notifications ; historique distinct
  de la tournée complète. Budget de workflow porté à 45 minutes pour la couverture accrue.
- Passe réelle du 27 octobre : 44 pages, 1 403 annonces récupérées (996 Point
  de Vente, 303 CessionPME, 104 PAP), 904 nouvelles fiches après dédoublonnage.
  Après filtres, 230 nouvelles annonces déclarant les murs, dont 71 < 40 m² ;
  les 28 autres nouvelles fiches retenues restent ambiguës et hors recommandations.
- Détail : 72 tentatives, 64 fiches lues (38 murs annoncés, 26 à confirmer),
  quatre refus, deux retraits et deux redirections de liste. Plafonds de temps
  et accès refusés respectés. Les déclarations ne valent pas actes vérifiés.
- Validation : 527 tests et parcours navigateur complet sur le stock élargi.

## Budget réel du projet et prise en compte du retour vendeur (27 octobre)

- Volet replié sous le prix cible : coût d’acquisition estimé, apport en euros,
  capital emprunté et mensualité. Ventilation du loyer entre vacance, charges et
  taxe, crédit et reste prudent ; rendement après provisions et frais d’achat.
- Scénario dégradé au prix étudié, avec le financement personnel : baisse du
  loyer de 10 %, au moins deux mois de vacance et effort d’épargne annuel.
  Travaux et frais de financement non chiffrés signalés séparément.
- Un même calcul de projection sert au cash-flow des cartes et au budget.
  Les chiffres de l’analyse détaillée et le filtre « prudent » utilisent aussi
  le profil personnel ; les repères du barème restent explicitement distincts.
- Les fiches et les lignes du suivi indiquent la présence d’un retour vendeur.
  Après validation, le dossier privé remplace l’ancien encart de prix cible
  avec le loyer, les charges et le prix reçus, sans modifier le stock publié.
- Recommandation locale suspendue tant que la réponse est à relire, incomplète,
  à négocier ou risquée. Un fonds ou risque confirmé rejoint les dossiers hors
  recommandations. Les dossiers intéressants conservent les critères du score
  source : la réponse ne crée pas artificiellement une pépite.
- Un retour déjà reçu coupe l’invitation au premier contact urgent. Les données
  et scores du stock restent inchangés ; aucune réponse privée n’est publiée.
- Vérifications : apports en pourcentage/fixes/comptant, taux zéro, frais inclus
  sans double comptage, inconnues, fonds confirmé, dossier négociable puis
  intéressant, données sources intactes et affichage de 320 à 1 440 px.

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
