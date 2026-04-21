"""
swing.py  —  Signal computation and chart building for the Swing Trading tab.

5 automated signals (0 or 1 each, max score = 5):
  S1 — Régime macro : SPY strictement au-dessus SMA200 (+1%)
  S2 — Pente SMA50 SPY positive sur 20 jours
  S3 — Ticker au-dessus de sa SMA200
  S4 — RSI(14) en zone d'entrée (30–60) : pas en freefall, pas suracheté
  S5 — Volume 5j > moyenne 20j : présence acheteurs

+ 1 signal manuel dans l'UI : catalyseur proche identifié

Score ≥ 4/6 → entrée possible
Score 2–3   → attendre
Score < 2   → rester en dehors
"""

import os
import json
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── Constantes ────────────────────────────────────────────────────────────────

TICKER_ICONS = {
    "NVDA": "🎮", "MSFT": "🪟", "GOOGL": "🔍", "META": "👥", "AAPL": "🍎",
    "TSM": "🏭", "ORCL": "🗄️",
    "LLY": "💊", "VKTX": "🧬", "BEAM": "✂️", "CATX": "☢️",
    "CAT": "🚜", "DE": "🌾", "URI": "🏗️", "HDMG.DE": "🧱",
    "RHM.DE": "🛡️", "HAG.DE": "🎯", "HO.PA": "✈️", "LDO.MI": "🚁",
    "SMR": "⚛️", "CCJ": "⛏️", "NNE": "⚡", "OKLO": "🔋", "ENPH": "☀️",
    "CL": "🪥", "COST": "🛒", "UBER": "🚗",
    "BTC-USD": "₿", "ETH-USD": "💎", "SOL-USD": "🌊",
    "GLD": "🥇", "SLV": "🥈",
    "RKLB": "🚀", "LUNR": "🌙", "ASTS": "📡",
    "RGTI": "🔬", "QBTS": "⚛️", "IONQ": "💫",
    "SOUN": "🎤", "AMPX": "🔋", "JMIA": "🛍️", "TCEHY": "🀄", "NURO": "🧠",
    "BDMD": "🔬",
}

SWING_GROUPS = {
    "🤖 IA / Tech":           {"tickers": ["NVDA","MSFT","GOOGL","META","AAPL","TSM","ORCL"], "color": "#3a86ff"},
    "💊 Santé / Biotech":     {"tickers": ["LLY","VKTX","BEAM","CATX","BDMD"],             "color": "#ffd93d"},
    "🏗️ Infrastructure":      {"tickers": ["CAT","DE","URI","HDMG.DE"],                      "color": "#6a4c93"},
    "🛡️ Défense":             {"tickers": ["RHM.DE","HAG.DE","HO.PA","LDO.MI"],             "color": "#4ecdc4"},
    "⚛️ Nucléaire / Énergie": {"tickers": ["SMR","CCJ","NNE","OKLO","ENPH"],                "color": "#06d6a0"},
    "🛒 Conso / Services":    {"tickers": ["CL","COST","UBER"],                              "color": "#aaaaaa"},
    "₿ Crypto":               {"tickers": ["BTC-USD","ETH-USD","SOL-USD"],                  "color": "#ff9f1c"},
    "🥇 Métaux":              {"tickers": ["GLD","SLV"],                                     "color": "#f5c542"},
    "🚀 Spatial":             {"tickers": ["RKLB","LUNR","ASTS"],                            "color": "#ff6b6b"},
    "🔬 Quantum":             {"tickers": ["RGTI","QBTS","IONQ"],                            "color": "#b185db"},
    "🌐 Spéculatif":          {"tickers": ["SOUN","AMPX","JMIA","TCEHY","NURO"],            "color": "#e63946"},
}

SWING_TICKERS     = [
    # Core Tech / IA
    "NVDA", "MSFT", "GOOGL", "META", "AAPL", "TSM", "ORCL",
    # Thématiques qualité
    "LLY", "CAT", "DE", "URI", "CL", "COST", "UBER", "ENPH",
    # Nucléaire
    "SMR", "CCJ", "NNE", "OKLO",
    # EU défense
    "RHM.DE", "HAG.DE", "HO.PA", "LDO.MI", "HDMG.DE",
    # Crypto
    "BTC-USD", "ETH-USD", "SOL-USD",
    # Métaux
    "GLD", "SLV",
    # Moonshots
    "RKLB", "LUNR", "ASTS",
    "RGTI", "QBTS", "IONQ",
    "VKTX", "BEAM", "CATX", "BDMD",
    "SOUN", "AMPX", "JMIA", "TCEHY", "NURO",
]
TRADES_PATH       = os.path.join(os.path.dirname(__file__), "data", "_trades.json")
CATALYSTS_PATH    = os.path.join(os.path.dirname(__file__), "data", "_catalysts.json")
TRADES_COLS       = ["Date", "Ticker", "Direction", "Prix entrée", "Stop",
                     "Cible", "Hypothèse", "Frais %", "Prix sortie", "P&L %", "Notes"]

CATALYST_COLORS = {
    "Earnings":    "#06d6a0",
    "Conférence":  "#3a86ff",
    "Macro":       "#ff9f1c",
    "Géopolitique":"#e63946",
    "Sectorielle": "#b185db",
    "Corporate":   "#aaaaaa",
}

RSI_PERIOD    = 14
GLOW_TICKERS  = ["BEAM", "META", "DE", "CAT", "BTC-USD", "ETH-USD", "SOL-USD",
                  "URI", "RKLB", "CCJ", "NNE", "LUNR", "ASTS"]   # tickers pour lesquels le signal RSI↗SMA14 fait briller la card
SMA_SHORT     = 50
SMA_LONG      = 200
SMA_SHIFT     = 25   # décalage SMA50 vers la gauche — pente des 25 derniers jours pour combler
VOL_SHORT     = 5
VOL_LONG      = 20
SPY_SLOPE_WIN = 20   # jours pour mesurer la pente SMA50

_DARK_BG   = "#1e2130"
_DARK_GRID = "#2e3450"
_DARK_TEXT = "#c9d1d9"


# ── Calculs ───────────────────────────────────────────────────────────────────

def detect_rsi_glow_tickers(prices: pd.DataFrame, lookback: int = 15,
                            tickers: list = None) -> dict:
    """
    Retourne {ticker: jours_depuis_signal} pour les tickers où RSI(14) a croisé
    sa SMA14 à la hausse depuis une zone de survente (RSI < 45),
    dans les `lookback` derniers jours.
    Seuls les tickers de `tickers` (défaut : GLOW_TICKERS) sont évalués.
    """
    candidates = tickers if tickers is not None else GLOW_TICKERS
    result = {}
    last_date = prices.index[-1]
    for ticker in candidates:
        if ticker not in prices.columns:
            continue
        p = prices[ticker].dropna()
        if len(p) < 60:
            continue
        rsi     = compute_rsi(p)
        rsi_sma = rsi.rolling(14).mean()

        rsi_w     = rsi.iloc[-lookback:]
        rsi_sma_w = rsi_sma.iloc[-lookback:]
        rsi_prev  = rsi.shift(1).iloc[-lookback:]
        rsi_sma_p = rsi_sma.shift(1).iloc[-lookback:]

        crossover = (
            (rsi_prev < rsi_sma_p) &
            (rsi_w >= rsi_sma_w) &
            (rsi_w < 45)
        )
        hits = crossover[crossover].index
        if len(hits) > 0:
            days = (last_date - hits[-1]).days
            result[ticker] = days
    return result


def compute_rsi(series: pd.Series, window: int = RSI_PERIOD) -> pd.Series:
    delta = series.diff()
    gain  = delta.clip(lower=0).rolling(window).mean()
    loss  = (-delta.clip(upper=0)).rolling(window).mean()
    rs    = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def compute_score_series(prices: pd.DataFrame, volumes: pd.DataFrame) -> dict:
    """
    Calcule la série de scores (0–5) pour chaque ticker sur l'historique complet.
    Retourne dict : ticker → pd.Series[int]
    """
    spy        = prices["SPY"]
    spy_sma200 = spy.rolling(SMA_LONG).mean()
    spy_sma50  = spy.rolling(SMA_SHORT).mean()

    result = {}
    for ticker in SWING_TICKERS:
        if ticker not in prices.columns:
            continue
        p = prices[ticker].dropna()

        # S1 : régime macro BULL (SPY > SMA200 + 1%)
        s1 = (spy > spy_sma200 * 1.01).astype(int)

        # S2 : pente SMA50 SPY positive
        s2 = (spy_sma50 > spy_sma50.shift(SPY_SLOPE_WIN)).astype(int)

        # S3 : ticker au-dessus SMA200
        sma200_t = p.rolling(SMA_LONG).mean()
        s3 = (p > sma200_t).astype(int)

        # S4 : RSI en zone d'entrée (30–60)
        rsi = compute_rsi(p)
        s4  = ((rsi >= 30) & (rsi <= 60)).astype(int)

        # S5 : volume récent > moyenne 20j
        if ticker in volumes.columns and not volumes[ticker].dropna().empty:
            vol      = volumes[ticker].reindex(p.index)
            vol_avg5  = vol.rolling(VOL_SHORT).mean()
            vol_avg20 = vol.rolling(VOL_LONG).mean()
            s5 = (vol_avg5 > vol_avg20).astype(int)
        else:
            s5 = pd.Series(0, index=p.index)

        idx   = p.index
        score = (
            s1.reindex(idx).fillna(0) +
            s2.reindex(idx).fillna(0) +
            s3 +
            s4 +
            s5.reindex(idx).fillna(0)
        ).astype(int)

        result[ticker] = score

    return result


def get_current_signals(prices: pd.DataFrame, volumes: pd.DataFrame,
                        ticker: str) -> list:
    """
    Retourne la liste des 5 signaux pour l'UI (état courant).
    Chaque élément : {label, value (bool), detail}
    """
    if ticker not in prices.columns or prices[ticker].dropna().empty:
        return []

    spy        = prices["SPY"]
    spy_sma200 = spy.rolling(SMA_LONG).mean()
    spy_sma50  = spy.rolling(SMA_SHORT).mean()

    p        = prices[ticker].dropna()
    sma200_t = p.rolling(SMA_LONG).mean()
    rsi      = compute_rsi(p)

    spy_last        = spy.iloc[-1]
    spy_sma200_last = spy_sma200.iloc[-1]
    spy_sma50_last  = spy_sma50.iloc[-1]
    spy_sma50_prev  = (spy_sma50.iloc[-SPY_SLOPE_WIN - 1]
                       if len(spy_sma50) > SPY_SLOPE_WIN else spy_sma50.iloc[0])

    p_last      = p.iloc[-1]
    sma200_last = sma200_t.iloc[-1]
    rsi_last    = rsi.iloc[-1]

    signals = [
        {
            "label":  "Régime macro (SPY > SMA200)",
            "value":  spy_last > spy_sma200_last * 1.01,
            "detail": (f"SPY ${spy_last:.0f} vs SMA200 ${spy_sma200_last:.0f} "
                       f"({(spy_last / spy_sma200_last - 1) * 100:+.1f}%)"),
        },
        {
            "label":  "Pente SMA50 SPY positive (20j)",
            "value":  spy_sma50_last > spy_sma50_prev,
            "detail": (f"SMA50 actuelle ${spy_sma50_last:.0f} "
                       f"vs il y a 20j ${spy_sma50_prev:.0f}"),
        },
        {
            "label":  f"{ticker} au-dessus SMA200",
            "value":  p_last > sma200_last,
            "detail": (f"${p_last:.2f} vs SMA200 ${sma200_last:.2f} "
                       f"({(p_last / sma200_last - 1) * 100:+.1f}%)"),
        },
        {
            "label":  "RSI(14) en zone d'entrée (30–60)",
            "value":  30 <= rsi_last <= 60,
            "detail": f"RSI = {rsi_last:.1f}",
        },
    ]

    if ticker in volumes.columns and not volumes[ticker].dropna().empty:
        vol       = volumes[ticker].dropna()
        vol_avg5  = vol.rolling(VOL_SHORT).mean()
        vol_avg20 = vol.rolling(VOL_LONG).mean()
        vs = vol_avg5.iloc[-1]
        va = vol_avg20.iloc[-1]
        signals.append({
            "label":  "Volume 5j > moyenne 20j",
            "value":  vs > va,
            "detail": f"Moy. 5j : {vs / 1e6:.1f}M  —  Moy. 20j : {va / 1e6:.1f}M",
        })
    else:
        signals.append({
            "label":  "Volume 5j > moyenne 20j",
            "value":  False,
            "detail": "Données volume non disponibles",
        })

    return signals


# ── Graphiques ────────────────────────────────────────────────────────────────

def _add_catalyst_markers(fig, catalysts: list, row: int = 1):
    """Ajoute les lignes verticales de catalyseurs sur une figure."""
    for c in catalysts:
        color = CATALYST_COLORS.get(c["type"], "#ffffff")
        fig.add_vline(x=c["dt"], line_width=1.2, line_dash="dot",
                      line_color=color, opacity=0.7, row=row, col=1)
        fig.add_annotation(
            x=c["dt"], y=1, yref="paper",
            text=f"<b>{c['type'][0]}</b>",
            showarrow=False, font=dict(size=9, color=color),
            bgcolor="rgba(0,0,0,0.5)", borderpad=2,
            xanchor="center", yanchor="top",
        )


def build_price_chart(ticker: str, prices: pd.DataFrame, volumes: pd.DataFrame,
                      period_days: int = 365, catalysts: list = None) -> go.Figure:
    """Prix + SMA50 décalée -25j + SMA200 + (volume en barres & RSI en ligne sur axe secondaire)."""
    p_full      = prices[ticker].dropna()
    sma50_full  = p_full.rolling(SMA_SHORT).mean()
    sma200_full = p_full.rolling(SMA_LONG).mean()

    p      = p_full.iloc[-period_days:]
    sma200 = sma200_full.iloc[-period_days:]
    rsi    = compute_rsi(p_full).iloc[-period_days:]

    # ── SMA50 décalée de SMA_SHIFT jours vers la gauche + projection ──────────
    # Principe : sma50 est une moyenne sur 50j → son "centre de gravité" est à J-25.
    # On l'affiche à sa date réelle (J-25) plutôt qu'à J → décalage visuel vers la gauche.
    # Les SMA_SHIFT derniers jours sont comblés par extrapolation quadratique :
    #   Phase 1 (j1–5)  : pente moyenne 5j + prolongation de la variation de pente 5j.
    #   Phase 2 (j6–25) : linéaire avec la pente atteinte en fin de phase 1.
    #   La projection est ancrée sur last_val pour garantir la continuité.
    SHIFT = SMA_SHIFT
    n     = len(sma50_full)
    sv    = sma50_full.values.astype(float)

    sma50_nonan = sma50_full.dropna()
    last_val    = float(sma50_nonan.iloc[-1])

    # Partie historique : à la date d[i] on affiche sma50[i + SHIFT]
    hist_vals = np.full(n, np.nan)
    if n > SHIFT:
        hist_vals[:n - SHIFT] = sv[SHIFT:n]

    # Partie projetée — fenêtre de moyenne décroissante, toutes ancrées sur j0 :
    #   à j-25+k : SMA(max(50 - 2k, 5)) calculée sur les derniers prix réels
    #   → à j-25 on affiche SMA50(j0) = last_val (continuité garantie)
    #   → à j0   on affiche SMA5(j0)  (momentum récent)
    SMA_END   = 5
    STEP      = (SMA_SHORT - SMA_END) / (SHIFT - SMA_END)   # 45/20 = 2.25 → plancher SMA5 à j-5
    prices_arr = p_full.values.astype(float)
    proj_vals = np.full(n, np.nan)
    if n > SHIFT and len(prices_arr) >= SMA_SHORT:
        proj_vals[n - SHIFT - 1] = last_val    # jonction continue
        for k in range(SHIFT):
            win = max(int(round(SMA_SHORT - STEP * k)), SMA_END)
            proj_vals[n - SHIFT + k] = float(np.mean(prices_arr[-win:]))

    sma50_hist = pd.Series(hist_vals, index=sma50_full.index).iloc[-period_days:]
    sma50_proj = pd.Series(proj_vals, index=sma50_full.index).iloc[-period_days:]

    has_vol = (ticker in volumes.columns and
               not volumes[ticker].dropna().empty)
    n_rows      = 2 if has_vol else 1
    row_heights = [0.70, 0.30] if has_vol else [1.0]

    specs = [[{}], [{"secondary_y": True}]] if has_vol else [[{}]]
    fig   = make_subplots(rows=n_rows, cols=1, shared_xaxes=True,
                          row_heights=row_heights, vertical_spacing=0.03,
                          specs=specs)

    # ── Graphique prix ────────────────────────────────────────────────────────
    fig.add_trace(go.Scatter(x=p.index, y=p.values, name="Prix",
                             line=dict(color="#3a86ff", width=2)), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=sma50_hist.index, y=sma50_hist.values,
        name=f"SMA{SMA_SHORT} (décalée -{SHIFT}j)",
        line=dict(color="#ff9f1c", width=1.5, dash="dot")),
        row=1, col=1)
    fig.add_trace(go.Scatter(
        x=sma50_proj.index, y=sma50_proj.values,
        name=f"SMA{SMA_SHORT} projection",
        line=dict(color="#ff9f1c", width=1.5, dash="dot"),
        opacity=0.45, showlegend=False),
        row=1, col=1)
    fig.add_trace(go.Scatter(x=sma200.index, y=sma200.values, name=f"SMA{SMA_LONG}",
                             line=dict(color="#e63946", width=1.5, dash="dash")),
                  row=1, col=1)

    # ── Volume + RSI sur le même sous-graphique ───────────────────────────────
    if has_vol:
        vol     = volumes[ticker].reindex(p.index)
        vol_avg = volumes[ticker].dropna().rolling(VOL_LONG).mean().reindex(p.index)
        colors  = [
            "#3a86ff" if (not pd.isna(v) and not pd.isna(a) and v >= a) else "#e63946"
            for v, a in zip(vol, vol_avg)
        ]
        fig.add_trace(go.Bar(x=vol.index, y=vol.values, name="Volume",
                             marker_color=colors, opacity=0.45),
                      row=2, col=1, secondary_y=False)

        # RSI sur axe secondaire (0–100)
        rsi_sma14 = rsi.rolling(14).mean()
        fig.add_trace(go.Scatter(x=rsi.index, y=rsi.values, name="RSI(14)",
                                 line=dict(color="#a8dadc", width=1.5)),
                      row=2, col=1, secondary_y=True)
        fig.add_trace(go.Scatter(x=rsi_sma14.index, y=rsi_sma14.values,
                                 name="SMA14(RSI)",
                                 line=dict(color="#ff9f1c", width=1.2, dash="dot")),
                      row=2, col=1, secondary_y=True)
        # Zones 30 / 60
        for level, color in [(30, "#06d6a0"), (60, "#ffd166")]:
            fig.add_hline(y=level, line_dash="dot", line_color=color,
                          line_width=1, opacity=0.6,
                          row=2, col=1, secondary_y=True)

        fig.update_yaxes(title_text="Volume", row=2, col=1, secondary_y=False,
                         showgrid=True, gridcolor=_DARK_GRID, zeroline=False)
        fig.update_yaxes(title_text="RSI", row=2, col=1, secondary_y=True,
                         range=[0, 100], showgrid=False, zeroline=False,
                         tickvals=[30, 50, 60, 70],
                         color="#a8dadc")

    # ── Marqueurs catalyseurs ─────────────────────────────────────────────────
    if catalysts:
        _add_catalyst_markers(fig, catalysts, row=1)

    fig.update_layout(
        height=500, hovermode="x unified", showlegend=True,
        legend=dict(orientation="h", y=1.02),
        margin=dict(l=0, r=50, t=30, b=0),
        plot_bgcolor=_DARK_BG, paper_bgcolor=_DARK_BG,
        font=dict(color=_DARK_TEXT),
    )
    fig.update_xaxes(showgrid=True, gridcolor=_DARK_GRID, zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor=_DARK_GRID, zeroline=False,
                     row=1, col=1)
    return fig


def build_score_chart(ticker: str, score_series: pd.Series, prices: pd.DataFrame,
                      period_days: int = 365, catalysts: list = None) -> go.Figure:
    """Score historique (0–5) superposé au prix normalisé — validation rétrospective."""
    score  = score_series.iloc[-period_days:]
    p      = prices[ticker].dropna().iloc[-period_days:]
    p_norm = p / p.iloc[0] * 100 if len(p) > 0 else p

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Scatter(x=p_norm.index, y=p_norm.values,
                   name=f"{ticker} (base 100)",
                   line=dict(color="#3a86ff", width=1.5), opacity=0.45),
        secondary_y=False)

    fig.add_trace(
        go.Scatter(x=score.index, y=score.values, name="Score (0–5)",
                   line=dict(color="#ffd166", width=2),
                   fill="tozeroy", fillcolor="rgba(255,209,102,0.12)"),
        secondary_y=True)

    fig.add_hline(y=3, line_dash="dot", line_color="#06d6a0", line_width=1.2,
                  secondary_y=True,
                  annotation_text=" Seuil ≥ 3",
                  annotation_font_color="#06d6a0",
                  annotation_position="top right")

    # ── Marqueurs catalyseurs ─────────────────────────────────────────────────
    if catalysts:
        for c in catalysts:
            color = CATALYST_COLORS.get(c["type"], "#ffffff")
            fig.add_vline(x=c["dt"], line_width=1, line_dash="dot",
                          line_color=color, opacity=0.6)

    fig.update_layout(
        height=280, hovermode="x unified",
        legend=dict(orientation="h", y=1.08),
        margin=dict(l=0, r=60, t=30, b=0),
        plot_bgcolor=_DARK_BG, paper_bgcolor=_DARK_BG,
        font=dict(color=_DARK_TEXT),
    )
    fig.update_xaxes(showgrid=True, gridcolor=_DARK_GRID, zeroline=False)
    fig.update_yaxes(title_text="Prix (base 100)", secondary_y=False,
                     gridcolor=_DARK_GRID, zeroline=False)
    fig.update_yaxes(title_text="Score", secondary_y=True,
                     range=[0, 6], gridcolor=_DARK_GRID, zeroline=False)
    return fig


# ── Catalyseurs ───────────────────────────────────────────────────────────────

def load_catalysts() -> list:
    if os.path.exists(CATALYSTS_PATH):
        with open(CATALYSTS_PATH, encoding="utf-8") as f:
            return json.load(f)
    return []


def _filter_catalysts(catalysts: list, ticker: str,
                      start: pd.Timestamp, end: pd.Timestamp) -> list:
    """Retourne les catalyseurs pertinents pour un ticker sur une période."""
    result = []
    for c in catalysts:
        if ticker not in c["tickers"] and not set(c["tickers"]) >= {"NVDA","GOOGL","META"}:
            if ticker not in c["tickers"]:
                continue
        dt = pd.Timestamp(c["date"])
        if start <= dt <= end:
            result.append({**c, "dt": dt})
    return result


# ── Journal de trades ──────────────────────────────────────────────────────────

def load_trades() -> pd.DataFrame:
    if os.path.exists(TRADES_PATH):
        with open(TRADES_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if data:
            df = pd.DataFrame(data)
            for col in TRADES_COLS:          # rétro-compat : colonnes manquantes → ""
                if col not in df.columns:
                    df[col] = ""
            return df[TRADES_COLS]
    return pd.DataFrame(columns=TRADES_COLS)


def save_trades(df: pd.DataFrame):
    os.makedirs(os.path.dirname(TRADES_PATH), exist_ok=True)
    records = df.astype(str).where(df.notna(), "").to_dict(orient="records")
    with open(TRADES_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
