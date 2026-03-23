"""
run_backtest.py  —  Run strategy on 3 periods and display results.

Periods:
  TRAIN    : 2015-01-01 → 2021-12-31
  OOS BEAR : 2022-01-01 → 2022-12-31
  OOS BULL : 2023-01-01 → today

Usage:
  python run_backtest.py           # use cached data
  python run_backtest.py --refresh # re-download all
"""

import sys
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from data_feed  import load_prices, RISK_ON, DEFENSIVE, TICKERS
from backtest   import run, benchmark_equal_weight
from metrics    import compute_metrics, print_table

# ── Periods ──────────────────────────────────────────────────────────────────

PERIODS = {
    "Historique (2015-2021)": ("2015-01-01", "2021-12-31"),
    "Validation Bear (2022)": ("2022-01-01", "2022-12-31"),
    "Validation Bull (2023-now)": ("2023-01-01", "2026-03-18"),
}
INITIAL = 1000.0

# ── Load data ─────────────────────────────────────────────────────────────────

refresh = "--refresh" in sys.argv
print("Loading prices...")
prices = load_prices(refresh=refresh)
prices = prices.ffill()
print(f"Loaded {prices.shape[1]} tickers, {len(prices)} days "
      f"({prices.index.min().date()} to {prices.index.max().date()})\n")

# ── Run each period ───────────────────────────────────────────────────────────

results = {}

for label, (start, end) in PERIODS.items():
    end = min(end, prices.index.max().strftime("%Y-%m-%d"))
    sub = prices.loc[start:end]
    if len(sub) < 50:
        print(f"Skipping {label}: insufficient data")
        continue

    print(f"{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")

    eq_strat, regime_s, trades = run(prices, start, end, INITIAL)

    # Benchmark: equal weight on all risk-on assets available in that period
    ro_avail = [t for t in RISK_ON if t in prices.columns]
    eq_bnh   = benchmark_equal_weight(prices, ro_avail, start, end, INITIAL)

    m_strat = compute_metrics(eq_strat)
    m_bnh   = compute_metrics(eq_bnh)

    print_table({"Strategy": m_strat, "Buy & Hold": m_bnh})

    # Regime breakdown
    counts = regime_s.value_counts()
    total_days = len(regime_s)
    print(f"\nRegime breakdown:")
    for code, name in [(1,"BULL"), (0,"TRANSITION"), (-1,"BEAR")]:
        n = counts.get(code, 0)
        print(f"  {name:<12}: {n:4d} days ({100*n/total_days:.0f}%)")

    # Trade log summary
    if not trades.empty:
        print(f"\nRebalances: {len(trades)} total")
        print(f"Avg turnover: {trades['turnover'].mean():.1%}")
        print(f"Avg cost/rebal: {trades['cost_pct'].mean():.3f}%")

    print()
    results[label] = {
        "eq_strat": eq_strat,
        "eq_bnh":   eq_bnh,
        "regime":   regime_s,
        "trades":   trades,
        "m_strat":  m_strat,
        "m_bnh":    m_bnh,
    }

# ── Plot ──────────────────────────────────────────────────────────────────────

n_periods = len(results)
fig, axes = plt.subplots(n_periods, 2, figsize=(16, 5 * n_periods),
                         gridspec_kw={"width_ratios": [3, 1]})
if n_periods == 1:
    axes = [axes]

REGIME_COLORS = {1: "#d4f0c0", 0: "#fff3cd", -1: "#f8d7da"}

for row, (label, data) in enumerate(results.items()):
    ax_main = axes[row][0]
    ax_dd   = axes[row][1]

    eq_s = data["eq_strat"] / INITIAL
    eq_b = data["eq_bnh"]   / INITIAL
    reg  = data["regime"]

    # Background shading by regime
    prev_date = eq_s.index[0]
    prev_reg  = reg.iloc[0]
    for i in range(1, len(reg)):
        if reg.iloc[i] != prev_reg or i == len(reg) - 1:
            ax_main.axvspan(prev_date, reg.index[i],
                            alpha=0.25, color=REGIME_COLORS.get(prev_reg, "white"),
                            linewidth=0)
            prev_date = reg.index[i]
            prev_reg  = reg.iloc[i]

    ax_main.plot(eq_b.index, eq_b, color="gray",       lw=1.5, ls="--", label="Buy & Hold")
    ax_main.plot(eq_s.index, eq_s, color="steelblue",  lw=2,   label="Strategy")
    ax_main.axhline(1.0, color="black", lw=0.5, ls=":")
    ax_main.set_title(label)
    ax_main.set_ylabel("Value (normalized)")
    ax_main.legend(fontsize=8)
    ax_main.grid(alpha=0.3)

    # Legend for regime colors
    patches = [
        mpatches.Patch(color=REGIME_COLORS[1],  alpha=0.5, label="BULL"),
        mpatches.Patch(color=REGIME_COLORS[0],  alpha=0.5, label="TRANSITION"),
        mpatches.Patch(color=REGIME_COLORS[-1], alpha=0.5, label="BEAR"),
    ]
    ax_main.legend(handles=patches + ax_main.lines, fontsize=7, loc="upper left")

    # Drawdown comparison (right panel)
    for eq, color, lbl in [(eq_s, "steelblue", "Strategy"), (eq_b, "gray", "B&H")]:
        dd = (eq - eq.cummax()) / eq.cummax() * 100
        ax_dd.plot(dd.index, dd, color=color, lw=1.2, label=lbl)
    ax_dd.fill_between(eq_s.index,
                       (eq_s - eq_s.cummax()) / eq_s.cummax() * 100,
                       0, alpha=0.15, color="steelblue")
    ax_dd.set_title("Drawdown (%)")
    ax_dd.legend(fontsize=7)
    ax_dd.grid(alpha=0.3)
    ax_dd.set_ylabel("%")

plt.tight_layout()
out = "backtest_results.png"
plt.savefig(out, dpi=150)
print(f"\nChart saved: {out}")
