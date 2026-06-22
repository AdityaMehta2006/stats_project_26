"""
recommender.py
--------------
Anomaly & opportunity recommendation engine.

Principle: STATS DETECT, LLM EXPLAINS. Deterministic detectors run over the
existing pillars (GARCH volatility, return distribution, forex cointegration,
price trend) and emit structured signals with a 0-1 severity. A rules-based
summary is always produced; an optional local LLM turns the signals into a
plain-English analyst note (it is given the numbers and must not invent any).
"""

import json
import numpy as np

from data_loader import get_equity_data, build_equity_returns
from analysis.garch import fit_garch, get_return_distribution
from analysis.pairs import get_best_pair_analysis

import llm_client


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return float(max(lo, min(hi, x)))


# ---------------------------------------------------------------------------
# Detectors — each returns a signal dict, or None if nothing notable
# ---------------------------------------------------------------------------

def detect_volatility_regime(ticker: str, garch: dict) -> dict | None:
    vol = [p["volatility"] for p in garch.get("conditional_volatility", [])]
    if len(vol) < 30:
        return None
    arr = np.array(vol, dtype=float)
    latest = float(arr[-1])
    pct = float((arr < latest).mean())  # percentile of current vol within its own history
    annualized = round(latest * np.sqrt(252), 1)
    persistence = garch.get("persistence")

    if pct >= 0.85:
        return {
            "type": "volatility_regime", "asset": ticker, "direction": "elevated",
            "label": "Elevated volatility regime",
            "severity": _clamp((pct - 0.85) / 0.15 * 0.6 + 0.4),
            "recommendation": "reduce risk / size smaller",
            "note": f"Current volatility sits in the {pct*100:.0f}th percentile of its own history "
                    f"(~{annualized}% annualized). High persistence ({persistence}) means shocks fade slowly.",
            "evidence": {"vol_percentile": round(pct, 2), "annualized_vol_pct": annualized,
                         "persistence": persistence},
        }
    if pct <= 0.15:
        return {
            "type": "volatility_regime", "asset": ticker, "direction": "compressed",
            "label": "Compressed (calm) volatility regime",
            "severity": _clamp((0.15 - pct) / 0.15 * 0.5 + 0.3),
            "recommendation": "watch for regime change",
            "note": f"Volatility is unusually low ({pct*100:.0f}th percentile, ~{annualized}% annualized). "
                    f"Calm regimes can precede sharp expansions.",
            "evidence": {"vol_percentile": round(pct, 2), "annualized_vol_pct": annualized,
                         "persistence": persistence},
        }
    return None


def detect_tail_event(ticker: str, dist: dict) -> dict | None:
    returns = build_equity_returns(ticker) * 100.0  # daily %
    if len(returns) < 30:
        return None
    latest = float(returns.iloc[-1])
    recent_sigma = float(returns.tail(21).std())  # trailing ~1M daily vol
    if recent_sigma <= 0:
        return None
    z = latest / recent_sigma
    kurt = dist.get("descriptive_stats", {}).get("kurtosis")
    if abs(z) >= 2.5:
        direction = "down" if z < 0 else "up"
        return {
            "type": "tail_event", "asset": ticker, "direction": direction,
            "label": f"Outsized {direction}-move today ({z:+.1f}σ)",
            "severity": _clamp((abs(z) - 2.5) / 2.5 * 0.6 + 0.4),
            "recommendation": "expect mean-revert or continuation — confirm with regime",
            "note": f"Latest daily return {latest:+.2f}% is {z:+.1f} standard deviations from its "
                    f"recent mean. Excess kurtosis {kurt} means such tail moves are not rare for this asset.",
            "evidence": {"latest_return_pct": round(latest, 2), "z_sigma": round(z, 2),
                         "excess_kurtosis": kurt},
        }
    return None


def detect_pairs_opportunity(pairs, best: dict) -> dict | None:
    if not best or "pair_a" not in best:
        return None
    coint_p = best.get("coint_pvalue", 1.0)
    half_life = best.get("half_life_days")
    zs = [s["z_score"] for s in best.get("spread_series", []) if "z_score" in s]
    if not zs:
        return None
    z = float(zs[-1])
    label_pair = f"{best['pair_a']}/{best['pair_b']}"

    if coint_p < 0.05 and abs(z) >= 2:
        direction = "long spread" if z < 0 else "short spread"
        return {
            "type": "pairs_opportunity", "asset": label_pair, "direction": direction,
            "label": f"Mean-reversion entry on {label_pair}",
            "severity": _clamp(0.5 + (abs(z) - 2) / 2 * 0.4 + (0.05 - coint_p) / 0.05 * 0.1),
            "recommendation": f"consider {direction} (z={z:+.2f})",
            "note": f"{label_pair} is cointegrated (p={coint_p}) and its spread z-score is {z:+.2f}, "
                    f"beyond the ±2 band. Expected mean-reversion half-life ~{half_life} days.",
            "evidence": {"pair": label_pair, "z_score": round(z, 2), "coint_pvalue": coint_p,
                         "half_life_days": half_life},
        }
    if coint_p < 0.05 and abs(z) >= 1:
        return {
            "type": "pairs_opportunity", "asset": label_pair, "direction": "building",
            "label": f"{label_pair} spread stretching",
            "severity": _clamp(0.25 + (abs(z) - 1) * 0.2),
            "recommendation": "watch — no entry yet",
            "note": f"{label_pair} is cointegrated (p={coint_p}); spread z-score {z:+.2f} is approaching "
                    f"the ±2 entry band.",
            "evidence": {"pair": label_pair, "z_score": round(z, 2), "coint_pvalue": coint_p,
                         "half_life_days": half_life},
        }
    return None


def detect_trend(ticker: str) -> dict | None:
    px = get_equity_data(ticker)["Close"].dropna()
    if len(px) < 210:
        return None
    last = float(px.iloc[-1])
    ma50 = float(px.rolling(50).mean().iloc[-1])
    ma200 = float(px.rolling(200).mean().iloc[-1])
    ret_3m = float(px.iloc[-1] / px.iloc[-63] - 1) * 100
    hi_52w = float(px.tail(252).max())
    lo_52w = float(px.tail(252).min())
    near_high = last >= hi_52w * 0.98
    near_low = last <= lo_52w * 1.02

    if last > ma50 > ma200:
        return {
            "type": "trend", "asset": ticker, "direction": "uptrend",
            "label": "Confirmed uptrend" + (" · near 52w high" if near_high else ""),
            "severity": _clamp(0.4 + min(abs(ret_3m) / 30, 0.4) + (0.15 if near_high else 0)),
            "recommendation": "momentum favorable — trail risk",
            "note": f"Price > 50DMA > 200DMA (golden-cross alignment); 3-month return {ret_3m:+.1f}%."
                    + (" Trading near its 52-week high." if near_high else ""),
            "evidence": {"price": round(last, 2), "ma50": round(ma50, 2), "ma200": round(ma200, 2),
                         "ret_3m_pct": round(ret_3m, 1)},
        }
    if last < ma50 < ma200:
        return {
            "type": "trend", "asset": ticker, "direction": "downtrend",
            "label": "Confirmed downtrend" + (" · near 52w low" if near_low else ""),
            "severity": _clamp(0.4 + min(abs(ret_3m) / 30, 0.4) + (0.15 if near_low else 0)),
            "recommendation": "momentum negative — avoid catching the knife",
            "note": f"Price < 50DMA < 200DMA (death-cross alignment); 3-month return {ret_3m:+.1f}%."
                    + (" Trading near its 52-week low." if near_low else ""),
            "evidence": {"price": round(last, 2), "ma50": round(ma50, 2), "ma200": round(ma200, 2),
                         "ret_3m_pct": round(ret_3m, 1)},
        }
    return None


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def _rules_summary(ticker: str, signals: list) -> str:
    if not signals:
        return (f"No notable anomalies for {ticker} right now: volatility is mid-range, no tail move "
                f"today, trend is mixed, and the forex spread is inside its normal band.")
    parts = [f"{s['label']} ({s['recommendation']})." for s in signals]
    return f"{len(signals)} signal(s) for {ticker}: " + " ".join(parts)


def _llm_narrative(ticker: str, signals: list) -> str | None:
    if not signals or not llm_client.available():
        return None
    payload = [
        {k: s[k] for k in ("type", "asset", "direction", "label", "severity", "evidence")}
        for s in signals
    ]
    system = (
        "You are a precise quant analyst. You are given DETECTED signals with their numbers. "
        "Write a brief markdown note (3-5 sentences). Use ONLY the numbers provided — never invent "
        "figures, prices, or dates. Be concrete and cite the evidence. End with one cautious, "
        "non-prescriptive 'what to watch'. No disclaimers, no preamble."
    )
    user = (
        f"Asset focus: {ticker}\n"
        f"Detected signals (JSON):\n{json.dumps(payload, indent=2)}\n\n"
        "Write the analyst note."
    )
    return llm_client.chat(system, user, max_tokens=300, temperature=0.3)


def generate_recommendations(ticker: str = "^GSPC", pairs=None, use_llm: bool = False) -> dict:
    """Run all detectors for a ticker (+ optional forex pairs) and assemble signals."""
    signals = []
    diagnostics = {}

    # Gather the heavier analyses once, tolerate individual failures
    garch = dist = best = None
    try:
        garch = fit_garch(ticker)
    except Exception as e:
        diagnostics["garch"] = str(e)
    try:
        dist = get_return_distribution(ticker)
    except Exception as e:
        diagnostics["distribution"] = str(e)
    try:
        best = get_best_pair_analysis(pairs)
    except Exception as e:
        diagnostics["pairs"] = str(e)

    for detector, args in [
        (detect_volatility_regime, (ticker, garch)) if garch else (None, None),
        (detect_tail_event, (ticker, dist)) if dist else (None, None),
        (detect_trend, (ticker,)),
        (detect_pairs_opportunity, (pairs, best)) if best else (None, None),
    ]:
        if detector is None:
            continue
        try:
            sig = detector(*args)
            if sig:
                sig["severity"] = round(float(sig["severity"]), 2)
                signals.append(sig)
        except Exception as e:  # noqa: BLE001
            diagnostics[getattr(detector, "__name__", "detector")] = str(e)

    signals.sort(key=lambda s: s["severity"], reverse=True)

    # Confidence: scales with how many notable signals fired and how strong they are
    confidence = round(_clamp(0.2 + 0.2 * len(signals) + 0.3 * (signals[0]["severity"] if signals else 0)), 2)

    top = signals[0]["label"] if signals else "No notable anomalies"
    result = {
        "ticker": ticker,
        "pairs": list(pairs) if pairs else None,
        "signals": signals,
        "overall": {"headline": top, "confidence": confidence},
        "rules_summary": _rules_summary(ticker, signals),
        "llm_narrative": None,
        "mode": "rules",
        "llm": llm_client.info(),
    }
    if diagnostics:
        result["diagnostics"] = diagnostics

    if use_llm:
        narrative = _llm_narrative(ticker, signals)
        if narrative:
            result["llm_narrative"] = narrative
            result["mode"] = "llm"

    return result
