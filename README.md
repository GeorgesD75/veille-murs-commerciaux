# Les Murs. — votre veille de murs commerciaux, automatique

Chaque matin à 7 h, ce système :
1. fait la tournée de **8 sources** (sites spécialisés, API, alertes email des grands
   portails, ventes aux enchères) ;
2. **écarte les pièges** (fonds de commerce déguisés, prix incohérents, hors zone,
   rendements trop beaux pour être vrais) ;
3. **note chaque annonce sur 100** (rendement, emplacement, prix vs marché, trajet,
   quartier 18e) et compare au marché local ;
4. met à jour votre site privé **« Les Murs. »** (comparateur, simulateur de
   financement, checklist d'achat) ;
5. vous **envoie un email** s'il y a du nouveau — et un email immédiat 🔥 si une
   pépite (score ≥ 80) apparaît.

Zéro serveur, zéro abonnement : GitHub exécute et héberge tout gratuitement.

---

## Mise en route (~30 minutes, une seule fois)

### Étape 1 — Créer un compte GitHub et y envoyer le projet

1. Créez un compte sur [github.com](https://github.com) (gratuit).
2. Créez un dépôt : bouton **New repository**, nom `veille-murs-commerciaux`,
   visibilité **Public** (obligatoire pour l'hébergement gratuit du site —
   pas d'inquiétude : le site est non référencé par les moteurs de recherche,
   et le dépôt ne contient aucun mot de passe). **Ne cochez rien d'autre.**
3. Sur VOTRE ordinateur, ouvrez PowerShell dans le dossier du projet et collez
   (remplacez `VOTRE-PSEUDO`) :

   ```powershell
   git remote add origin https://github.com/VOTRE-PSEUDO/veille-murs-commerciaux.git
   git push -u origin master
   ```

   GitHub vous demandera de vous connecter — suivez la fenêtre qui s'ouvre.

### Étape 2 — Activer le site (GitHub Pages)

1. Sur la page GitHub du dépôt : **Settings → Pages**.
2. Sous « Build and deployment » : Source = **Deploy from a branch**,
   Branch = **master**, dossier = **/docs**, puis **Save**.
3. Après ~2 minutes, l'adresse de votre site apparaît en haut de cette page
   (`https://VOTRE-PSEUDO.github.io/veille-murs-commerciaux/`). Gardez-la.
4. Recopiez cette adresse dans le fichier `config.yaml` du dépôt : ouvrez le
   fichier sur GitHub, cliquez le crayon ✏️, remplissez
   `url_dashboard: "https://…"` (tout en bas), bouton **Commit changes**.
   → C'est le lien « Ouvrir le tableau de chasse » de vos emails.

### Étape 3 — Autoriser la lecture des alertes dans votre Gmail

Les grands portails (LeBonCoin, SeLoger, Geolocaux…) interdisent la collecte
automatique MAIS envoient des alertes email gratuites : le système les lit
directement dans votre boîte Gmail. **Sans risque pour vos autres emails** :
le robot ne cherche QUE les messages venant des portails connus — il ne lit ni
ne marque rien d'autre.

1. Activez la **validation en 2 étapes** sur votre compte Google (si ce n'est
   pas déjà fait) : [myaccount.google.com/security](https://myaccount.google.com/security).
2. Créez un **mot de passe d'application** (un mot de passe spécial, limité,
   que vous pouvez révoquer à tout moment — PAS votre mot de passe Gmail) :
   [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
   → nom « veille murs » → notez les 16 caractères affichés (c'est `IMAP_PASSWORD`).

### Étape 4 — Le compte d'envoi d'emails (Resend)

1. Créez un compte gratuit sur [resend.com](https://resend.com) **avec votre adresse
   personnelle** (celle où vous voulez recevoir les alertes : en offre gratuite,
   Resend n'envoie qu'à l'adresse du compte).
2. Menu **API Keys → Create API key** → copiez la clé (c'est `RESEND_API_KEY`).

### Étape 5 — Renseigner les 4 secrets

Sur GitHub : **Settings → Secrets and variables → Actions → New repository secret**,
quatre fois :

| Nom du secret | Valeur |
|---|---|
| `IMAP_USER` | votre adresse Gmail (celle qui reçoit les alertes) |
| `IMAP_PASSWORD` | le mot de passe d'application 16 caractères (étape 3) |
| `RESEND_API_KEY` | la clé Resend (étape 4) |
| `EMAIL_TO` | votre adresse Gmail (la même) |

### Étape 6 — Créer les alertes sur les portails

Sur chaque portail, créez une recherche + alerte email **vers votre adresse
Gmail**. Critères conseillés partout : *achat / vente · local commercial ·
Île-de-France · 140 000 à 420 000 €*.

- **LeBonCoin** ([leboncoin.fr](https://www.leboncoin.fr)) : catégorie
  Immobilier → Bureaux & Commerces, filtre « Vente », zone Île-de-France,
  fourchette de prix → bouton **Créer une alerte** (créez un compte LeBonCoin
  avec l'adresse dédiée, ou renseignez-la comme email de réception).
- **SeLoger Bureaux & Commerces** ([bureauxlocaux.com](https://www.bureauxlocaux.com)) :
  recherche « Acheter · Local commercial · Île-de-France » → **Créer une alerte email**.
- **Geolocaux** ([geolocaux.com](https://www.geolocaux.com)) : Achat → Local
  commercial → Île-de-France → **Alerte email**.
- Bonus : les alertes de n'importe quel autre portail envoyées à cette boîte
  seront tentées aussi — au pire elles sont ignorées proprement.

Astuce : depuis la boîte dédiée, un test simple = transférez-vous une vraie
alerte reçue ; à la tournée suivante, l'annonce apparaît sur le site.

### Étape 7 — Premier essai

1. Onglet **Actions** du dépôt → « Veille quotidienne » → **Run workflow**.
2. Deux minutes plus tard : la coche verte ✅, votre site est à jour, et vous
   recevez l'email du jour s'il y a des nouveautés.

C'est terminé : chaque matin à 7 h, tout se refait sans vous.

---

## La vie courante

- **Consulter** : ouvrez votre site (mettez-le en favori sur ordinateur ET téléphone).
- **Lancer une tournée à la main** : Actions → Veille quotidienne → Run workflow.
- **Modifier un réglage** : sur GitHub, ouvrez le fichier → crayon ✏️ → Commit.
  - `config.yaml` — budget, barème du score, seuils, communes bonus, sources
    on/off, cible de rendement, hypothèses de crédit ;
  - `data/benchmarks.json` — les fourchettes de prix/m² et loyers du marché
    (affinez-les au fil de vos visites : tout le monde vous dira merci) ;
  - `data/trajets.json` — les temps de trajet depuis Paris 18e.
  Le score de TOUTES les annonces est recalculé à la tournée suivante.

## En cas de pépin

- **Une source en erreur** dans « Santé des sources » (pied du site) : pas grave,
  les autres continuent ; si ça dure plusieurs jours, le site a probablement
  changé sa structure — les autres sources compensent en attendant un correctif.
- **Pas d'emails** : vérifiez les 4 secrets (étape 5) et que `EMAIL_TO` est bien
  l'adresse de votre compte Resend.
- **`imap : avertissement identifiants absents`** : secrets `IMAP_USER` /
  `IMAP_PASSWORD` manquants ou mal copiés.
- **La tournée ne se lance plus** : GitHub suspend les crons après 60 jours sans
  activité — le commit quotidien des données l'évite normalement ; sinon, un
  passage sur Actions → « Enable workflow » suffit.

## Ce qu'il y a sous le capot

```
run.py                  La tournée : collecte → filtres → score → site → emails
config.yaml             TOUS les réglages, commentés en français
sources/                1 fichier = 1 source (8 canaux), client HTTP poli
                        (robots.txt vérifié, 3-5 s entre requêtes, arrêt sur refus)
pipeline/               Filtres anti-pièges, dédoublonnage, enrichissement,
                        scoring /100, lecture du prix, notifications
dashboard/generer.py    Le site « Les Murs. » (1 fichier autonome, non référencé)
data/annonces.json      La mémoire (committée à chaque tournée = historique gratuit)
tests/                  96 tests automatiques, joués avant chaque tournée
.github/workflows/      Le réveil-matin (cron 7 h Paris + bouton manuel)
```

Choix assumés, en une ligne chacun : stockage JSON versionné (diffs lisibles) ;
scraping poli et documenté source par source ; les grands portails passent par
leurs alertes email officielles ; les enchères ont leur score d'intérêt propre
(le prix final étant imprévisible, on ne le prédit jamais) ; tout rendement
> 10 % est plafonné sous le seuil d'affichage jusqu'à vérification humaine.

Budget de fonctionnement : **0 €** (GitHub Actions ~3 min/jour, Pages, Resend
et Gmail dans leurs offres gratuites).
