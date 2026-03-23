"""
app.py  —  Project 7 Seas — Trading Strategy Dashboard
"""

import sys, os, json, pickle, contextlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from data_feed  import load_prices, RISK_ON, DEFENSIVE, TICKERS, MOONSHOTS
from regime     import compute_regime, regime_label, BUFFER
from allocator  import compute_weights, MOMENTUM_LOOKBACK, TOP_N_BULL
from backtest   import run, benchmark_equal_weight, FEE_RATE
from metrics    import compute_metrics

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Project 7 Seas",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Sector definitions ────────────────────────────────────────────────────────

SECTORS = {
    "🥇 Or & Argent": {
        "tickers":     ["GLD", "SLV"],
        "sma":         100,
        "color":       "#f5c542",
        "description": "Métaux précieux — valeurs refuge et couverture inflation",
        "thesis":      "Or : réserve de valeur face à la débasement monétaire, demande des banques centrales en hausse structurelle. Argent : double exposition métal précieux + industriel (solaire, électronique). À surveiller en régime BEAR ou incertitude géopolitique.",
    },
    "🤖 IA / Tech": {
        "tickers":     ["NVDA", "MSFT", "GOOGL", "META", "TSM"],
        "sma":         100,
        "color":       "#3a86ff",
        "description": "Intelligence artificielle et semi-conducteurs",
        "thesis":      "Rupture technologique en cours d'adoption massive — momentum fort malgré risque de bulle.",
    },
    "🚀 Spatial": {
        "tickers":     ["RKLB", "LUNR", "ASTS"],
        "sma":         50,
        "color":       "#ff6b6b",
        "description": "New Space — launch, satellites, exploration lunaire",
        "thesis":      "Effondrement des coûts de lancement. Prochaine étape : économie lunaire. Encore en phase early.",
    },
    "🛡️ Défense EU": {
        "tickers":     ["RHM.DE", "BA.L", "HAG.DE"],
        "sma":         100,
        "color":       "#4ecdc4",
        "description": "Réarmement européen — cycle haussier structurel",
        "thesis":      "Contexte géopolitique impose une hausse durable des budgets défense en Europe. Cycle de 10 ans.",
    },
    "⚛️ Quantum": {
        "tickers":     ["RGTI", "QBTS", "IONQ"],
        "sma":         50,
        "color":       "#b185db",
        "description": "Informatique quantique — horizon 5-10 ans",
        "thesis":      "Technologie de rupture réelle mais horizon long. Très spéculatif, position sizing réduit.",
    },
    "💊 Biotech": {
        "tickers":     ["LLY", "VKTX", "BEAM"],
        "sma":         100,
        "color":       "#ffd93d",
        "description": "Innovation médicale — GLP-1, thérapies géniques",
        "thesis":      "GLP-1 : révolution en cours. Thérapies géniques : 5-10 ans. Surveiller catalyseurs FDA.",
    },
    "₿ Crypto": {
        "tickers":     ["BTC-USD", "ETH-USD", "SOL-USD"],
        "sma":         50,
        "color":       "#ff9f1c",
        "description": "Actifs numériques",
        "thesis":      "BTC institutionnalisé (ETF). SOL/ETH : infrastructure Web3. Cycles de 4 ans à surveiller.",
    },
    "🏗️ Construction": {
        "tickers":     ["CAT", "DE", "URI"],
        "sma":         100,
        "color":       "#6a4c93",
        "description": "Infrastructure et matériaux de construction",
        "thesis":      "Baromètre de l'activité industrielle mondiale. Bénéficiaire des plans d'infrastructure.",
    },
    "☢️ Nucléaire": {
        "tickers":     ["CCJ", "NNE", "OKLO"],
        "sma":         50,
        "color":       "#06d6a0",
        "description": "Énergie nucléaire nouvelle génération — uranium, SMR, micro-réacteurs",
        "thesis":      "Le consensus anti-nucléaire se retourne : Big Tech signe des contrats directs avec des réacteurs (Microsoft/Three Mile Island, Google/Kairos). CCJ bénéficiaire direct ; NNE et OKLO sont des paris SMR très early. Re-rating possible bien avant 2030 si les premiers SMR sont opérationnels.",
    },
    "🧠 BCI": {
        "tickers":     ["NURO"],
        "sma":         50,
        "color":       "#a2d2ff",
        "description": "Interface cerveau-machine — neurostimulation, BCI",
        "thesis":      "Moins médiatisé que l'IA générative mais potentiellement aussi disruptif sur 10-15 ans. La FDA déverrouille la réglementation. Les pure plays liquides cotés sont rares — Synchron (privé) concentre l'attention. NURO est une exposition partielle très spéculative.",
    },
}

# ── Constants ─────────────────────────────────────────────────────────────────

REGIME_BG       = {1: "rgba(144,238,144,0.15)", 0: "rgba(255,220,80,0.15)", -1: "rgba(255,100,100,0.15)"}
REGIME_FILL     = {1: "rgba(46,200,100,0.22)",  0: "rgba(255,180,0,0.22)",  -1: "rgba(220,60,60,0.22)"}
REGIME_LABEL    = {1: "BULL", 0: "TRANSITION", -1: "BEAR"}
REGIME_EMOJI    = {1: "🟢",   0: "🟡",          -1: "🔴"}
THESES_PATH     = os.path.join(os.path.dirname(__file__), "..", "data", "theses.json")

# ── Dark theme ────────────────────────────────────────────────────────────────

_DARK_BG   = "#1e2130"
_DARK_GRID = "#2e3450"
_DARK_TEXT = "#c9d1d9"
_SPY_COLOR = "#e0e0e0"   # SPY line sur fond sombre (blanc cassé)

def apply_dark_theme(fig):
    """Apply consistent dark theme to any Plotly figure."""
    fig.update_layout(
        plot_bgcolor=_DARK_BG,
        paper_bgcolor=_DARK_BG,
        font=dict(color=_DARK_TEXT),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=_DARK_TEXT)),
    )
    fig.update_xaxes(showgrid=True, gridcolor=_DARK_GRID, color=_DARK_TEXT,
                     linecolor=_DARK_GRID, zerolinecolor=_DARK_GRID)
    fig.update_yaxes(showgrid=True, gridcolor=_DARK_GRID, color=_DARK_TEXT,
                     linecolor=_DARK_GRID, zerolinecolor=_DARK_GRID)
    return fig

# ── Data loading ──────────────────────────────────────────────────────────────

ALL_TICKERS = list(set(
    list(TICKERS.keys()) +
    list(MOONSHOTS.keys()) +
    [t for s in SECTORS.values() for t in s["tickers"]]
))

@st.cache_data(show_spinner="Chargement des prix...")
def get_prices(do_refresh: bool):
    return load_prices(tickers=ALL_TICKERS, refresh=do_refresh).ffill()

# Sidebar — minimal
st.sidebar.title("🌊 Project 7 Seas")
st.sidebar.markdown("---")
refresh = st.sidebar.button("🔄 Rafraîchir les données")
prices  = get_prices(refresh)

# ── Disk cache pour les composites sectoriels ──────────────────────────────────

_PRICES_CSV = os.path.join(os.path.dirname(__file__), "..", "data", "_prices.csv")
_CACHE_PKL  = os.path.join(os.path.dirname(__file__), "..", "data", "_computed_cache.pkl")

_BT_DEFAULT_INITIAL  = 1000
_BT_DEFAULT_GOLD_PCT = 50

SECTOR_PERIODS = [
    ("12 derniers mois",   1),
    ("3 ans",              3),
    ("Historique complet", None),
]

RANKING_PERIODS = SECTOR_PERIODS  # même découpage


def _csv_last_date() -> str:
    """Retourne la dernière date du CSV sous forme de string YYYY-MM-DD."""
    tail = pd.read_csv(_PRICES_CSV, index_col=0, parse_dates=True).index.max()
    return str(tail.date())


def _cache_valid() -> bool:
    if not os.path.exists(_CACHE_PKL) or not os.path.exists(_PRICES_CSV):
        return False
    try:
        with open(_CACHE_PKL, "rb") as f:
            cached = pickle.load(f)
        return cached.get("_last_date") == _csv_last_date()
    except Exception:
        return False


def _build_spy_figs(spy: pd.Series, sma200: pd.Series, full_regime: pd.Series) -> dict:
    """Pré-construit les 3 figures SPY (12m, 5 ans, complet)."""
    figs    = {}
    last_dt = spy.index.max()
    cuts    = {"12m": last_dt - pd.DateOffset(years=1),
               "5y":  last_dt - pd.DateOffset(years=5)}

    for key, h, cutoff in [
        ("12m", 300, cuts["12m"]),
        ("5y",  380, cuts["5y"]),
        ("full", 380, spy.index[0]),
    ]:
        s_s   = spy.loc[cutoff:]
        sma_s = sma200.loc[cutoff:]
        reg_s = full_regime.loc[cutoff:]
        fig   = go.Figure()
        regime_shading(fig, reg_s)
        fig.add_trace(go.Scatter(x=sma_s.index, y=sma_s, name="SMA200",
                                 line=dict(color="steelblue", dash="dash",
                                           width=1.5 if key != "full" else 1.2)))
        fig.add_trace(go.Scatter(x=s_s.index, y=s_s, name="SPY",
                                 line=dict(color=_SPY_COLOR,
                                           width=2 if key != "full" else 1.8)))
        fig.update_layout(height=h, margin=dict(t=10, b=10),
                          legend=dict(orientation="h"), hovermode="x unified")
        apply_dark_theme(fig)
        figs[key] = fig
    return figs


def _build_backtest_fig(data: dict, period_name: str, spy_sma200: pd.Series) -> go.Figure:
    """Pré-construit une figure backtest (equity + DD + SPY)."""
    PERIOD_COLORS = {"Historique": "steelblue",
                     "Validation Bear": "tomato",
                     "Validation Bull": "seagreen"}
    eq, bnh, reg = data["equity"], data["bnh"], data["regime"]
    color = PERIOD_COLORS.get(period_name, "gray")

    fig  = make_subplots(rows=3, cols=1, shared_xaxes=True,
                         row_heights=[0.60, 0.25, 0.15], vertical_spacing=0.03)
    norm = eq.iloc[0]
    fig.add_trace(go.Scatter(x=bnh.index, y=bnh/norm, name="Buy & Hold",
                             line=dict(color="gray", dash="dash", width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=eq.index, y=eq/norm, name="Stratégie",
                             line=dict(color=color, width=2.5)), row=1, col=1)
    fig.add_hline(y=1.0, line_dash="dot", line_color="black", line_width=0.5, row=1, col=1)

    dd_s = (eq  - eq.cummax())  / eq.cummax()  * 100
    dd_b = (bnh - bnh.cummax()) / bnh.cummax() * 100
    fig.add_trace(go.Scatter(x=dd_b.index, y=dd_b, name="B&H DD",
                             line=dict(color="gray", dash="dash", width=1),
                             showlegend=False), row=2, col=1)
    fig.add_trace(go.Scatter(x=dd_s.index, y=dd_s, name="Strat DD",
                             fill="tozeroy", fillcolor="rgba(70,130,180,0.12)",
                             line=dict(color=color, width=1.2),
                             showlegend=False), row=2, col=1)

    spy_p  = prices["SPY"].loc[reg.index[0]:reg.index[-1]]
    sma200 = spy_sma200.loc[reg.index[0]:reg.index[-1]]
    prev_i, prev_r = 0, reg.iloc[0]
    for idx in range(1, len(reg)):
        if reg.iloc[idx] != prev_r or idx == len(reg) - 1:
            x1 = reg.index[-1] if idx == len(reg) - 1 else reg.index[idx]
            for row_n in (1, 3):
                fig.add_shape(type="rect", x0=reg.index[prev_i], x1=x1,
                              y0=0, y1=1, xref="x", yref="y domain",
                              fillcolor=REGIME_FILL[prev_r],
                              row=row_n, col=1, layer="below", line_width=0)
            prev_i, prev_r = idx, reg.iloc[idx]

    fig.add_trace(go.Scatter(x=spy_p.index, y=spy_p, name="SPY",
                             line=dict(color=_SPY_COLOR, width=1.5),
                             showlegend=False), row=3, col=1)
    fig.add_trace(go.Scatter(x=sma200.index, y=sma200, name="SMA200",
                             line=dict(color="steelblue", dash="dash", width=1.2),
                             showlegend=False), row=3, col=1)
    fig.update_yaxes(title_text="Valeur (norm.)", row=1, col=1)
    fig.update_yaxes(title_text="DD %",           row=2, col=1)
    fig.update_yaxes(title_text="SPY",            row=3, col=1)
    fig.update_layout(height=600, margin=dict(t=20, b=20),
                      legend=dict(orientation="h"))
    apply_dark_theme(fig)
    return fig


def _build_ranking_figs(draft: dict) -> dict:
    """Pré-construit les 3 figures de classement."""
    last_dt = prices.index.max()
    figs    = {}
    for label, years in RANKING_PERIODS:
        cutoff = None if years is None else last_dt - pd.DateOffset(years=years)
        rows   = []
        for sector_name, info in SECTORS.items():
            if sector_name not in draft:
                continue
            d      = draft[sector_name]
            sliced = d["comp"].dropna() if cutoff is None else d["comp"].loc[cutoff:].dropna()
            if len(sliced) < 2:
                continue
            perf    = (sliced.iloc[-1] / sliced.iloc[0] - 1) * 100
            cur_reg = int(d["regime"].iloc[-1])
            rows.append({"label": f"{REGIME_EMOJI[cur_reg]} {sector_name}",
                         "perf":  perf,
                         "color": info["color"] if perf >= 0 else "#e05252"})
        if not rows:
            continue
        rows.sort(key=lambda x: x["perf"])
        fig = go.Figure(go.Bar(
            x=[r["perf"]  for r in rows], y=[r["label"] for r in rows],
            orientation="h", marker_color=[r["color"] for r in rows],
            marker_line_width=0,
            text=[f"{r['perf']:+.1f}%" for r in rows],
            textposition="outside", textfont=dict(color=_DARK_TEXT, size=12),
            cliponaxis=False,
        ))
        fig.add_vline(x=0, line_color=_DARK_TEXT, line_width=1, line_dash="dot")
        fig.update_layout(height=max(320, len(rows) * 48),
                          margin=dict(t=10, b=10, l=10, r=90),
                          xaxis_title="Performance (%)", showlegend=False)
        apply_dark_theme(fig)
        figs[label] = fig
    return figs


def _build_sector_cache() -> dict:
    result     = {}
    full_start = prices.index[0]
    last_dt    = prices.index.max()
    result["_last_date"] = str(last_dt.date())

    # 1. SPY — séries + figures
    if "SPY" in prices.columns:
        spy        = prices["SPY"]
        sma200     = spy.rolling(200).mean()
        full_regime = compute_regime(spy)
        result["_spy"]      = {"sma200": sma200, "regime": full_regime}
        result["_spy_figs"] = _build_spy_figs(spy, sma200, full_regime)

    # 2. Momentum tous tickers (1M, 3M, 6M, 1A)
    windows = {"1M": 21, "3M": 63, "6M": 126, "1A": 252}
    mom = {}
    for t in prices.columns:
        s = prices[t].dropna()
        if s.empty:
            continue
        row = {lbl: (f"{(s.iloc[-1] / s.iloc[-d] - 1) * 100:+.1f}%" if len(s) >= d else "—")
               for lbl, d in windows.items()}
        row["Prix"] = f"${s.iloc[-1]:.2f}"
        mom[t] = row
    result["_momentum"] = mom

    # 3. Composites sectoriels + figures
    cutoffs = {lbl: (None if y is None else last_dt - pd.DateOffset(years=y))
               for lbl, y in SECTOR_PERIODS}
    sector_figs = {}
    for name, info in SECTORS.items():
        comp = sector_composite(info["tickers"], full_start)
        if comp.empty or len(comp.dropna()) < info["sma"] + 5:
            continue
        sma, regime = sector_regime(comp, info["sma"])
        result[name] = {"comp": comp, "sma": sma, "regime": regime}
        figs = {}
        for period_label, cutoff in cutoffs.items():
            idx    = comp.index[0] if cutoff is None else cutoff
            comp_s = comp.loc[idx:]
            if not comp_s.dropna().empty:
                figs[period_label] = sector_chart(comp_s, sma.loc[idx:],
                                                  regime.loc[idx:], info["color"], info["sma"])
        sector_figs[name] = figs
    result["_sector_figs"] = sector_figs

    # 4. Backtest paramètres par défaut
    try:
        spy_sma = result.get("_spy", {}).get("sma200", pd.Series(dtype=float))
        ro      = [t for t in RISK_ON if t in prices.columns]
        bt_results = {}
        for label, s, e in [
            ("Historique",      "2015-01-01", "2021-12-31"),
            ("Validation Bear", "2022-01-01", "2022-12-31"),
            ("Validation Bull", "2023-01-01", last_dt.strftime("%Y-%m-%d")),
        ]:
            eq, reg, trades = run(prices, s, e, _BT_DEFAULT_INITIAL,
                                  FEE_RATE, gold_ratio=_BT_DEFAULT_GOLD_PCT / 100)
            bnh = benchmark_equal_weight(prices, ro, s, e, _BT_DEFAULT_INITIAL)
            bt_results[label] = {"equity": eq, "regime": reg, "trades": trades, "bnh": bnh,
                                 "metrics_strat": compute_metrics(eq),
                                 "metrics_bnh":   compute_metrics(bnh)}
        result["_backtest"]      = bt_results
        result["_backtest_figs"] = {p: _build_backtest_fig(d, p, spy_sma)
                                    for p, d in bt_results.items()}
    except Exception as e:
        print(f"  WARNING: backtest cache failed: {e}")

    # 5. Figures classement
    result["_ranking_figs"] = _build_ranking_figs(result)

    return result

# ── Helper functions ──────────────────────────────────────────────────────────

def regime_shading(fig: go.Figure, regime: pd.Series, use_vrect: bool = True):
    """Add regime background shading to a single-axis figure."""
    if len(regime) < 2:
        return
    prev_i, prev_r = 0, regime.iloc[0]
    for i in range(1, len(regime)):
        if regime.iloc[i] != prev_r or i == len(regime) - 1:
            x1 = regime.index[-1] if i == len(regime) - 1 else regime.index[i]
            if use_vrect:
                fig.add_vrect(x0=regime.index[prev_i], x1=x1,
                              fillcolor=REGIME_FILL[prev_r], layer="below", line_width=0)
            prev_i, prev_r = i, regime.iloc[i]


def sector_composite(tickers: list, start) -> pd.Series:
    """Equal-weight composite of available tickers, each normalised to 100 at first valid date."""
    avail = [t for t in tickers if t in prices.columns]
    if not avail:
        return pd.Series(dtype=float)
    sub = prices[avail].loc[pd.Timestamp(start):].copy()
    normed = pd.DataFrame({
        t: sub[t] / sub[t].dropna().iloc[0] * 100
        for t in avail if sub[t].dropna().size > 0
    })
    return normed.mean(axis=1)


def sector_regime(composite: pd.Series, sma_period: int, buffer: float = 0.02):
    """Return (sma, regime) for a sector composite."""
    sma    = composite.rolling(sma_period).mean()
    rel    = (composite - sma) / sma
    regime = pd.Series(0, index=composite.index, dtype=int)
    regime[rel >  buffer] =  1
    regime[rel < -buffer] = -1
    regime[rel.isna()]    =  0
    return sma, regime


def sector_chart(composite: pd.Series, sma: pd.Series, regime: pd.Series,
                 color: str, sma_period: int) -> go.Figure:
    """Sector chart: composite + SMA + regime background."""
    fig = go.Figure()
    regime_shading(fig, regime)
    fig.add_trace(go.Scatter(x=sma.index, y=sma, name=f"SMA{sma_period}",
                             line=dict(color="gray", dash="dash", width=1.2)))
    fig.add_trace(go.Scatter(x=composite.index, y=composite, name="Composite",
                             line=dict(color=color, width=2.2)))
    fig.update_layout(height=320, margin=dict(t=10, b=20, l=10, r=10),
                      legend=dict(orientation="h", y=1.08),
                      hovermode="x unified", yaxis_title="Valeur (base 100)")
    apply_dark_theme(fig)
    return fig


# ── Theses helpers ─────────────────────────────────────────────────────────────

THESES_COLS = ["Thèse", "Secteur", "Conviction", "Horizon", "Stade", "Tickers", "Notes"]

def load_theses() -> pd.DataFrame:
    if os.path.exists(THESES_PATH):
        with open(THESES_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if data:
            return pd.DataFrame(data, columns=THESES_COLS)
    return pd.DataFrame(columns=THESES_COLS)


def save_theses(df: pd.DataFrame):
    os.makedirs(os.path.dirname(THESES_PATH), exist_ok=True)
    # Convert to native Python types for JSON serialisation
    records = df.astype(str).where(df.notna(), "").to_dict(orient="records")
    with open(THESES_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)


# ── Chargement du cache sectoriel ─────────────────────────────────────────────

if _cache_valid() and not refresh:
    with open(_CACHE_PKL, "rb") as _f:
        sector_cache = pickle.load(_f)
else:
    with st.spinner("Calcul du cache (première fois ou après Rafraîchir)..."):
        try:
            sector_cache = _build_sector_cache()
            with open(_CACHE_PKL, "wb") as _f:
                pickle.dump(sector_cache, _f)
        except Exception as _e:
            st.error(f"Erreur lors du calcul du cache : {_e}")
            import traceback
            st.code(traceback.format_exc())
            sector_cache = {}

# ── Backtest (paramètres custom uniquement — défaut = depuis le pkl) ───────────

@st.cache_data(show_spinner="Calcul du backtest...")
def _run_backtest_custom(prices_version: str, top_n: int, lookback: int,
                         buf: float, fee: float, initial: int, gold_pct: int) -> dict:
    import allocator as _alloc
    import regime    as _reg
    _alloc.TOP_N_BULL        = top_n
    _alloc.MOMENTUM_LOOKBACK = lookback
    _reg.BUFFER              = buf
    ro      = [t for t in RISK_ON if t in prices.columns]
    results = {}
    for label, s, e in [
        ("Historique",      "2015-01-01", "2021-12-31"),
        ("Validation Bear", "2022-01-01", "2022-12-31"),
        ("Validation Bull", "2023-01-01", prices.index.max().strftime("%Y-%m-%d")),
    ]:
        eq, reg, trades = run(prices, s, e, initial, fee, gold_ratio=gold_pct / 100)
        bnh = benchmark_equal_weight(prices, ro, s, e, initial)
        results[label] = {"equity": eq, "regime": reg, "trades": trades, "bnh": bnh,
                          "metrics_strat": compute_metrics(eq),
                          "metrics_bnh":   compute_metrics(bnh)}
    return results

# ── Tabs ──────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📡 Signal Macro", "🔭 Secteurs", "💡 Thèses", "📊 Backtest", "🏆 Classement"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — SIGNAL MACRO
# ══════════════════════════════════════════════════════════════════════════════

with tab1:
    st.title("Signal Macro — SPY / SMA200")

    spy = prices["SPY"] if "SPY" in prices.columns else None

    if spy is None or "_spy" not in sector_cache:
        st.error("SPY non disponible.")
    else:
        full_regime  = sector_cache["_spy"]["regime"]
        sma200_full  = sector_cache["_spy"]["sma200"]
        today_regime = int(full_regime.iloc[-1])
        today_date   = prices.index.max().strftime("%d %B %Y")

        sma200_now = sma200_full.iloc[-1]
        spy_now    = spy.iloc[-1]
        diff_pct   = (spy_now / sma200_now - 1) * 100

        # ── Régime actuel
        st.markdown(
            f"### {REGIME_EMOJI[today_regime]} Régime : **{REGIME_LABEL[today_regime]}**  —  {today_date}"
        )
        c1, c2, c3 = st.columns(3)
        c1.metric("SPY",      f"${spy_now:.2f}")
        c2.metric("SMA200",   f"${sma200_now:.2f}")
        c3.metric("Distance", f"{diff_pct:+.2f}%",
                  delta_color="normal" if diff_pct > 0 else "inverse")

        _spy_figs = sector_cache.get("_spy_figs", {})

        st.markdown("---")
        st.subheader("12 derniers mois")
        if "12m" in _spy_figs:
            st.plotly_chart(_spy_figs["12m"], use_container_width=True)

        st.markdown("---")
        st.subheader("Historique long — 5 ans")
        if "5y" in _spy_figs:
            st.plotly_chart(_spy_figs["5y"], use_container_width=True)

        st.markdown("---")
        st.subheader("Historique complet")
        if "full" in _spy_figs:
            st.plotly_chart(_spy_figs["full"], use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — SECTEURS
# ══════════════════════════════════════════════════════════════════════════════

with tab2:
    st.title("Santé des secteurs")
    st.caption("Composites equal-weight normalisés à 100 — régime calculé sur l'historique complet.")

    sector_tabs = st.tabs(list(SECTORS.keys()))

    for i, (sector_name, info) in enumerate(SECTORS.items()):
        with sector_tabs[i]:

            st.caption(f"*{info['description']}*")
            st.info(info["thesis"], icon="💡")

            if sector_name not in sector_cache:
                st.warning("Données insuffisantes.")
                continue

            cached = sector_cache[sector_name]
            comp_full, sma_full, regime_full = cached["comp"], cached["sma"], cached["regime"]

            # ── Régime actuel + momentum
            cur_reg = int(regime_full.iloc[-1])
            col_reg, col_mom = st.columns([1, 2])

            with col_reg:
                st.metric("Régime", f"{REGIME_EMOJI[cur_reg]} {REGIME_LABEL[cur_reg]}")
                recent = regime_full.iloc[-20:]
                if (recent == 1).all():
                    st.success("BULL solide (20 derniers jours)")
                elif (recent == -1).all():
                    st.error("BEAR solide (20 derniers jours)")
                else:
                    st.warning("Zone de transition récente")

            with col_mom:
                _mom_cache = sector_cache.get("_momentum", {})
                avail_t = [t for t in info["tickers"] if t in _mom_cache]
                mom_rows = []
                for t in avail_t:
                    m = _mom_cache[t]
                    mom_rows.append({"Ticker": t, "1M": m["1M"], "3M": m["3M"], "1A": m["1A"], "Prix": m["Prix"]})
                if mom_rows:
                    st.dataframe(pd.DataFrame(mom_rows).set_index("Ticker"),
                                 use_container_width=True)

            st.markdown("---")

            # ── 3 graphes pré-construits depuis le cache
            _sfigs = sector_cache.get("_sector_figs", {}).get(sector_name, {})
            for period_label, _ in SECTOR_PERIODS:
                st.subheader(period_label)
                if period_label in _sfigs:
                    st.plotly_chart(_sfigs[period_label], use_container_width=True)
                else:
                    st.caption("Pas encore de données sur cette période.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — THÈSES
# ══════════════════════════════════════════════════════════════════════════════

with tab3:
    st.title("Carnet de thèses")
    st.caption(
        "Identifie et suis tes convictions d'investissement long terme. "
        "Règle d'or : max 2-3 thèses actives simultanément."
    )

    theses_df = load_theses()

    # ── Éditeur
    st.subheader("Thèses actives")
    sector_options = [s.split(" ", 1)[-1] for s in SECTORS.keys()] + ["Autre"]

    edited = st.data_editor(
        theses_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Thèse":      st.column_config.TextColumn("Thèse", width="large"),
            "Secteur":    st.column_config.SelectboxColumn("Secteur", options=sector_options),
            "Conviction": st.column_config.NumberColumn("★ Conviction", min_value=1, max_value=5, step=1, format="%d ★"),
            "Horizon":    st.column_config.TextColumn("Horizon (ex: 2026-2030)"),
            "Stade":      st.column_config.SelectboxColumn("Stade",
                              options=["Incubation", "Early", "Accélération", "Mature", "Sortie"]),
            "Tickers":    st.column_config.TextColumn("Tickers (séparés par ,)"),
            "Notes":      st.column_config.TextColumn("Notes / Catalyseurs", width="large"),
        },
        hide_index=True,
        key="theses_editor",
    )

    col_save, col_hint = st.columns([1, 4])
    with col_save:
        if st.button("💾 Sauvegarder", type="primary"):
            save_theses(edited)
            st.success("Sauvegardé.")
            st.rerun()
    with col_hint:
        st.caption("Les modifications ne sont pas automatiques — clique Sauvegarder après chaque édition.")

    # ── Performance des tickers associés aux thèses
    if not theses_df.empty:
        st.markdown("---")
        st.subheader("Performance des tickers de thèses")

        thesis_tickers = list(set(
            t.strip()
            for _, row in theses_df.iterrows()
            for t in str(row.get("Tickers", "")).split(",")
            if t.strip()
        ))
        avail_tt = [t for t in thesis_tickers if t in prices.columns]

        if avail_tt:
            perf_rows  = []
            _mom_cache = sector_cache.get("_momentum", {})
            for t in sorted(avail_tt):
                m = _mom_cache.get(t)
                if m:
                    perf_rows.append({"Ticker": t, "1M": m["1M"], "3M": m["3M"],
                                      "6M": m["6M"], "1A": m["1A"], "Prix actuel": m["Prix"]})
            st.dataframe(pd.DataFrame(perf_rows).set_index("Ticker"), use_container_width=True)
        else:
            st.info("Ajoute des tickers dans les thèses ci-dessus pour voir leur performance.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — BACKTEST (conservé en arrière-plan)
# ══════════════════════════════════════════════════════════════════════════════

with tab4:
    st.title("Backtest stratégie")
    st.caption("Conservé pour référence. La stratégie momentum/régime reste disponible ici.")

    import allocator as _alloc
    import regime    as _reg

    with st.expander("Paramètres stratégie", expanded=False):
        c1, c2, c3, c4, c5 = st.columns(5)
        top_n    = c1.slider("Top N (bull)",         1,  10, TOP_N_BULL)
        lookback = c2.slider("Lookback (j)",        10,  90, MOMENTUM_LOOKBACK, 5)
        buf      = c3.slider("Buffer SPY (%)",     0.0, 5.0, BUFFER * 100, 0.5) / 100
        fee      = c4.slider("Frais/side (%)",     0.0, 0.5, FEE_RATE * 100, 0.05) / 100
        initial  = c5.number_input("Capital (€)", 100, 100_000, _BT_DEFAULT_INITIAL, 100)
        gold_pct = st.slider("Gold (GLD) %", 0, 100, _BT_DEFAULT_GOLD_PCT, 5)

    _is_default = (top_n    == TOP_N_BULL        and
                   lookback == MOMENTUM_LOOKBACK  and
                   abs(buf - BUFFER)    < 1e-6    and
                   abs(fee - FEE_RATE)  < 1e-6    and
                   int(initial) == _BT_DEFAULT_INITIAL and
                   gold_pct == _BT_DEFAULT_GOLD_PCT)

    if _is_default and "_backtest" in sector_cache:
        results      = sector_cache["_backtest"]
        bt_figs      = sector_cache.get("_backtest_figs", {})
        _figs_cached = True
    else:
        results      = _run_backtest_custom(
            prices.index.max().isoformat(),
            top_n, lookback, buf, fee, int(initial), gold_pct)
        spy_sma_bt   = sector_cache.get("_spy", {}).get("sma200", pd.Series(dtype=float))
        bt_figs      = {p: _build_backtest_fig(d, p, spy_sma_bt) for p, d in results.items()}
        _figs_cached = False

    # Metrics summary
    st.subheader("Résumé des performances")
    rows = []
    for p, data in results.items():
        ms, mb = data["metrics_strat"], data["metrics_bnh"]
        rows.append({"Période": p,
                     "CAGR Strat":   ms["CAGR"],   "CAGR B&H":    mb["CAGR"],
                     "Sharpe Strat": ms["Sharpe"],  "Max DD Strat": ms["Max Drawdown"],
                     "Max DD B&H":   mb["Max Drawdown"]})
    st.dataframe(pd.DataFrame(rows).set_index("Période"), use_container_width=True)

    for p, data in results.items():
        st.subheader(p)
        if p in bt_figs:
            st.plotly_chart(bt_figs[p], use_container_width=True)
        trades = data["trades"]
        if not trades.empty:
            with st.expander(f"Log rebalancement ({len(trades)} événements)"):
                display = trades.copy()
                display["regime"]   = display["regime"].map(REGIME_LABEL)
                display["holdings"] = display["holdings"].apply(
                    lambda h: "  |  ".join(f"{t} {w:.0%}" for t, w in h.items())
                )
                st.dataframe(display[["regime", "holdings", "turnover", "cost_pct"]],
                             use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — CLASSEMENT
# ══════════════════════════════════════════════════════════════════════════════

with tab5:
    st.title("Classement des secteurs")
    st.caption("Performance des composites equal-weight, secteurs triés du meilleur au moins bon.")

    _rfigs = sector_cache.get("_ranking_figs", {})
    for period_label, _ in RANKING_PERIODS:
        st.subheader(period_label)
        if period_label in _rfigs:
            st.plotly_chart(_rfigs[period_label], use_container_width=True)
        else:
            st.warning("Données insuffisantes pour cette période.")
