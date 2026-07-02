# Veille murs commerciaux — Paris & Île-de-France

Système automatisé de veille d'annonces de **murs de locaux commerciaux** (murs occupés en
priorité) pour un investisseur particulier basé à Paris 18e. Budget 150 000 – 400 000 €,
objectif : bail commercial 3/6/9, gestion minimale.

Fonctionnement cible : un run quotidien via GitHub Actions collecte les annonces, les filtre,
les score, met à jour un dashboard GitHub Pages et envoie un email s'il y a du nouveau.
**Aucun serveur à gérer.**

## Avancement par phases

- [x] **Phase 1** — structure, pipeline (normalisation → filtres → dédoublonnage →
  enrichissement → scoring), tests sur données mockées
- [x] **Phase 2** — parsers Niveau 1 : pointdevente.fr, murscommerciaux.com,
  iburoshop.fr, flagship.fr (century21.fr écarté : robots.txt restrictif, couvert
  via les alertes email en Phase 4)
- [ ] **Phase 3** — dashboard GitHub Pages
- [ ] **Phase 4** — module IMAP (alertes email des portails) + notifications Resend
- [ ] **Phase 5** — workflow GitHub Actions + README complet pas-à-pas

## Démarrage rapide (développement)

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m pytest          # tests
.venv\Scripts\python run.py             # run complet sur la source mock
```

## Structure

```
run.py                 Point d'entrée : collecte → pipeline → stockage
config.yaml            Tous les paramètres (budget, scoring, sources…) modifiables à la main
sources/               1 fichier = 1 source, interface commune (sources/base.py)
pipeline/              Normalisation, filtres, dédoublonnage, enrichissement, scoring, stockage
data/benchmarks.json   Fourchettes de prix/m² et loyers médians par département — à affiner à la main
data/trajets.json      Temps de trajet approximatifs depuis Paris 18e — à affiner à la main
data/annonces.json     Mémoire du collecteur (générée, versionnée dans git pour le dédoublonnage)
tests/                 Tests unitaires (pytest)
```

## Choix documentés

- **Stockage JSON versionné plutôt que SQLite** : les diffs restent lisibles dans git à chaque
  run (on voit les annonces apparaître/disparaître), pas de fichier binaire committé. L'accès
  est isolé dans `pipeline/stockage.py` si l'on veut migrer plus tard.
- **Temps de trajet : table statique** (`data/trajets.json`). Recherche par commune, sinon
  valeur par défaut du département. C'est approximatif mais suffisant pour un filtre à 1h,
  gratuit, sans API, et corrigeable à la main.
- **Détection fonds de commerce** : mots-clés éliminatoires + contrôle de cohérence prix/m²
  (un local à < 1 500 €/m² en petite couronne sans le mot « murs » est presque toujours un
  fonds ou un droit au bail). Listes et planchers dans `config.yaml`.
- **Le scoring est recalculé à chaque run** sur tout le stock : modifier `config.yaml` ou les
  benchmarks re-score toutes les annonces au run suivant.
- **Scraping poli, vérifié source par source** (relevés robots.txt du 2026-07-02 documentés
  en tête de chaque parser) : User-Agent honnête avec contact, 3-5 s entre requêtes, arrêt
  propre sur 403/429, premières pages uniquement (les listings sont triés « plus récentes
  d'abord », largement suffisant pour un run quotidien). ~7 requêtes par run au total.
