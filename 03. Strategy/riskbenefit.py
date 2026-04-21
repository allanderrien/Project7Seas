"""
riskbenefit.py  —  Analyse risque/bénéfice standardisée basée sur les targets analystes.

Flux : fetch yfinance → table éditable → probabilités → score.
"""

import os
import json
import time
from datetime import date, timedelta

TARGETS_PATH   = os.path.join(os.path.dirname(__file__), "data", "_targets.json")
DOWNSIDE_FLOOR = 0.06   # plancher 6% pour éviter les emballements à faible downside

DEFAULT_RB_TICKERS = ["LLY", "COST", "CL", "SMR", "SMCI", "UBER", "ENPH"]


# ── Cache ─────────────────────────────────────────────────────────────────────

def load_targets_cache() -> dict:
    if os.path.exists(TARGETS_PATH):
        with open(TARGETS_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_targets_cache(data: dict):
    os.makedirs(os.path.dirname(TARGETS_PATH), exist_ok=True)
    with open(TARGETS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ── Fetch yfinance ────────────────────────────────────────────────────────────

def fetch_targets_yf(tickers: list) -> dict:
    """Prix courant + targets analystes 12 mois depuis Yahoo Finance (yfinance)."""
    try:
        import yfinance as yf
        from yfinance.exceptions import YFRateLimitError
    except ImportError:
        return {t: _empty() for t in tickers}

    out = {}
    pause = 4.0 if len(tickers) > 20 else (3.0 if len(tickers) > 10 else 2.0)

    for t in tickers:
        d = _empty()

        # ── Prix via fast_info (endpoint léger) ───────────────────────────────
        try:
            fi = yf.Ticker(t).fast_info
            d["price"] = round(float(fi.get("lastPrice") or fi.get("previousClose")), 2)
        except Exception:
            pass
        time.sleep(pause)

        # ── Targets via analyst_price_targets ─────────────────────────────────
        try:
            apt = yf.Ticker(t).analyst_price_targets
            if apt and apt.get("high"):
                d["high"]   = round(float(apt["high"]),  2)
                d["low"]    = round(float(apt["low"]),   2)
                d["mean"]   = round(float(apt.get("mean") or apt.get("median")), 2)
                d["source"] = "Yahoo Finance"
        except YFRateLimitError:
            d["source"] = "Rate limit — réessayer dans quelques minutes"
        except Exception:
            pass
        time.sleep(pause)

        # ── Fallback via info si analyst_price_targets vide ───────────────────
        if not d["high"]:
            try:
                info = yf.Ticker(t).info
                d["high"] = info.get("targetHighPrice")
                d["low"]  = info.get("targetLowPrice")
                d["mean"] = info.get("targetMeanPrice") or info.get("targetMedianPrice")
                if d["high"]:
                    d["high"]   = round(float(d["high"]), 2)
                    d["low"]    = round(float(d["low"]),  2)
                    d["mean"]   = round(float(d["mean"]), 2)
                    d["source"] = "Yahoo Finance"
            except Exception:
                pass
            time.sleep(pause)

        d["fetched_at"] = date.today().isoformat()
        out[t] = d

    return out


CACHE_TTL_DAYS = 14

def _empty():
    return {"price": None, "low": None, "mean": None, "high": None,
            "source": "Manuel", "fetched_at": None}

def is_fresh(entry: dict) -> bool:
    """True si les données ont moins de CACHE_TTL_DAYS jours."""
    fa = entry.get("fetched_at")
    if not fa:
        return False
    try:
        return (date.today() - date.fromisoformat(fa)).days < CACHE_TTL_DAYS
    except ValueError:
        return False


# ── Métriques ─────────────────────────────────────────────────────────────────

def compute_metrics(price: float, low: float, mean: float, high: float) -> dict:
    upside     = (high  - price) / price
    downside   = max((price - low) / price, DOWNSIDE_FLOOR)
    dispersion = (high  - low)   / price
    return {"upside": upside, "downside": downside, "dispersion": dispersion}


def suggest_probabilities(dispersion: float) -> tuple:
    """Suggestions P(↑) / P(→) / P(↓) basées sur la dispersion."""
    if   dispersion < 0.20: p_bull, p_bear = 0.55, 0.15
    elif dispersion < 0.40: p_bull, p_bear = 0.45, 0.20
    elif dispersion < 0.60: p_bull, p_bear = 0.40, 0.25
    else:                   p_bull, p_bear = 0.35, 0.30
    return round(p_bull, 2), round(1.0 - p_bull - p_bear, 2), round(p_bear, 2)


def compute_score(upside: float, downside: float, dispersion: float,
                  p_bull: float, p_bear: float) -> dict:
    esperance = p_bull * upside - p_bear * downside
    ratio     = upside / max(downside, 1e-9)
    score     = esperance * ratio / (1 + dispersion)
    return {"esperance": esperance, "ratio": ratio, "score": score}
