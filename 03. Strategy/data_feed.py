"""
data_feed.py  —  Download and cache daily close prices via yfinance.
"""

import os
import time
import requests
import pandas as pd
from tqdm import tqdm

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# ── Universe definition ───────────────────────────────────────────────────────

TICKERS = {
    # --- Risk-ON : Core quality ---
    "NVDA":    "NVIDIA",
    "ORCL":    "Oracle",
    "LLY":     "Eli Lilly",
    "RHM.DE":  "Rheinmetall",
    "LDO.MI":  "Leonardo",
    "HO.PA":   "Thales",
    "HDMG.DE": "Heidelberg Mat.",
    "HAG.DE":  "Hensoldt",         # IPO sep-2020, short history
    # --- Risk-ON : Growth ---
    "TSM":     "TSMC",
    "GOOGL":   "Alphabet",
    "MSFT":    "Microsoft",
    "AAPL":    "Apple",
    "META":    "Meta",
    "CAT":     "Caterpillar",
    "BTC-USD": "Bitcoin",
    "SOL-USD": "Solana",           # available from ~2020
    # --- Defensive ---
    "GLD":     "Gold ETF",
    "SLV":     "Silver ETF",
    # --- Regime signals ---
    "SPY":     "S&P 500",
}

RISK_ON   = ["NVDA","ORCL","LLY","RHM.DE","LDO.MI","HO.PA","HDMG.DE","HAG.DE",
             "TSM","GOOGL","MSFT","AAPL","META","CAT","BTC-USD","SOL-USD"]
DEFENSIVE = ["GLD","SLV"]
REGIME    = ["SPY","GLD"]

# ── Moonshot universe (speculative, for scanner only — not backtested) ────────

MOONSHOTS = {
    # Spatial
    "RKLB":  "Rocket Lab",
    "LUNR":  "Intuitive Machines",
    "ASTS":  "AST SpaceMobile",
    # Quantum
    "RGTI":  "Rigetti Computing",
    "QBTS":  "D-Wave Quantum",
    "IONQ":  "IonQ",
    # Biotech
    "CATX":  "Perspective Therapeutics",
    "BEAM":  "Beam Therapeutics",
    "VKTX":  "Viking Therapeutics",
    # Crypto
    "ETH-USD": "Ethereum",
    # Autres
    "SOUN":  "SoundHound AI",
    "AMPX":  "Amprius Technologies",
    "JMIA":  "Jumia Technologies",
    "TCEHY": "Tencent (OTC)",
}

TICKERS.update(MOONSHOTS)


# ── Download helpers ──────────────────────────────────────────────────────────

# stooq.com suffix mapping
STOOQ_SUFFIX = {
    ".DE": ".de", ".MI": ".it", ".PA": ".fr",
    "-USD": ".v",               # crypto vs USD on stooq (e.g. btc.v)
}

def _stooq_symbol(ticker: str) -> str:
    """Convert ticker to stooq symbol."""
    for suffix, stooq_s in STOOQ_SUFFIX.items():
        if ticker.endswith(suffix):
            base = ticker[: -len(suffix)]
            if suffix == "-USD":
                return base.lower() + stooq_s
            return base.lower() + stooq_s
    return ticker.lower() + ".us"


def _fetch_stooq(ticker: str, start: str = "2014-01-01") -> pd.Series:
    sym  = _stooq_symbol(ticker)
    d1   = start.replace("-", "")
    d2   = "20260401"
    url  = f"https://stooq.com/q/d/l/?s={sym}&d1={d1}&d2={d2}&i=d"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200 or "No data" in r.text or len(r.text) < 50:
            return pd.Series(dtype=float, name=ticker)
        from io import StringIO
        df = pd.read_csv(StringIO(r.text), parse_dates=["Date"])
        df = df.set_index("Date").sort_index()
        s  = df["Close"].dropna()
        s.name = ticker
        return s
    except Exception as e:
        print(f"  stooq error {ticker}: {e}")
        return pd.Series(dtype=float, name=ticker)


def load_prices(tickers: list = None, refresh: bool = False,
                start: str = "2014-01-01") -> pd.DataFrame:
    """Return a DataFrame of daily close prices, columns = tickers."""
    if tickers is None:
        tickers = list(TICKERS.keys())

    os.makedirs(DATA_DIR, exist_ok=True)
    cache_path = os.path.join(DATA_DIR, "_prices.csv")

    if os.path.exists(cache_path) and not refresh:
        df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
        missing = [t for t in tickers if t not in df.columns]
        if not missing:
            print(f"  Loaded from cache ({df.shape[1]} tickers)")
            return df[tickers].sort_index()

    print(f"  Downloading {len(tickers)} tickers from stooq.com...")
    closes = {}
    for t in tqdm(tickers, desc="Fetching"):
        s = _fetch_stooq(t, start=start)
        closes[t] = s   # always include (empty = all-NaN column, prevents redownload)
        if s.empty:
            print(f"  WARNING: no data for {t} (stooq sym: {_stooq_symbol(t)})")
        time.sleep(0.3)   # polite rate limiting

    df = pd.DataFrame(closes).sort_index()
    df.to_csv(cache_path)
    return df


if __name__ == "__main__":
    df = load_prices(refresh=True)
    print(f"Shape : {df.shape}")
    print(f"Period: {df.index.min().date()} to {df.index.max().date()}")
    print(df.tail(3).to_string())
