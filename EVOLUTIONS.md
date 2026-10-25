# Refonte de la recherche — 25 octobre 2026

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
