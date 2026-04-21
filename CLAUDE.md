# Project 7 Seas — CLAUDE.md

Outil de veille et d'aide à la décision d'investissement personnel.
**Pas d'exécution automatique** — toutes les décisions sont manuelles via Revolut.

## Structure du projet

```
03. Strategy/
  data_feed.py     — Téléchargement stooq.com, cache CSV (_prices.csv), TICKERS, TICKER_DESC
  regime.py        — Détection régime SPY SMA200 ±1% → {1=BULL, 0=TRANS, -1=BEAR}
  allocator.py     — Allocation par régime (momentum top-N bull, GLD/SLV bear)
  backtest.py      — Moteur backtest biweekly avec protection look-ahead
  metrics.py       — CAGR, Sharpe, Max Drawdown, Calmar, Win Rate
  swing.py         — Signaux swing trading, journal des trades, SMA décalée, SWING_GROUPS, TICKER_ICONS
  riskbenefit.py   — Analyse risque/bénéfice : fetch yfinance targets, cache TTL 14j, score
  ui/app.py        — Dashboard Streamlit (6 tabs)
  data/
    _prices.csv           — Cache prix (2014-01-01 à aujourd'hui, ~3MB)
    _volume.csv           — Cache volumes (2 ans glissants, tickers swing uniquement)
    _computed_cache.pkl   — Cache calculs : séries + figures Plotly pré-construites
    theses.json           — Carnet de thèses éditable depuis l'app
    _trades.json          — Journal des trades swing (entrées + sorties + frais %)
    _targets.json         — Cache targets analystes Yahoo Finance (TTL 14 jours)

Lancer l'app.bat   — Lance le serveur Streamlit (port 8501)
```

## Lancer l'application

Double-cliquer sur `Lancer l'app.bat` depuis la racine du projet.
Le bat file : tue le process sur port 8501, supprime les `__pycache__`, relance Streamlit.

## Architecture de l'app (6 tabs)

| Tab | Description |
|---|---|
| 📡 Signal Macro | Régime SPY actuel + historique 12 mois / 5 ans / complet |
| 🔭 Secteurs | 10 secteurs, composite equal-weight + SMA + régime coloré |
| 💡 Thèses | Carnet de convictions éditable, sauvegarde JSON, perf tickers |
| 📊 Backtest | Backtest momentum/régime conservé pour référence |
| 🏆 Classement | Bar chart secteurs triés par performance (3 périodes) |
| 📈 Swing Trading | Graphique prix/SMA décalée, journal trades, sélecteur cards groupées |
| ⚖️ Risque/Bénéfice | Targets analystes yfinance, probabilités, score espérance×ratio B/R |

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

Note : LDO.MI, HO.PA, HEI.DE ne sont pas disponibles sur stooq.com → couverts par le fallback yfinance. BA.L (BAE Systems) est dans TICKERS avec suffixe `.uk`. HDMG.DE était un ticker invalide (pointe vers Heidelberger Druckmaschinen sur Yahoo) — remplacé par HEI.DE (Heidelberg Materials).

## Tab Swing Trading (swing.py + app.py tab5)

**Tickers swing** : ~48 tickers regroupés en 11 familles dans `SWING_GROUPS` (swing.py).
**Sélecteur** : cards groupées par famille (couleur + icône emoji), 4 boutons max par ligne, retour à la ligne automatique. État via `st.session_state["sw_ticker"]`.

**Signal RSI glow** (`detect_rsi_glow_tickers`) :
- Détecte : RSI(14) croise sa SMA14 à la hausse depuis zone survente (RSI < 45), dans les 15 derniers jours
- Retourne `dict {ticker: jours_depuis_signal}`
- Tickers surveillés : `GLOW_TICKERS` dans `swing.py` (actuellement BEAM, META, DE, CAT)
- Affichage : neon doré fixe sur la card (`box-shadow` + `border` #ffd166) + badge `J+N` en bas à droite
- CSS : Streamlit expose la key du bouton comme classe `st-key-{key}` sur le `stElementContainer` → `.st-key-sw_btn_{ticker} button` est le sélecteur fiable

**SMA50 décalée + RSI** (`build_price_chart`) :
- RSI(14) affiché sur axe secondaire du sous-graphique volume, avec sa SMA14 en orange pointillé
- Historique : SMA50[i+25] affiché à la date[i] → moving average centrée
- Projection (25 derniers jours) : fenêtre rétrécie de SMA50 → SMA5, toutes calculées sur les prix jusqu'à j0 (ancre commune)
- `STEP = (50 - 5) / (25 - 5) = 2.25` — pas de rétrécissement par jour
- `win = max(int(round(50 - 2.25 * k)), 5)` — évite le slice d'indices flottants

**Journal des trades** (`_trades.json`) :
- Colonnes : Date, Ticker, Direction (Long/Short), Prix entrée, Quantité, Prix sortie, Frais %
- P&L : Long = (sortie/entrée−1)×100−frais%, Short = (1−sortie/entrée)×100−frais%
- Formulaire entrée + expander "Enregistrer une sortie" (sélecteur trade ouvert + P&L preview)

**Familles SWING_GROUPS** :
```
🤖 IA/Tech, 💊 Santé/Biotech, 🏗️ Infrastructure, 🛡️ Défense,
⚛️ Nucléaire/Énergie, 🛒 Conso/Services, ₿ Crypto, 🥇 Métaux,
🚀 Spatial, 🔬 Quantum, 🌐 Spéculatif
```

## Tab Risque/Bénéfice (riskbenefit.py + app.py tab6)

**Fetch** : `yfinance` — `fast_info` pour le prix, `analyst_price_targets` pour les targets (high/low/mean), fallback `.info`. Sleep entre chaque requête (2–4s selon volume).
**Cache** : `_targets.json`, TTL 14 jours par ticker. Si `fetched_at` < 14j → skip fetch. Merge `existing.update(fetched)` pour ne pas écraser les données fraîches.
**Avertissement** : Yahoo Finance rate-limite au-delà de ~10 tickers simultanés.
**Score** :
- `downside = max((price - low) / price, 6%)` — plancher 6%
- `dispersion = (high - low) / price`
- `espérance = p_bull × upside − p_bear × downside`
- `ratio B/R = upside / downside`
- `score = espérance × ratio / (1 + dispersion)`

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
- **Source unique : yfinance** — stooq.com banni (IP bloquée depuis >1 mois, `STOOQ_AVAILABLE = False`)
- Cache dans `data/_prices.csv` — start obligatoire 2014-01-01 pour warmup SMA200
- Tickers indisponibles sauvegardés comme colonnes vides (évite re-download)
- `load_prices` — stratégie incrémentale :
  - Démarrage normal : retour immédiat depuis CSV si tous les tickers présents (zéro requête réseau)
  - Nouveaux tickers manquants : télécharge uniquement ceux-là depuis 2014, merge
  - Rafraîchir : télécharge seulement les 7 derniers jours via `_fetch_batch` (batch yfinance)
  - `_fetch_batch` : `yf.download()` en chunks de 30 tickers = 2 requêtes batch max pour ~65 tickers. Fallback individuel `_fetch_yfinance()` pour les tickers absents du résultat.
- `load_volume` — même logique incrémentale, historique 2 ans. Batch yfinance via `_fetch_volume_batch`.
- yfinance : rate-limit temporaire (minutes/heures) si appelé trop fréquemment. Avec le batch, ~2 appels au lieu de 65 → risque très réduit.
- Deux boutons sidebar : "🔌 Tester stooq" et "🔌 Tester yfinance" — testent uniquement l'accessibilité IP (SPY 5j).
- **Après un rate-limit yfinance, attendre 15-30 min avant de relancer un refresh.**

### Tickers — points d'attention
- **NURO** : delisté (acquisition par ECOR en cours fin 2024) — à remplacer dans le secteur BCI
- **HEI.DE** : ticker correct pour Heidelberg Materials sur Yahoo Finance (ancien HDMG.DE invalide)
- **LDO.MI, HO.PA, HEI.DE** : non disponibles sur stooq, couverts par fallback yfinance

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

## Prochaines étapes

- [ ] Ajouter fallback yfinance dans `load_volume` (volumes critiques pour analyse swing)
- [ ] Investiguer prix plats depuis le 20 mars après refresh (probablement ffill masquant fusion stooq/yfinance)
- [ ] Remplacer NURO (delisté) par ECOR ou autre ticker BCI
- [ ] Retirer le bloc debug "🔧 Cache debug" de la sidebar avant push GitHub
- [ ] Migration GitHub + Streamlit Community Cloud (inclure _prices.csv et _computed_cache.pkl)
- [ ] GitHub Action pour mise à jour automatique du CSV + rebuild pkl (1x/jour)
- [ ] Mobile : layout="wide" à revoir, desktop prioritaire pour l'instant
- [ ] Enrichir les thèses sectorielles (catalyseurs, dates FDA, etc.)
