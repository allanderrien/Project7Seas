"""
regime.py  —  Macro regime detection.

Signal: SPY close vs SPY SMA200 only.
  Gold is NOT used — it increasingly behaves as a speculative asset
  and is no longer a reliable risk-off indicator.

Regime values:
   1  = BULL       → risk-on allocation
   0  = TRANSITION → mixed allocation (buffer zone)
  -1  = BEAR       → defensive allocation

Buffer of ±2% around SMA200 to avoid whipsaws at the boundary.
"""

import pandas as pd

SMA_PERIOD = 200
BUFFER     = 0.01   # ±1% buffer zone (optimised: tighter = faster reaction)


def compute_regime(spy: pd.Series, gld: pd.Series = None) -> pd.Series:
    """
    Daily regime signal based solely on SPY vs SMA200.
    gld parameter kept for API compatibility but ignored.

    Returns pd.Series with values {-1, 0, 1}, same index as spy.
    """
    sma = spy.rolling(SMA_PERIOD).mean()
    rel = (spy - sma) / sma   # normalised distance from SMA

    regime = pd.Series(0, index=spy.index, dtype=int)
    regime[rel >  BUFFER] =  1   # BULL
    regime[rel < -BUFFER] = -1   # BEAR
    # between -BUFFER and +BUFFER → TRANSITION (0), already set

    # NaN during warmup → TRANSITION
    regime[rel.isna()] = 0

    return regime


def regime_label(code: int) -> str:
    return {1: "BULL", 0: "TRANSITION", -1: "BEAR"}.get(code, "?")
