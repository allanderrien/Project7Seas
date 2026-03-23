"""
metrics.py  —  Performance metrics for an equity curve.
"""

import numpy as np
import pandas as pd


def compute_metrics(equity: pd.Series, freq: int = 252) -> dict:
    returns = equity.pct_change().dropna()
    total   = equity.iloc[-1] / equity.iloc[0] - 1
    n_years = len(equity) / freq
    cagr    = (1 + total) ** (1 / n_years) - 1 if n_years > 0 else 0
    vol     = returns.std() * np.sqrt(freq)
    sharpe  = (returns.mean() * freq) / (vol) if vol > 0 else 0
    running_max = equity.cummax()
    dd      = (equity - running_max) / running_max
    max_dd  = dd.min()
    calmar  = cagr / abs(max_dd) if max_dd != 0 else np.inf
    nz      = returns[returns != 0]
    win     = (nz > 0).mean() if len(nz) > 0 else 0

    return {
        "Total Return":    f"{total:+.1%}",
        "CAGR":            f"{cagr:+.1%}",
        "Ann. Volatility": f"{vol:.1%}",
        "Sharpe":          f"{sharpe:.2f}",
        "Max Drawdown":    f"{max_dd:.1%}",
        "Calmar":          f"{calmar:.2f}",
        "Win Rate":        f"{win:.1%}",
        "_cagr": cagr, "_sharpe": sharpe, "_max_dd": max_dd,
    }


def print_table(results: dict) -> None:
    labels = [k for k in list(results.values())[0] if not k.startswith("_")]
    cw = max(len(n) for n in results) + 2
    hdr = f"{'Metric':<20}" + "".join(f"{n:>{cw}}" for n in results)
    print(hdr)
    print("-" * len(hdr))
    for lbl in labels:
        print(f"{lbl:<20}" + "".join(f"{results[n][lbl]:>{cw}}" for n in results))
