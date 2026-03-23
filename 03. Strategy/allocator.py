"""
allocator.py  —  Portfolio weight allocation based on regime.

BULL       : top N risk-on assets by 30-day momentum, equal weight
BEAR       : GLD 50% + SLV 50%
TRANSITION : top 3 risk-on (50%) + GLD 25% + SLV 25%

Look-ahead protection: weights computed using only prices <= rebalance date.
"""

import pandas as pd

from data_feed import RISK_ON, DEFENSIVE

MOMENTUM_LOOKBACK = 30   # days to measure momentum
TOP_N_BULL        =  3   # assets to hold in bull (optimised: top3 > top7)
GOLD_RATIO        = 0.5  # share of GLD in defensive allocation (rest = SLV)


def _momentum_ranks(prices: pd.DataFrame, date: pd.Timestamp,
                    candidates: list, lookback: int) -> pd.Series:
    """Return 30-day returns for candidates, computed strictly before `date`."""
    idx = prices.index.get_loc(date)
    if idx < lookback:
        return pd.Series(dtype=float)
    past = prices.iloc[idx - lookback]
    curr = prices.iloc[idx]
    avail = [c for c in candidates if c in prices.columns
             and not pd.isna(past.get(c)) and not pd.isna(curr.get(c))]
    if not avail:
        return pd.Series(dtype=float)
    return ((curr[avail] / past[avail]) - 1).sort_values(ascending=False)


def compute_weights(prices: pd.DataFrame, date: pd.Timestamp,
                    regime: int, gold_ratio: float = None) -> pd.Series:
    """
    Return target portfolio weights for rebalancing on `date`.
    Weights sum to 1.0. All values >= 0 (long-only, no leverage).
    """
    all_tickers = list(prices.columns)
    w = pd.Series(0.0, index=all_tickers)

    risk_on_avail  = [t for t in RISK_ON   if t in all_tickers]
    defensive_avail = [t for t in DEFENSIVE if t in all_tickers]

    gld_w = GOLD_RATIO if gold_ratio is None else gold_ratio

    # Defensive weights: gld_w to gold, rest to silver
    def _def_weights() -> dict:
        out = {}
        if "GLD" in defensive_avail and "SLV" in defensive_avail:
            out["GLD"] = gld_w
            out["SLV"] = 1.0 - gld_w
        elif defensive_avail:
            for t in defensive_avail:
                out[t] = 1.0 / len(defensive_avail)
        return out

    if regime == 1:  # BULL
        ranks = _momentum_ranks(prices, date, risk_on_avail, MOMENTUM_LOOKBACK)
        if ranks.empty:
            for t, v in _def_weights().items():
                w[t] = v
        else:
            top = ranks.head(TOP_N_BULL).index.tolist()
            for t in top:
                w[t] = 1.0 / len(top)

    elif regime == -1:  # BEAR
        for t, v in _def_weights().items():
            w[t] = v

    else:  # TRANSITION
        top_n_trans = max(1, TOP_N_BULL // 2)
        ranks = _momentum_ranks(prices, date, risk_on_avail, MOMENTUM_LOOKBACK)
        risk_share = 0.50
        def_share  = 0.50
        if not ranks.empty:
            top = ranks.head(top_n_trans).index.tolist()
            for t in top:
                w[t] = risk_share / len(top)
        for t, v in _def_weights().items():
            w[t] += def_share * v

    return w
