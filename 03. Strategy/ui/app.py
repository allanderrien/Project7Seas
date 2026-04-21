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

from data_feed  import load_prices, load_volume, TICKERS, MOONSHOTS, TICKER_DESC
from regime     import compute_regime, regime_label
from swing        import (SWING_TICKERS, SWING_GROUPS, TICKER_ICONS,
                          build_price_chart, detect_rsi_glow_tickers,
                          load_trades, save_trades, TRADES_COLS)
from riskbenefit  import (DEFAULT_RB_TICKERS, fetch_targets_yf,
                          load_targets_cache, save_targets_cache,
                          compute_metrics, suggest_probabilities, compute_score,
                          is_fresh)
from worldmap     import build_world_map
from streamlit_folium import st_folium

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

@st.cache_data(show_spinner="Chargement des volumes...")
def get_volumes(do_refresh: bool):
    return load_volume(tickers=SWING_TICKERS, refresh=do_refresh)

# Sidebar — minimal
st.sidebar.title("🌊 Project 7 Seas")
st.sidebar.markdown("---")
refresh = st.sidebar.button("🔄 Rafraîchir les données")
prices  = get_prices(refresh)
volumes = get_volumes(refresh)
if not prices.empty:
    last_date = prices.index.max()
    st.sidebar.caption(f"Données au {last_date.strftime('%d %b %Y')}")

if st.sidebar.button("🔌 Tester stooq"):
    import requests
    try:
        _d2 = pd.Timestamp.today().strftime("%Y%m%d")
        _d1 = (pd.Timestamp.today() - pd.Timedelta(days=10)).strftime("%Y%m%d")
        r = requests.get(f"https://stooq.com/q/d/l/?s=spy.us&d1={_d1}&d2={_d2}&i=d", timeout=10)
        if r.status_code == 200 and "Date" in r.text:
            st.sidebar.success("✅ Stooq accessible")
        else:
            st.sidebar.error("❌ IP bloquée par stooq (rate-limit)")
    except Exception as e:
        st.sidebar.error(f"❌ Stooq inaccessible : {e}")

if st.sidebar.button("🔌 Tester yfinance"):
    import yfinance as yf
    try:
        _h = yf.Ticker("SPY").history(period="5d", auto_adjust=True)
        if not _h.empty and not _h["Close"].dropna().empty:
            st.sidebar.success("✅ yfinance accessible")
        else:
            st.sidebar.error("❌ yfinance : réponse vide")
    except Exception as e:
        st.sidebar.error(f"❌ yfinance inaccessible : {e}")

# ── Disk cache pour les composites sectoriels ──────────────────────────────────

_PRICES_CSV = os.path.join(os.path.dirname(__file__), "..", "data", "_prices.csv")
_CACHE_PKL  = os.path.join(os.path.dirname(__file__), "..", "data", "_computed_cache.pkl")

SECTOR_PERIODS = [
    ("12 derniers mois",   1),
    ("3 ans",              3),
    ("Historique complet", None),
]

RANKING_PERIODS = SECTOR_PERIODS  # même découpage


def _cache_valid() -> bool:
    return os.path.exists(_CACHE_PKL)


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

    # 4. Figures classement
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

# ── Tabs ──────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(["📡 Signal Macro", "🔭 Secteurs", "💡 Thèses", "🏆 Classement", "📈 Swing", "⚖️ Risque/Bénéfice", "🗺️ Carte"])

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
# TAB 4 — CLASSEMENT
# ══════════════════════════════════════════════════════════════════════════════

with tab4:
    st.title("Classement des secteurs")
    st.caption("Performance des composites equal-weight, secteurs triés du meilleur au moins bon.")

    _rfigs = sector_cache.get("_ranking_figs", {})
    for period_label, _ in RANKING_PERIODS:
        st.subheader(period_label)
        if period_label in _rfigs:
            st.plotly_chart(_rfigs[period_label], use_container_width=True)
        else:
            st.warning("Données insuffisantes pour cette période.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — SWING TRADING
# ══════════════════════════════════════════════════════════════════════════════

with tab5:
    st.title("📈 Swing Trading")
    st.caption("Apprentissage — signaux d'entrée sur NVDA, GOOGL, META")

    # ── Sélecteur ticker — cards groupées ────────────────────────────────────
    if "sw_ticker" not in st.session_state:
        st.session_state["sw_ticker"] = SWING_TICKERS[0]

    glow_tickers = detect_rsi_glow_tickers(prices)

    def _css_key(t):
        return t.replace(".", r"\.")
    glow_rules = "".join(
        f".st-key-sw_btn_{_css_key(t)} button {{"
        f"border:1px solid #ffd166 !important;"
        f"color:#ffd166 !important;"
        f"box-shadow:0 0 6px #ffd166,0 0 14px rgba(255,209,102,0.4);}}"
        for t in glow_tickers
    )
    st.markdown(f"<style>{glow_rules}</style>", unsafe_allow_html=True)

    groups_list = list(SWING_GROUPS.items())
    for row_start in range(0, len(groups_list), 2):
        cols = st.columns(2)
        for col_idx, (group_name, group_info) in enumerate(groups_list[row_start:row_start + 2]):
            with cols[col_idx]:
                color   = group_info["color"]
                tickers = group_info["tickers"]
                st.markdown(
                    f'<div style="border-left:4px solid {color};padding:2px 8px;'
                    f'margin-bottom:4px;font-weight:600;color:{color};font-size:0.82em">'
                    f'{group_name}</div>',
                    unsafe_allow_html=True,
                )
                COLS_PER_ROW = 4
                for chunk_start in range(0, len(tickers), COLS_PER_ROW):
                    chunk = tickers[chunk_start:chunk_start + COLS_PER_ROW]
                    btn_cols = st.columns(COLS_PER_ROW)
                    for i, t in enumerate(chunk):
                        icon   = TICKER_ICONS.get(t, "")
                        active = st.session_state["sw_ticker"] == t
                        glow  = t in glow_tickers
                        label = f"{'▶ ' if active else ''}{icon} {t}"
                        if btn_cols[i].button(label, key=f"sw_btn_{t}", use_container_width=True):
                            st.session_state["sw_ticker"] = t
                            st.rerun()
                        if glow:
                            btn_cols[i].markdown(
                                f'<div style="text-align:right;font-size:0.65em;'
                                f'color:#ffd166;margin-top:-10px;padding-right:4px;">'
                                f'J+{glow_tickers[t]}</div>',
                                unsafe_allow_html=True)

    ticker_sw = st.session_state["sw_ticker"]

    # ── Garde-fou ticker manquant ─────────────────────────────────────────────
    if ticker_sw not in prices.columns or prices[ticker_sw].dropna().empty:
        st.warning(f"**{ticker_sw}** n'est pas encore dans le cache de prix. Cliquez sur **Rafraîchir** dans la sidebar.")
    else:
        # ── Sélecteur période ─────────────────────────────────────────────────
        period_map = {90: "3 mois", 180: "6 mois", 365: "1 an", 730: "2 ans"}
        period_sw  = st.select_slider(
            "Période d'affichage",
            options=list(period_map.keys()),
            value=365,
            format_func=lambda x: period_map[x],
            key="sw_period"
        )

        # ── Graphique prix ────────────────────────────────────────────────────
        _name = TICKERS.get(ticker_sw, "")
        st.subheader(f"{ticker_sw}{' — ' + _name if _name else ''} — Prix, SMA50/200 & volume")
        if ticker_sw in TICKER_DESC:
            st.caption(TICKER_DESC[ticker_sw])
        fig_price = build_price_chart(ticker_sw, prices, volumes, period_sw)
        st.plotly_chart(fig_price, use_container_width=True)

        st.divider()

        # ── Journal de trades ─────────────────────────────────────────────────
        st.subheader("Journal de trades")
        trades_df = load_trades()

        with st.expander("➕ Nouveau trade", expanded=False):
            c1, c2, c3 = st.columns(3)
            t_date   = c1.date_input("Date", key="sw_t_date")
            t_ticker = c2.selectbox("Ticker", SWING_TICKERS, key="sw_t_ticker")
            t_dir    = c3.selectbox("Direction", ["Long", "Short"], key="sw_t_dir")
            c4, c5, c6 = st.columns(3)
            t_entry  = c4.number_input("Prix entrée ($)", min_value=0.0, step=0.01, key="sw_t_entry")
            t_stop   = c5.number_input("Stop ($)",        min_value=0.0, step=0.01, key="sw_t_stop")
            t_target = c6.number_input("Cible ($)",       min_value=0.0, step=0.01, key="sw_t_target")
            c7, c8   = st.columns([1, 3])
            t_fees   = c7.number_input("Frais %", min_value=0.0, max_value=5.0,
                                       value=0.0, step=0.05, format="%.2f", key="sw_t_fees")
            t_hypo   = c8.text_area("Hypothèse — pourquoi ce trade ?", key="sw_t_hypo", height=68)
            if st.button("Enregistrer", key="sw_save"):
                new_row = pd.DataFrame([[
                    str(t_date), t_ticker, t_dir,
                    f"{t_entry:.2f}", f"{t_stop:.2f}", f"{t_target:.2f}",
                    t_hypo, f"{t_fees:.2f}", "", "", ""
                ]], columns=TRADES_COLS)
                trades_df = pd.concat([trades_df, new_row], ignore_index=True)
                save_trades(trades_df)
                st.success("Trade enregistré.")
                st.rerun()

        # ── Enregistrer une sortie ─────────────────────────────────────────────
        open_trades = trades_df[trades_df["Prix sortie"].isin(["", "nan", "None"])
                                | trades_df["Prix sortie"].isna()] if not trades_df.empty else pd.DataFrame()
        if not open_trades.empty:
            with st.expander("📤 Enregistrer une sortie", expanded=False):
                labels = [
                    f"{row['Date']} · {row['Ticker']} {row['Direction']} @ {row['Prix entrée']}"
                    for _, row in open_trades.iterrows()
                ]
                chosen = st.selectbox("Position ouverte", labels, key="sw_exit_select")
                chosen_idx = open_trades.index[labels.index(chosen)]

                cx1, cx2 = st.columns(2)
                exit_price = cx1.number_input("Prix de sortie ($)", min_value=0.0,
                                              step=0.01, key="sw_exit_price")
                exit_notes = cx2.text_input("Notes", key="sw_exit_notes")

                # Aperçu P&L
                if exit_price > 0:
                    try:
                        entry   = float(trades_df.at[chosen_idx, "Prix entrée"])
                        fees    = float(trades_df.at[chosen_idx, "Frais %"] or 0)
                        direct  = trades_df.at[chosen_idx, "Direction"]
                        raw_pnl = ((exit_price / entry - 1) * 100 if direct == "Long"
                                   else (1 - exit_price / entry) * 100)
                        net_pnl = raw_pnl - fees
                        color   = "#06d6a0" if net_pnl >= 0 else "#e63946"
                        st.markdown(
                            f"P&L net : <span style='color:{color};font-weight:700'>"
                            f"{net_pnl:+.2f}%</span> (brut {raw_pnl:+.2f}% − frais {fees:.2f}%)",
                            unsafe_allow_html=True)
                    except (ValueError, ZeroDivisionError):
                        pass

                if st.button("Enregistrer la sortie", key="sw_exit_save"):
                    try:
                        entry   = float(trades_df.at[chosen_idx, "Prix entrée"])
                        fees    = float(trades_df.at[chosen_idx, "Frais %"] or 0)
                        direct  = trades_df.at[chosen_idx, "Direction"]
                        raw_pnl = ((exit_price / entry - 1) * 100 if direct == "Long"
                                   else (1 - exit_price / entry) * 100)
                        net_pnl = raw_pnl - fees
                        trades_df.at[chosen_idx, "Prix sortie"] = f"{exit_price:.2f}"
                        trades_df.at[chosen_idx, "P&L %"]       = f"{net_pnl:+.2f}"
                        trades_df.at[chosen_idx, "Notes"]        = exit_notes
                        save_trades(trades_df)
                        st.success(f"Sortie enregistrée — P&L net : {net_pnl:+.2f}%")
                        st.rerun()
                    except (ValueError, ZeroDivisionError) as e:
                        st.error(f"Erreur de calcul : {e}")

        if not trades_df.empty:
            st.dataframe(trades_df, use_container_width=True, hide_index=True)
        else:
            st.info("Aucun trade enregistré. Utilisez le formulaire ci-dessus pour commencer.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 6 — RISQUE / BÉNÉFICE
# ══════════════════════════════════════════════════════════════════════════════

with tab6:
    st.title("⚖️ Analyse Risque / Bénéfice")
    st.caption("Targets analystes 12 mois — méthode standardisée. Données éditables manuellement.")

    # ── Sélection tickers ─────────────────────────────────────────────────────
    all_known = DEFAULT_RB_TICKERS + [t for t in prices.columns if t not in DEFAULT_RB_TICKERS]
    tickers_rb = st.multiselect("Tickers à analyser", options=all_known,
                                default=DEFAULT_RB_TICKERS, key="rb_tickers")

    if len(tickers_rb) > 8:
        st.warning(f"{len(tickers_rb)} tickers sélectionnés — Yahoo Finance rate-limite au-delà de ~8. Réduire la sélection ou patienter entre les fetches.")
    if st.button("🔄 Récupérer targets (Yahoo Finance)", key="rb_fetch"):
        with st.spinner("Récupération Yahoo Finance…"):
            existing = load_targets_cache()
            to_fetch = [t for t in tickers_rb if not is_fresh(existing.get(t, {}))]
            skip     = [t for t in tickers_rb if t not in to_fetch]
            if skip:
                st.toast(f"Cache valide (<14j) : {', '.join(skip)} — ignorés.")
            fetched = fetch_targets_yf(to_fetch) if to_fetch else {}
            # Compléter le prix depuis _prices.csv si yfinance ne l'a pas
            for t, d in fetched.items():
                if d["price"] is None and t in prices.columns:
                    s = prices[t].dropna()
                    if not s.empty:
                        d["price"] = round(float(s.iloc[-1]), 2)
            existing.update(fetched)        # fusionner : nouveaux écrasent les périmés
            save_targets_cache(existing)
            st.session_state["rb_raw"] = existing
            rate_limited = [t for t, d in fetched.items() if "Rate limit" in (d.get("source") or "")]
            if rate_limited:
                st.warning(f"Rate limit Yahoo Finance sur : {', '.join(rate_limited)}. Réessayer dans quelques minutes.")
            else:
                st.success("Targets récupérés.")

    # Charger depuis session_state ou cache disque
    if "rb_raw" not in st.session_state:
        _cached = load_targets_cache()
        if _cached:
            st.session_state["rb_raw"] = _cached

    if "rb_raw" not in st.session_state:
        st.info("Cliquez sur **Récupérer targets** pour commencer.")
    else:
        raw = st.session_state["rb_raw"]

        # ── Table éditable ────────────────────────────────────────────────────
        st.subheader("Données de référence")
        st.caption("Toutes les valeurs sont éditables. Double-cliquer pour modifier.")

        rows_rb = []
        for t in tickers_rb:
            d = raw.get(t, {"price": None, "low": None, "mean": None,
                            "high": None, "source": "Manuel"})
            rows_rb.append({
                "Ticker":       t,
                "Prix ($)":     d.get("price"),
                "Target Low":   d.get("low"),
                "Target Moyen": d.get("mean"),
                "Target High":  d.get("high"),
                "Source":       d.get("source", "Manuel"),
            })

        edited_rb = st.data_editor(
            pd.DataFrame(rows_rb),
            column_config={
                "Ticker":       st.column_config.TextColumn(disabled=True),
                "Prix ($)":     st.column_config.NumberColumn(format="%.2f", min_value=0.0),
                "Target Low":   st.column_config.NumberColumn(format="%.2f", min_value=0.0),
                "Target Moyen": st.column_config.NumberColumn(format="%.2f", min_value=0.0),
                "Target High":  st.column_config.NumberColumn(format="%.2f", min_value=0.0),
                "Source":       st.column_config.TextColumn(disabled=True),
            },
            hide_index=True,
            use_container_width=True,
            key="rb_editor",
        )

        # ── Probabilités ──────────────────────────────────────────────────────
        st.subheader("Probabilités")
        st.caption("P(↑) + P(↓) ≤ 100 — P(→) est calculée automatiquement. "
                   "La suggestion est basée sur la dispersion des targets.")

        # En-tête
        _h = st.columns([1.2, 1, 1, 1, 2.5])
        for col, label in zip(_h, ["**Ticker**", "**P(↑) %**", "**P(↓) %**",
                                    "**P(→) %**", "**Suggestion / dispersion**"]):
            col.markdown(label)

        proba_inputs_rb = {}
        valid_rb = []
        for _, row in edited_rb.iterrows():
            t = row["Ticker"]
            p, lo, me, hi = (row["Prix ($)"], row["Target Low"],
                             row["Target Moyen"], row["Target High"])
            if not all(v is not None and not pd.isna(v) and float(v) > 0
                       for v in [p, lo, hi]):
                continue
            me_val = float(me) if (me is not None and not pd.isna(me)) else (float(lo) + float(hi)) / 2
            m_rb   = compute_metrics(float(p), float(lo), me_val, float(hi))
            p_bull_s, _, p_bear_s = suggest_probabilities(m_rb["dispersion"])

            cols_rb = st.columns([1.2, 1, 1, 1, 2.5])
            cols_rb[0].markdown(f"**{t}**")
            p_bull_in = cols_rb[1].number_input(
                "", min_value=0, max_value=100, value=int(p_bull_s * 100),
                step=5, key=f"rb_bull_{t}", label_visibility="collapsed") / 100
            p_bear_in = cols_rb[2].number_input(
                "", min_value=0, max_value=100, value=int(p_bear_s * 100),
                step=5, key=f"rb_bear_{t}", label_visibility="collapsed") / 100
            p_neu_in  = max(round(1 - p_bull_in - p_bear_in, 2), 0.0)
            cols_rb[3].metric("", f"{p_neu_in * 100:.0f}%")
            cols_rb[4].caption(
                f"Disp. {m_rb['dispersion']*100:.0f}% → "
                f"sugg. {int(p_bull_s*100)} / {int(round(1-p_bull_s-p_bear_s,2)*100)} / {int(p_bear_s*100)}"
            )
            proba_inputs_rb[t] = (p_bull_in, p_neu_in, p_bear_in, m_rb)
            valid_rb.append(t)

        # ── Calculer ──────────────────────────────────────────────────────────
        st.divider()
        if st.button("📊 Calculer", key="rb_calc", type="primary") and valid_rb:
            results_rb = []
            for _, row in edited_rb.iterrows():
                t = row["Ticker"]
                if t not in proba_inputs_rb:
                    continue
                p    = float(row["Prix ($)"])
                lo   = float(row["Target Low"])
                hi   = float(row["Target High"])
                me   = (float(row["Target Moyen"])
                        if row["Target Moyen"] is not None and not pd.isna(row["Target Moyen"])
                        else (lo + hi) / 2)
                p_bull, p_neu, p_bear, m_rb = proba_inputs_rb[t]
                s_rb = compute_score(m_rb["upside"], m_rb["downside"],
                                     m_rb["dispersion"], p_bull, p_bear)
                results_rb.append({
                    "ticker": t, "price": p, "low": lo, "mean": me, "high": hi,
                    "source": row["Source"],
                    **m_rb,
                    "p_bull": p_bull, "p_neu": p_neu, "p_bear": p_bear,
                    **s_rb,
                })
            st.session_state["rb_results"] = results_rb

        # ── Résultats ─────────────────────────────────────────────────────────
        if st.session_state.get("rb_results"):
            results_rb = sorted(st.session_state["rb_results"],
                                key=lambda x: x["score"], reverse=True)

            st.subheader("Résultats")

            # Tableau récap
            st.dataframe(pd.DataFrame([{
                "Ticker":     r["ticker"],
                "Prix":       f"${r['price']:.2f}",
                "Upside":     f"{r['upside']*100:.1f}%",
                "Downside":   f"{r['downside']*100:.1f}%",
                "Dispersion": f"{r['dispersion']*100:.0f}%",
                "P(↑/→/↓)":  f"{r['p_bull']*100:.0f}/{r['p_neu']*100:.0f}/{r['p_bear']*100:.0f}",
                "Espérance":  f"{r['esperance']*100:.1f}%",
                "Ratio B/R":  f"{r['ratio']:.2f}×",
                "Score":      f"{r['score']*100:.2f}",
            } for r in results_rb]), hide_index=True, use_container_width=True)

            # Détail par ticker
            st.subheader("Analyse détaillée")

            def _disp_comment(d):
                if d < 0.20: return "Forte convergence des analystes."
                if d < 0.40: return "Convergence modérée."
                if d < 0.60: return "Incertitude importante."
                return "Forte incertitude — dispersion très élevée."

            def _asym_comment(score):
                if score > 0.02: return "✅ Asymétrie favorable."
                if score > 0:    return "⚠️ Asymétrie modérée — attendre un meilleur point d'entrée."
                return "❌ Asymétrie défavorable — risque non compensé."

            for i, r in enumerate(results_rb, 1):
                with st.expander(f"**#{i} {r['ticker']}** — Score {r['score']*100:.2f}"):
                    st.markdown(f"""
**Source :** {r['source']}
**Prix actuel :** ${r['price']:.2f} &nbsp;|&nbsp; Low : ${r['low']:.2f} &nbsp;|&nbsp; Moyen : ${r['mean']:.2f} &nbsp;|&nbsp; High : ${r['high']:.2f}

**Upside :** {r['upside']*100:.1f}% &nbsp;|&nbsp; **Downside :** {r['downside']*100:.1f}% &nbsp;|&nbsp; **Dispersion :** {r['dispersion']*100:.0f}%
{_disp_comment(r['dispersion'])}

**Probabilités :** P(↑) {r['p_bull']*100:.0f}% / P(→) {r['p_neu']*100:.0f}% / P(↓) {r['p_bear']*100:.0f}%

**Espérance :** {r['esperance']*100:.1f}% &nbsp;|&nbsp; **Ratio B/R :** {r['ratio']:.2f}× &nbsp;|&nbsp; **Score :** {r['score']*100:.2f}

*{_asym_comment(r['score'])}*
""")

            # Classement final
            st.subheader("Classement")
            for i, r in enumerate(results_rb, 1):
                color = ("#06d6a0" if r["score"] > 0.02
                         else "#ffd166" if r["score"] > 0 else "#e63946")
                st.markdown(
                    f"<span style='color:{color}'>**#{i} {r['ticker']}**</span>"
                    f" — Score **{r['score']*100:.2f}** "
                    f"| Upside {r['upside']*100:.1f}% / Downside {r['downside']*100:.1f}% "
                    f"| Ratio {r['ratio']:.2f}×",
                    unsafe_allow_html=True
                )

# ══════════════════════════════════════════════════════════════════════════════
# TAB 7 — CARTE GÉOGRAPHIQUE
# ══════════════════════════════════════════════════════════════════════════════

with tab7:
    st.title("Carte — Courtiers & Sièges sociaux")
    st.caption(
        "🏦 Marqueurs carrés = entités dépositaires (courtiers). "
        "🔵 Cercles colorés = sièges sociaux par secteur. "
        "Cliquer sur un marqueur pour les détails. "
        "Toggles en haut à droite pour afficher/masquer chaque couche."
    )

    world_map = build_world_map()
    st_folium(world_map, use_container_width=True, height=620, returned_objects=[])
