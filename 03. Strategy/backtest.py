"""
backtest.py  —  Biweekly rebalancing backtesting engine.

Look-ahead protection:
  - Regime and weights computed at close of rebalance day D.
  - New weights applied from day D+1 onward.
  - No future data used in any signal computation.
"""

import pandas as pd
import numpy as np

from regime   import compute_regime
from allocator import compute_weights

REBAL_FREQ = 10     # business days between rebalances (~2 weeks)
FEE_RATE   = 0.0015  # 0.15% per side (stocks + ETFs, conservative)


def run(prices: pd.DataFrame,
        start: str, end: str,
        initial_capital: float = 1000.0,
        fee_rate: float = FEE_RATE,
        gold_ratio: float = None) -> tuple[pd.Series, pd.Series, pd.DataFrame]:
    """
    Run backtest between start and end dates.

    Returns
    -------
    equity   : pd.Series  — portfolio value (daily)
    regime   : pd.Series  — regime signal (daily)
    trades   : pd.DataFrame — rebalance log
    """
    # Regime + momentum computed on FULL history so SMA200 is warmed up at period start
    if "SPY" not in prices.columns:
        raise ValueError("SPY required for regime detection.")

    start, end = pd.Timestamp(start), pd.Timestamp(end)

    # Guard: ensure enough history before period start for SMA200 warmup (need ~280 rows)
    pre_period = prices.loc[:start]
    if len(pre_period) < 280:
        raise ValueError(
            f"Not enough price history before {start} for SMA200 warmup "
            f"(have {len(pre_period)} rows, need ~280). "
            "Download prices starting from at least 2014-01-01."
        )

    full_regime = compute_regime(prices["SPY"])

    # Slice to backtest period (prices_full kept for momentum lookback)
    prices_full   = prices
    prices_period = prices.loc[start:end]

    dates       = prices_period.index
    rebal_dates = set(dates[::REBAL_FREQ])

    equity = pd.Series(index=dates, dtype=float)
    equity.iloc[0] = initial_capital

    current_weights = pd.Series(0.0, index=prices_period.columns)
    trade_log = []

    for i in range(1, len(dates)):
        date     = dates[i]
        prev     = dates[i - 1]
        reg_code = full_regime.loc[prev]

        # Rebalance at close of prev day → effective from today
        if prev in rebal_dates:
            new_w = compute_weights(prices_full.loc[:prev], prev, reg_code, gold_ratio=gold_ratio)
            turnover = (new_w - current_weights).abs().sum()
            cost = turnover * fee_rate
            current_weights = new_w
            trade_log.append({
                "date":     prev,
                "regime":   reg_code,
                "holdings": {t: round(w, 4) for t, w in new_w[new_w > 0].items()},
                "turnover": round(turnover, 4),
                "cost_pct": round(cost * 100, 3),
            })
        else:
            cost = 0.0

        # Daily P&L
        prev_prices = prices_period.loc[prev]
        curr_prices = prices_period.loc[date]
        valid = current_weights[current_weights > 0].index
        valid = [t for t in valid if not pd.isna(prev_prices.get(t)) and not pd.isna(curr_prices.get(t))]

        if valid:
            ret = sum(
                current_weights[t] * (curr_prices[t] / prev_prices[t] - 1)
                for t in valid
            )
        else:
            ret = 0.0

        equity.iloc[i] = equity.iloc[i - 1] * (1 + ret - cost)

    trades = pd.DataFrame(trade_log).set_index("date") if trade_log else pd.DataFrame()
    return equity, full_regime.loc[start:end], trades



def benchmark_equal_weight(prices: pd.DataFrame,
                            tickers: list,
                            start: str, end: str,
                            initial_capital: float = 1000.0) -> pd.Series:
    """Buy-and-hold equal weight on given tickers, no rebalancing, no fees."""
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    sub = prices[tickers].loc[start:end].dropna(how="all")
    avail = sub.columns[sub.iloc[0].notna()]
    w = 1.0 / len(avail)
    ret = sub[avail].pct_change().fillna(0)
    port_ret = ret.mean(axis=1)  # equal weight = mean of returns
    equity = (1 + port_ret).cumprod() * initial_capital
    return equity
