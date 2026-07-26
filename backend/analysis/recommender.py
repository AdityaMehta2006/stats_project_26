"""
recommender.py
--------------
Anomaly & opportunity recommendation engine.

Principle: STATS DETECT, LLM EXPLAINS. Deterministic detectors run over the
existing pillars (GARCH volatility, return distribution, forex cointegration,
price trend, macro dislocation, breakout, relative performance, options vol
mispricing) and emit
structured signals with a 0-1 severity. A rules-based summary is always
produced; an optional local LLM turns the signals into a plain-English
analyst note (it is given the numbers and must not invent any).
"""

import json
import numpy as np
import pandas as pd

from data_loader import get_equity_data, build_equity_returns
from analysis.garch import fit_garch, get_return_distribution
from analysis.pairs import get_best_pair_analysis
from analysis.macro_regression import get_macro_diagnostics
from analysis.black_scholes import analyze_option, RICH_RATIO, CHEAP_RATIO

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
    pct = float((arr < latest).mean())
    annualized = round(latest * np.sqrt(252), 1)
    persistence = garch.get("persistence")

    if pct >= 0.85:
        return {
            "type": "volatility_regime", "asset": ticker, "direction": "elevated",
            "label": "Elevated volatility regime",
            "severity": _clamp((pct - 0.85) / 0.15 * 0.6 + 0.4),
            "recommendation": "reduce risk / size smaller",
            "note": (
                f"Current volatility sits in the {pct*100:.0f}th percentile of its own history "
                f"(~{annualized}% annualized). High persistence ({persistence}) means shocks fade slowly."
            ),
            "evidence": {"vol_percentile": round(pct, 2), "annualized_vol_pct": annualized,
                         "persistence": persistence},
        }
    if pct <= 0.15:
        return {
            "type": "volatility_regime", "asset": ticker, "direction": "compressed",
            "label": "Compressed (calm) volatility regime",
            "severity": _clamp((0.15 - pct) / 0.15 * 0.5 + 0.3),
            "recommendation": "watch for regime change",
            "note": (
                f"Volatility is unusually low ({pct*100:.0f}th percentile, ~{annualized}% annualized). "
                f"Calm regimes can precede sharp expansions."
            ),
            "evidence": {"vol_percentile": round(pct, 2), "annualized_vol_pct": annualized,
                         "persistence": persistence},
        }
    return None


def detect_tail_event(ticker: str, dist: dict) -> dict | None:
    returns = build_equity_returns(ticker) * 100.0  # daily %
    if len(returns) < 30:
        return None
    latest = float(returns.iloc[-1])
    recent_sigma = float(returns.tail(21).std())
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
            "note": (
                f"Latest daily return {latest:+.2f}% is {z:+.1f} standard deviations from its "
                f"recent mean. Excess kurtosis {kurt} means such tail moves are not rare for this asset."
            ),
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
            "note": (
                f"{label_pair} is cointegrated (p={coint_p}) and its spread z-score is {z:+.2f}, "
                f"beyond the ±2 band. Expected mean-reversion half-life ~{half_life} days."
            ),
            "evidence": {"pair": label_pair, "z_score": round(z, 2), "coint_pvalue": coint_p,
                         "half_life_days": half_life},
        }
    if coint_p < 0.05 and abs(z) >= 1:
        return {
            "type": "pairs_opportunity", "asset": label_pair, "direction": "building",
            "label": f"{label_pair} spread stretching",
            "severity": _clamp(0.25 + (abs(z) - 1) * 0.2),
            "recommendation": "watch — no entry yet",
            "note": (
                f"{label_pair} is cointegrated (p={coint_p}); spread z-score {z:+.2f} is approaching "
                f"the ±2 entry band."
            ),
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
            "note": (
                f"Price > 50DMA > 200DMA (golden-cross alignment); 3-month return {ret_3m:+.1f}%."
                + (" Trading near its 52-week high." if near_high else "")
            ),
            "evidence": {"price": round(last, 2), "ma50": round(ma50, 2), "ma200": round(ma200, 2),
                         "ret_3m_pct": round(ret_3m, 1)},
        }
    if last < ma50 < ma200:
        return {
            "type": "trend", "asset": ticker, "direction": "downtrend",
            "label": "Confirmed downtrend" + (" · near 52w low" if near_low else ""),
            "severity": _clamp(0.4 + min(abs(ret_3m) / 30, 0.4) + (0.15 if near_low else 0)),
            "recommendation": "momentum negative — avoid catching the knife",
            "note": (
                f"Price < 50DMA < 200DMA (death-cross alignment); 3-month return {ret_3m:+.1f}%."
                + (" Trading near its 52-week low." if near_low else "")
            ),
            "evidence": {"price": round(last, 2), "ma50": round(ma50, 2), "ma200": round(ma200, 2),
                         "ret_3m_pct": round(ret_3m, 1)},
        }
    return None


def detect_macro_dislocation(ticker: str) -> dict | None:
    """
    Fires when the asset's latest monthly return deviates significantly from
    what the 8-factor macro OLS model predicts (|residual_z| >= 2.0), or when
    two or more macro factors are simultaneously at historical extremes.
    """
    try:
        diag = get_macro_diagnostics(ticker)
    except Exception:
        return None

    resid_z = diag.get("latest_residual_z", 0.0)
    extreme = diag.get("extreme_factors", {})
    n_extreme = len(extreme)

    if abs(resid_z) < 2.0 and n_extreme < 2:
        return None

    direction = "above_model" if resid_z > 0 else "below_model"

    resid_contrib = _clamp((abs(resid_z) - 2.0) / 3.0 * 0.5) if abs(resid_z) >= 2.0 else 0.0
    extreme_contrib = _clamp(n_extreme / 5.0 * 0.3)
    severity = _clamp(0.35 + resid_contrib + extreme_contrib)

    extreme_labels = {k: f"{v['latest_z']:+.1f}σ" for k, v in extreme.items()}
    pred = diag.get("latest_predicted_return", 0.0)
    actual = diag.get("latest_actual_return", 0.0)

    return {
        "type": "macro_dislocation", "asset": ticker, "direction": direction,
        "label": f"Macro dislocation: return is {resid_z:+.2f}σ from model",
        "severity": severity,
        "recommendation": (
            "investigate whether the move is macro-driven or idiosyncratic"
            if abs(resid_z) >= 2.0 else
            "monitor — multiple factors at historical extremes"
        ),
        "note": (
            f"The 8-factor macro OLS model predicts {pred*100:+.2f}% monthly return for {ticker}; "
            f"actual is {actual*100:+.2f}% (residual {resid_z:+.2f}σ). "
            + (
                f"{n_extreme} factor(s) at extremes: "
                + ", ".join(f"{k} {v}" for k, v in extreme_labels.items()) + "."
                if extreme else ""
            )
        ),
        "evidence": {
            "residual_z": round(resid_z, 2),
            "actual_return_pct": round(actual * 100, 2),
            "predicted_return_pct": round(pred * 100, 2),
            "n_extreme_factors": n_extreme,
            "macro_r2": diag.get("r_squared"),
        },
    }


def detect_breakout(ticker: str) -> dict | None:
    """
    Fires on Bollinger band squeeze (current band width < 60% of 50-day avg)
    or on a 20/50-day high/low price breakout.  Squeeze + breakout is the
    highest-confidence setup.
    """
    px = get_equity_data(ticker)["Close"].dropna()
    if len(px) < 70:
        return None

    bb_window = 20
    ma20 = px.rolling(bb_window).mean()
    std20 = px.rolling(bb_window).std()
    bb_width = (2 * std20 / ma20).dropna()

    if len(bb_width) < 50:
        return None

    current_width = float(bb_width.iloc[-1])
    avg_width = float(bb_width.rolling(50).mean().iloc[-1])
    if np.isnan(avg_width) or avg_width <= 0:
        return None
    squeeze_ratio = current_width / avg_width

    last = float(px.iloc[-1])
    hi_20 = float(px.iloc[-21:-1].max()) if len(px) >= 21 else float(px.max())
    lo_20 = float(px.iloc[-21:-1].min()) if len(px) >= 21 else float(px.min())
    hi_50 = float(px.iloc[-51:-1].max()) if len(px) >= 51 else float(px.max())
    lo_50 = float(px.iloc[-51:-1].min()) if len(px) >= 51 else float(px.min())

    breakout_up_50 = last > hi_50
    breakout_dn_50 = last < lo_50
    breakout_up_20 = last > hi_20
    breakout_dn_20 = last < lo_20
    squeezed = squeeze_ratio < 0.6

    if not (squeezed or breakout_up_50 or breakout_dn_50):
        return None

    if breakout_up_50:
        direction = "up"
        label = f"50-day high breakout" + (" after squeeze" if squeezed else "")
        severity = _clamp(0.55 + (0.2 if squeezed else 0))
        rec = "momentum signal — watch for follow-through"
    elif breakout_dn_50:
        direction = "down"
        label = f"50-day low breakdown" + (" after squeeze" if squeezed else "")
        severity = _clamp(0.55 + (0.2 if squeezed else 0))
        rec = "breakdown — monitor support levels"
    elif squeezed and breakout_up_20:
        direction = "up"
        label = "Volatility squeeze + 20-day breakout"
        severity = _clamp(0.45)
        rec = "potential breakout from compression"
    elif squeezed and breakout_dn_20:
        direction = "down"
        label = "Volatility squeeze + 20-day breakdown"
        severity = _clamp(0.45)
        rec = "potential breakdown from compression"
    else:
        direction = "neutral"
        label = f"Bollinger band squeeze (width {squeeze_ratio:.2f}x avg)"
        severity = _clamp(0.3 + (0.6 - squeeze_ratio) * 0.35)
        rec = "coiled — watch for direction break"

    return {
        "type": "breakout", "asset": ticker, "direction": direction,
        "label": label,
        "severity": severity,
        "recommendation": rec,
        "note": (
            f"Bollinger band width is {squeeze_ratio:.2f}x its 50-day average "
            f"({'squeezed — low volatility precedes breakout' if squeezed else 'normal range'}). "
            + ("Price broke above its 50-day high." if breakout_up_50 else "")
            + ("Price broke below its 50-day low." if breakout_dn_50 else "")
        ),
        "evidence": {
            "squeeze_ratio": round(squeeze_ratio, 2),
            "bb_width_current": round(current_width, 4),
            "bb_width_avg_50d": round(avg_width, 4),
            "breakout_50d_high": breakout_up_50,
            "breakout_50d_low": breakout_dn_50,
            "price": round(last, 2),
        },
    }


def detect_relative_performance(ticker: str) -> dict | None:
    """
    Computes 3-month log-return alpha vs S&P 500.  Fires when |alpha| >= 5%.
    """
    if ticker in ("^GSPC", "SPY", "SPX"):
        return None

    try:
        bench_ret = build_equity_returns("^GSPC")
        asset_ret = build_equity_returns(ticker)
    except Exception:
        return None

    combined = pd.DataFrame({"asset": asset_ret, "bench": bench_ret}).dropna()
    if len(combined) < 63:
        return None

    r3m = combined.tail(63)
    asset_3m = float(r3m["asset"].sum()) * 100
    bench_3m = float(r3m["bench"].sum()) * 100
    alpha_3m = asset_3m - bench_3m

    if abs(alpha_3m) < 5.0:
        return None

    # Historical percentile of this 3M alpha
    if len(combined) >= 126:
        rolling_alpha = (
            combined["asset"].rolling(63).sum() - combined["bench"].rolling(63).sum()
        ) * 100
        rolling_alpha = rolling_alpha.dropna()
        pct = float((rolling_alpha.iloc[:-1] < alpha_3m).mean())
    else:
        pct = 0.75 if alpha_3m > 0 else 0.25

    direction = "outperforming" if alpha_3m > 0 else "underperforming"
    severity = _clamp(0.3 + abs(alpha_3m) / 40.0 * 0.45 + abs(pct - 0.5) * 0.25)

    return {
        "type": "relative_performance", "asset": ticker, "direction": direction,
        "label": f"{ticker} {direction} S&P 500 by {alpha_3m:+.1f}% (3M)",
        "severity": severity,
        "recommendation": (
            "strength vs benchmark — check if sector/factor-driven or stock-specific"
            if alpha_3m > 0 else
            "weakness vs benchmark — identify catalyst or sector rotation"
        ),
        "note": (
            f"{ticker} returned {asset_3m:+.1f}% vs S&P 500's {bench_3m:+.1f}% over the past "
            f"3 months ({alpha_3m:+.1f}% alpha). "
            f"This alpha ranks in the {pct*100:.0f}th percentile of all 3-month windows."
        ),
        "evidence": {
            "asset_3m_pct": round(asset_3m, 1),
            "bench_3m_pct": round(bench_3m, 1),
            "alpha_3m_pct": round(alpha_3m, 1),
            "alpha_percentile": round(pct, 2),
        },
    }


def detect_vol_mispricing(ticker: str) -> dict | None:
    """
    Variance risk premium: the market's implied volatility against our own
    realised-vol estimate. Rich premium favours selling it, cheap favours
    buying it — a relative-value read, not a directional call.

    Silent when the ticker has no option chain, which is most of them.
    """
    try:
        opt = analyze_option(ticker)
    except Exception:
        return None

    mkt = opt.get("market") or {}
    iv = float(mkt.get("market_implied_vol") or 0.0)
    model_vol = float(mkt.get("model_volatility") or 0.0)
    if iv <= 0 or model_vol <= 0:
        return None

    ratio = iv / model_vol
    if CHEAP_RATIO <= ratio <= RICH_RATIO:
        return None

    if ratio > RICH_RATIO:
        direction = "rich"
        severity = _clamp(0.35 + (ratio - RICH_RATIO) / 0.5 * 0.65)
        label = f"{ticker} options rich — implied vol {ratio:.2f}× realised"
        recommendation = "sell premium / prefer spreads"
    else:
        direction = "cheap"
        severity = _clamp(0.35 + (CHEAP_RATIO - ratio) / CHEAP_RATIO * 0.65)
        label = f"{ticker} options cheap — implied vol {ratio:.2f}× realised"
        recommendation = "buy premium"

    return {
        "type": "vol_mispricing", "asset": ticker, "direction": direction,
        "label": label,
        "severity": severity,
        "recommendation": recommendation,
        "note": (
            f"The {mkt.get('expiry_used')} chain implies {iv*100:.1f}% annualized volatility "
            f"against {model_vol*100:.1f}% realised over the past year — a ratio of {ratio:.2f}. "
            f"Option premium looks {direction} relative to how much {ticker} has actually moved."
        ),
        "evidence": {
            "implied_vol_pct": round(iv * 100, 1),
            "realised_vol_pct": round(model_vol * 100, 1),
            "iv_ratio": round(ratio, 2),
            "expiry_used": mkt.get("expiry_used"),
        },
    }


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def _rules_summary(ticker: str, signals: list) -> str:
    if not signals:
        return (
            f"No notable anomalies for {ticker} right now: volatility is mid-range, no tail move "
            f"today, trend is mixed, and the forex spread is inside its normal band."
        )
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

    # Run heavier analyses once; tolerate individual failures
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

    # All detectors with their arguments; None entries are skipped
    detector_calls = [
        (detect_volatility_regime, (ticker, garch)) if garch else None,
        (detect_tail_event, (ticker, dist)) if dist else None,
        (detect_trend, (ticker,)),
        (detect_pairs_opportunity, (pairs, best)) if best else None,
        (detect_macro_dislocation, (ticker,)),
        (detect_breakout, (ticker,)),
        (detect_relative_performance, (ticker,)),
    ]

    for entry in detector_calls:
        if entry is None:
            continue
        detector, args = entry
        try:
            sig = detector(*args)
            if sig:
                sig["severity"] = round(float(sig["severity"]), 2)
                signals.append(sig)
        except Exception as e:
            diagnostics[detector.__name__] = str(e)

    signals.sort(key=lambda s: s["severity"], reverse=True)

    confidence = round(
        _clamp(0.2 + 0.15 * len(signals) + 0.3 * (signals[0]["severity"] if signals else 0)),
        2,
    )

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
