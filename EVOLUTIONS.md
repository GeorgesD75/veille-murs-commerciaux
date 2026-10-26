# Refonte de la recherche — 25 octobre 2026

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
