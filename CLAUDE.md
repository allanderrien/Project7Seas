# Project 7 Seas — CLAUDE.md

Outil de veille et d'aide à la décision d'investissement personnel.
**Pas d'exécution automatique** — toutes les décisions sont manuelles via Revolut.

## Structure du projet

```
03. Strategy/
  data_feed.py     — Téléchargement stooq.com, cache CSV (_prices.csv)
  regime.py        — Détection régime SPY SMA200 ±1% → {1=BULL, 0=TRANS, -1=BEAR}
  allocator.py     — Allocation par régime (momentum top-N bull, GLD/SLV bear)
  backtest.py      — Moteur backtest biweekly avec protection look-ahead
  metrics.py       — CAGR, Sharpe, Max Drawdown, Calmar, Win Rate
  ui/app.py        — Dashboard Streamlit (5 tabs)
  data/
    _prices.csv           — Cache prix (2014-01-01 à aujourd'hui, ~3MB)
    _computed_cache.pkl   — Cache calculs : séries + figures Plotly pré-construites
    theses.json           — Carnet de thèses éditable depuis l'app

Lancer l'app.bat   — Lance le serveur Streamlit (port 8501)
```

## Lancer l'application

Double-cliquer sur `Lancer l'app.bat` depuis la racine du projet.
Le bat file : tue le process sur port 8501, supprime les `__pycache__`, relance Streamlit.

## Architecture de l'app (5 tabs)

| Tab | Description |
|---|---|
| 📡 Signal Macro | Régime SPY actuel + historique 12 mois / 5 ans / complet |
| 🔭 Secteurs | 10 secteurs, composite equal-weight + SMA + régime coloré |
| 💡 Thèses | Carnet de convictions éditable, sauvegarde JSON, perf tickers |
| 📊 Backtest | Backtest momentum/régime conservé pour référence |
| 🏆 Classement | Bar chart secteurs triés par performance (3 périodes) |

## Secteurs suivis

| Secteur | Tickers | SMA |
|---|---|---|
| Or & Argent | GLD, SLV | 100j |
| IA/Tech | NVDA, MSFT, GOOGL, META, TSM | 100j |
| Spatial | RKLB, LUNR, ASTS | 50j |
| Défense EU | RHM.DE, BA.L, HAG.DE | 100j |
| Quantum | RGTI, QBTS, IONQ | 50j |
| Biotech | LLY, VKTX, BEAM | 100j |
| Crypto | BTC-USD, ETH-USD, SOL-USD | 50j |
| Construction | CAT, DE, URI | 100j |
| Nucléaire | CCJ, NNE, OKLO | 50j |
| BCI | NURO | 50j |

Note : LDO.MI, HO.PA, HDMG.DE ne sont pas disponibles sur stooq.com.

## Système de cache disque

L'app utilise `_computed_cache.pkl` pour éviter tout recalcul à l'affichage.

**Contenu du pkl :**
- `_spy` : séries SMA200 + régime SPY (historique complet)
- `_spy_figs` : 3 figures Plotly SPY (12 mois, 5 ans, complet)
- `_momentum` : dict ticker → {1M, 3M, 6M, 1A, Prix}
- `{secteur}` : {comp, sma, regime} par secteur
- `_sector_figs` : figures Plotly par secteur × 3 périodes
- `_backtest` : résultats backtest avec paramètres par défaut
- `_backtest_figs` : 3 figures backtest
- `_ranking_figs` : 3 figures classement

**Invalidation :** pkl mtime ≥ prices.csv mtime → chargement direct, sinon rebuild.
**Rebuild :** bouton "🔄 Rafraîchir" dans la sidebar.
**Après un changement de code** qui modifie la structure du pkl : supprimer `_computed_cache.pkl` manuellement depuis l'Explorateur Windows (ne pas utiliser `del` bash sur Windows — ça ne fonctionne pas), puis cliquer "Rafraîchir".

## Règles importantes

### Données
- Source : stooq.com (yfinance rate-limitée)
- Cache dans `data/_prices.csv` — start obligatoire 2014-01-01 pour warmup SMA200
- Tickers indisponibles sauvegardés comme colonnes vides (évite re-download)
- `load_prices` re-télécharge TOUT l'univers si un ticker manque — ajouter des tickers nécessite un "Rafraîchir"

### Fix critique — warmup SMA200
Le régime **doit** être calculé sur l'historique complet avant de slicer par période :
```python
full_regime = compute_regime(prices["SPY"])   # ← sur prices complet, PAS prices_period
```
Un garde-fou dans `backtest.py` lève une erreur si < 280 lignes avant la période de début.

### Régime
- SPY uniquement (GLD retiré — se comporte comme actif spéculatif, mauvais signal bear)
- Buffer ±1% autour de SMA200
- Secteurs : buffer ±2% (plus volatile que SPY)

### Source de données alternatives
Si stooq est indisponible, chercher des symboles alternatifs.
Pour les tickers EU : stooq utilise `.de`, `.fr`, `.it` comme suffixes.

## Prochaines étapes

- [ ] Retirer le bloc debug "🔧 Cache debug" de la sidebar avant push GitHub
- [ ] Migration GitHub + Streamlit Community Cloud (inclure _prices.csv et _computed_cache.pkl)
- [ ] GitHub Action pour mise à jour automatique du CSV + rebuild pkl (1x/jour)
- [ ] Mobile : layout="wide" à revoir, desktop prioritaire pour l'instant
- [ ] Enrichir les thèses sectorielles (catalyseurs, dates FDA, etc.)
