"""
recommender.py
--------------
Anomaly & opportunity recommendation engine.

Principle: STATS DETECT, RULES DECIDE, LLM EXPLAINS.

Three strictly separated layers, which is the design's main claim:

1. **Detection** (this module). Thirteen deterministic detectors run over the
   pillars and emit structured signals `{type, asset, direction, severity 0-1,
   evidence, note}`. Each answers one narrow question and knows nothing about
   the others.

     price/trend    : trend, breakout, momentum (12-1), relative_performance
     mean reversion : mean_reversion (RSI + displacement), pairs_opportunity
     volatility     : volatility_regime, tail_event, options_mispricing
     macro          : macro_dislocation
     flow / context : volume_anomaly, correlation_regime, seasonality

2. **Decision** (`decision.py`). Nets the signals into a single stance,
   conviction and position size — weighting by reliability, discounting
   redundant signals, and flagging genuine conflict instead of averaging it
   away. Fully deterministic and auditable.

3. **Explanation** (`llm_client.py`, optional). The LLM receives the detections
   and the decision as JSON and writes prose. It never computes, ranks, or
   invents a number. That constraint is what makes a small local model
   trustworthy here, and it means the system's actual output is unchanged
   whether or not the LLM is available.
"""

import json
import numpy as np
import pandas as pd

from data_loader import get_equity_data, build_equity_returns
from analysis.garch import fit_garch, get_return_distribution
from analysis.pairs import get_best_pair_analysis
from analysis.macro_regression import get_macro_diagnostics
from analysis.decision import decide
from analysis.black_scholes import RICH_RATIO, CHEAP_RATIO

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
        label = "50-day high breakout" + (" after squeeze" if squeezed else "")
        severity = _clamp(0.55 + (0.2 if squeezed else 0))
        rec = "momentum signal — watch for follow-through"
    elif breakout_dn_50:
        direction = "down"
        label = "50-day low breakdown" + (" after squeeze" if squeezed else "")
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


def detect_momentum(ticker: str) -> dict | None:
    """
    Classic **12-1 month momentum**, risk-adjusted.

    Measures the trailing 12-month return but *skips the most recent month*
    (hence "12-1"). The skip is not arbitrary: Jegadeesh & Titman (1993) found
    the most recent month exhibits short-term *reversal*, which contaminates the
    momentum signal, so the standard academic construction excludes it.

    Dividing by realised volatility gives a Sharpe-like quantity, so a 30% gain
    earned smoothly scores higher than the same gain earned through violent
    swings. Momentum is among the most replicated anomalies in finance, which is
    why its reliability weight is relatively high.
    """
    px = get_equity_data(ticker)["Close"].dropna()
    if len(px) < 273:                       # 252 trading days + ~21 to skip
        return None

    p_now = float(px.iloc[-22])             # skip the last month
    p_then = float(px.iloc[-274]) if len(px) >= 274 else float(px.iloc[0])
    if p_then <= 0:
        return None
    ret_12_1 = (p_now / p_then - 1.0) * 100

    rets = np.log(px / px.shift(1)).dropna()
    ann_vol = float(rets.tail(252).std() * np.sqrt(252)) * 100
    if ann_vol <= 0:
        return None
    risk_adj = ret_12_1 / ann_vol

    if abs(risk_adj) < 0.4:
        return None

    direction = "positive" if risk_adj > 0 else "negative"
    return {
        "type": "momentum", "asset": ticker, "direction": direction,
        "label": f"{direction.capitalize()} 12-1 momentum ({ret_12_1:+.1f}%, {risk_adj:+.2f} risk-adj)",
        "severity": _clamp(0.3 + min(abs(risk_adj) / 2.0, 0.55)),
        "recommendation": (
            "momentum tailwind — trend-following favourable" if risk_adj > 0
            else "momentum headwind — avoid fresh longs"
        ),
        "note": (
            f"Trailing 12-month return excluding the most recent month is {ret_12_1:+.1f}%, "
            f"or {risk_adj:+.2f} per unit of annualised volatility ({ann_vol:.1f}%). "
            f"The skipped month avoids contamination by short-term reversal."
        ),
        "evidence": {
            "return_12_1_pct": round(ret_12_1, 2),
            "annualized_vol_pct": round(ann_vol, 2),
            "risk_adjusted": round(risk_adj, 3),
        },
    }


def detect_mean_reversion(ticker: str) -> dict | None:
    """
    Short-horizon stretch: **RSI(14)** combined with distance from the 20-day mean.

    RSI = 100 - 100/(1 + RS), where RS is the ratio of average gains to average
    losses over 14 days. Wilder's original smoothing is used (an exponential
    recursion), not a simple average — the two differ noticeably and the simple
    version is a common misimplementation.

    Requiring *both* an RSI extreme and a multi-sigma displacement from the
    20-day mean is deliberate: RSI alone fires constantly in a trending market
    and is close to useless on its own, which is why its reliability weight here
    is only 0.55.
    """
    px = get_equity_data(ticker)["Close"].dropna()
    if len(px) < 60:
        return None

    delta = px.diff().dropna()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    # Wilder smoothing == EMA with alpha = 1/period.
    avg_gain = gain.ewm(alpha=1 / 14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi_series = 100 - 100 / (1 + rs)
    rsi = float(rsi_series.iloc[-1])
    if not np.isfinite(rsi):
        return None

    ma20 = px.rolling(20).mean()
    sd20 = px.rolling(20).std()
    last = float(px.iloc[-1])
    m, s = float(ma20.iloc[-1]), float(sd20.iloc[-1])
    if s <= 0:
        return None
    stretch = (last - m) / s

    oversold = rsi < 30 and stretch < -1.5
    overbought = rsi > 70 and stretch > 1.5
    if not (oversold or overbought):
        return None

    direction = "oversold" if oversold else "overbought"
    extremity = (30 - rsi) / 30 if oversold else (rsi - 70) / 30
    return {
        "type": "mean_reversion", "asset": ticker, "direction": direction,
        "label": f"{direction.capitalize()} — RSI {rsi:.1f}, {stretch:+.1f}σ from 20-day mean",
        "severity": _clamp(0.3 + extremity * 0.35 + min(abs(stretch) / 6, 0.2)),
        "recommendation": (
            "possible bounce — mean-reversion candidate" if oversold
            else "possible pullback — stretched to the upside"
        ),
        "note": (
            f"RSI(14) is {rsi:.1f} ({'below 30' if oversold else 'above 70'}) and price is "
            f"{stretch:+.1f} standard deviations from its 20-day mean. Both conditions are "
            f"required because RSI alone fires persistently in trends."
        ),
        "evidence": {
            "rsi_14": round(rsi, 2),
            "stretch_sigma": round(stretch, 2),
            "price": round(last, 2),
            "ma20": round(m, 2),
        },
    }


def detect_volume_anomaly(ticker: str) -> dict | None:
    """
    Unusual volume, interpreted through the direction of the accompanying move.

    Volume alone is ambiguous — a spike says "something happened", not what. Read
    together with the price change it becomes interpretable: heavy volume on a
    rally suggests **accumulation** (buyers pressing), heavy volume on a decline
    suggests **distribution** (sellers pressing). Volume with no price response
    is flagged as a neutral spike rather than forced into a direction.

    Compared against the 50-day median rather than the mean, because volume
    distributions are strongly right-skewed and a single earnings day would drag
    a mean average badly.
    """
    df = get_equity_data(ticker)
    if "Volume" not in df.columns:
        return None
    vol = df["Volume"].dropna()
    px = df["Close"].dropna()
    if len(vol) < 60 or len(px) < 60:
        return None

    recent = float(vol.iloc[-1])
    baseline = float(vol.iloc[-51:-1].median())
    if baseline <= 0 or recent <= 0:
        return None
    ratio = recent / baseline
    if ratio < 1.8:
        return None

    ret_1d = float(px.iloc[-1] / px.iloc[-2] - 1) * 100
    if ret_1d > 0.5:
        direction, label_word = "accumulation", "buying"
    elif ret_1d < -0.5:
        direction, label_word = "distribution", "selling"
    else:
        direction, label_word = "spike", "activity"

    return {
        "type": "volume_anomaly", "asset": ticker, "direction": direction,
        "label": f"Volume {ratio:.1f}x normal on {ret_1d:+.1f}% move ({label_word})",
        "severity": _clamp(0.25 + min((ratio - 1.8) / 3.0, 0.45)),
        "recommendation": (
            "institutional interest — confirms the move" if direction != "spike"
            else "elevated activity without direction — watch for resolution"
        ),
        "note": (
            f"Latest volume is {ratio:.1f}x its 50-day median while price moved "
            f"{ret_1d:+.1f}%. Median is used because volume is right-skewed and a mean "
            f"would be dragged by single events."
        ),
        "evidence": {
            "volume_ratio": round(ratio, 2),
            "latest_volume": int(recent),
            "median_50d_volume": int(baseline),
            "return_1d_pct": round(ret_1d, 2),
        },
    }


def detect_seasonality(ticker: str) -> dict | None:
    """
    Calendar effect for the current month, tested rather than asserted.

    Computes the historical mean return for this month of the year and runs a
    **one-sample t-test** against zero. Only fires when p < 0.10 *and* at least 8
    observations of that month exist.

    The honesty caveat, which is stated in the signal's own note: testing 12
    months means roughly one will look significant at the 10% level by pure
    chance. Calendar anomalies are also the most heavily data-mined findings in
    finance, and many famous ones ("sell in May") have weakened substantially
    since publication. This is why `decision.py` assigns seasonality the lowest
    reliability weight of any detector, 0.40 — it is included for completeness
    and as a worked example of multiple-testing risk, not because it should drive
    a decision.
    """
    from scipy import stats as sp_stats

    px = get_equity_data(ticker)["Close"].dropna()
    if len(px) < 750:                       # need ~3 years for any monthly power
        return None

    monthly = px.resample("ME").last()
    rets = (np.log(monthly / monthly.shift(1)).dropna()) * 100
    if len(rets) < 24:
        return None

    current_month = pd.Timestamp.today().month
    this_month = rets[rets.index.month == current_month]
    if len(this_month) < 8:
        return None

    mean_ret = float(this_month.mean())
    overall_mean = float(rets.mean())
    t_stat, p_val = sp_stats.ttest_1samp(this_month.values, 0.0)
    if not np.isfinite(p_val) or p_val >= 0.10:
        return None

    month_name = pd.Timestamp(2000, current_month, 1).strftime("%B")
    direction = "favorable" if mean_ret > 0 else "unfavorable"
    win_rate = float((this_month > 0).mean() * 100)

    return {
        "type": "seasonality", "asset": ticker, "direction": direction,
        "label": f"{month_name} historically {direction} ({mean_ret:+.2f}% avg, p={p_val:.3f})",
        "severity": _clamp(0.2 + min(abs(mean_ret) / 6.0, 0.25) + (0.10 if p_val < 0.05 else 0)),
        "recommendation": "weak calendar tilt — do not trade on this alone",
        "note": (
            f"{month_name} has averaged {mean_ret:+.2f}% across {len(this_month)} years "
            f"(vs {overall_mean:+.2f}% for all months), win rate {win_rate:.0f}%, "
            f"t={t_stat:+.2f}, p={p_val:.3f}. Caveat: testing all 12 months means about one "
            f"will appear significant at the 10% level by chance alone, so this is weak "
            f"evidence by construction."
        ),
        "evidence": {
            "month": month_name,
            "mean_return_pct": round(mean_ret, 3),
            "all_month_mean_pct": round(overall_mean, 3),
            "years_observed": int(len(this_month)),
            "win_rate_pct": round(win_rate, 1),
            "t_stat": round(float(t_stat), 3),
            "p_value": round(float(p_val), 4),
        },
    }


def detect_options_mispricing(ticker: str) -> dict | None:
    """
    **Variance risk premium**: the market's implied volatility versus our
    GARCH-forecast volatility.

    This is the detector that connects the options module to the recommender, and
    it is the signal the project roadmap listed as the missing link between the
    volatility pillar and a tradeable view.

    Economics: implied volatility is what option buyers pay for future variance;
    the GARCH forecast is what the data says that variance should be. The gap is
    a **risk premium**, and it is persistently positive in index options — option
    sellers get paid because they lose catastrophically in crashes. So a positive
    gap is not automatically free money; it is compensation for a real exposure.
    A negative gap is the more genuinely unusual state, implying hedges are cheap
    relative to forecast risk.

    Requires a listed option chain, so it silently declines to fire for indices
    and FX pairs that have none on Yahoo.
    """
    try:
        from analysis.market_options import garch_vol_term_structure, _compare_to_chain, \
            get_spot, get_risk_free_rate, get_dividend_yield
    except Exception:
        return None

    try:
        spot = get_spot(ticker)
        r = get_risk_free_rate()["rate_cc"]
        q = get_dividend_yield(ticker)["q"]
        vol_info = garch_vol_term_structure(ticker, horizon_days=30)
        sigma = vol_info.get("sigma_garch")
        if not sigma or sigma <= 0:
            return None
        cmp_ = _compare_to_chain(ticker, spot, round(spot, 2), 30 / 365.0, r, q,
                                 sigma, "call", None)
    except Exception:
        return None

    if not cmp_ or not cmp_.get("available"):
        return None
    ratio = cmp_.get("iv_to_model_ratio")
    vrp = cmp_.get("variance_risk_premium_pct")
    if ratio is None or vrp is None:
        return None
    if CHEAP_RATIO <= ratio <= RICH_RATIO:
        return None

    rich = ratio > RICH_RATIO
    direction = "rich" if rich else "cheap"
    return {
        "type": "options_mispricing", "asset": ticker, "direction": direction,
        "label": (
            f"Options {direction} — IV {cmp_['market_implied_vol_pct']:.1f}% vs "
            f"GARCH forecast {cmp_['model_forecast_vol_pct']:.1f}%"
        ),
        "severity": _clamp(0.3 + min(abs(ratio - 1.0) / 1.0, 0.5)),
        "recommendation": (
            "premium-selling favourable, but crash exposure is the price" if rich
            else "hedges look cheap versus forecast risk — consider protection"
        ),
        "note": (
            f"Market implied volatility is {cmp_['market_implied_vol_pct']:.1f}% against a "
            f"GARCH forecast of {cmp_['model_forecast_vol_pct']:.1f}% for the same maturity "
            f"({cmp_['days_to_expiry']} days) — a variance risk premium of {vrp:+.1f} "
            f"points, ratio {ratio:.2f}. A positive premium is normal and compensates "
            f"sellers for crash risk; a negative one means protection is unusually cheap."
        ),
        "evidence": {
            "market_implied_vol_pct": cmp_["market_implied_vol_pct"],
            "garch_forecast_vol_pct": cmp_["model_forecast_vol_pct"],
            "variance_risk_premium_pct": vrp,
            "iv_to_model_ratio": ratio,
            "expiry": cmp_["expiry_used"],
            "strike": cmp_["nearest_strike"],
        },
    }


def detect_correlation_regime(ticker: str, pairs=None) -> dict | None:
    """
    Correlation-regime shift: is this asset's relationship with the market
    breaking down?

    Compares a 60-day rolling correlation against the S&P 500 with its own
    2-year history. A large move in either direction is informative context:

      * **Decoupling** (correlation collapsing) means the asset is trading on
        idiosyncratic news, so market-level analysis explains less of it and
        diversification is temporarily better than usual.
      * **Converging** (correlation spiking) is the classic stress signature —
        in a crisis everything correlates to 1 and diversification evaporates
        exactly when it is needed.

    Classified as `neutral` in the decision layer because it changes *how much to
    trust other signals* rather than giving a direction of its own.
    """
    if ticker in ("^GSPC", "SPY", "SPX"):
        return None
    try:
        bench = build_equity_returns("^GSPC")
        asset = build_equity_returns(ticker)
    except Exception:
        return None

    combined = pd.DataFrame({"a": asset, "b": bench}).dropna()
    if len(combined) < 300:
        return None

    roll = combined["a"].rolling(60).corr(combined["b"]).dropna()
    if len(roll) < 250:
        return None
    current = float(roll.iloc[-1])
    hist = roll.iloc[-504:-1] if len(roll) > 504 else roll.iloc[:-1]
    mean_c, sd_c = float(hist.mean()), float(hist.std())
    if sd_c <= 0:
        return None
    z = (current - mean_c) / sd_c
    if abs(z) < 2.0:
        return None

    direction = "converging" if z > 0 else "decoupling"
    return {
        "type": "correlation_regime", "asset": ticker, "direction": direction,
        "label": f"Correlation to S&P {direction} ({current:+.2f} vs {mean_c:+.2f} normal, {z:+.1f}σ)",
        "severity": _clamp(0.25 + min((abs(z) - 2.0) / 3.0, 0.35)),
        "recommendation": (
            "correlations rising — diversification weakening, treat market signals as more binding"
            if z > 0 else
            "trading on idiosyncratic news — market-level analysis explains less right now"
        ),
        "note": (
            f"60-day correlation with the S&P 500 is {current:+.2f} against a 2-year average of "
            f"{mean_c:+.2f} (σ={sd_c:.2f}), a {z:+.1f}σ shift. "
            + ("Rising correlation is the classic stress signature — diversification fails "
               "precisely when it is most needed." if z > 0 else
               "Falling correlation means asset-specific drivers dominate.")
        ),
        "evidence": {
            "current_correlation": round(current, 4),
            "historical_mean": round(mean_c, 4),
            "historical_std": round(sd_c, 4),
            "z_score": round(z, 2),
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


def _llm_narrative(ticker: str, signals: list, decision_payload: dict | None = None) -> str | None:
    """
    Ask the local model to narrate the detections *and* the rule-based decision.

    The model is given the decision as a fact to explain, not a question to
    answer. It cannot change the stance, the conviction or the size — those are
    already fixed by `decision.py`. This keeps the division of labour strict: the
    rules are accountable for what the system recommends, the LLM only for how
    readably it is described.
    """
    if not signals or not llm_client.available():
        return None
    payload = [
        {k: s[k] for k in ("type", "asset", "direction", "label", "severity", "evidence")}
        for s in signals
    ]
    decision_summary = None
    if decision_payload:
        decision_summary = {
            k: decision_payload.get(k) for k in
            ("stance", "action", "conviction", "position_size_pct", "net_score",
             "conflict_ratio", "independent_families", "rationale")
        }
    system = (
        "You are a precise quant analyst. You are given DETECTED signals with their numbers "
        "and a DECISION already computed by a deterministic rule engine. "
        "Write a brief markdown note (4-6 sentences) explaining the detections and why they "
        "support that decision. Use ONLY the numbers provided — never invent figures, prices, "
        "or dates, and never change the stance, conviction or position size. If the engine "
        "flagged a conflict, say so plainly. End with one cautious, non-prescriptive "
        "'what to watch'. No disclaimers, no preamble."
    )
    user = (
        f"Asset focus: {ticker}\n"
        f"Detected signals (JSON):\n{json.dumps(payload, indent=2)}\n\n"
        f"Rule-engine decision (JSON):\n{json.dumps(decision_summary, indent=2)}\n\n"
        "Write the analyst note."
    )
    return llm_client.chat(system, user, max_tokens=420, temperature=0.3)


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
        (detect_momentum, (ticker,)),
        (detect_mean_reversion, (ticker,)),
        (detect_volume_anomaly, (ticker,)),
        (detect_seasonality, (ticker,)),
        (detect_correlation_regime, (ticker, pairs)),
        (detect_options_mispricing, (ticker,)),
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

    # The current volatility percentile feeds the decision layer's risk overlay,
    # scaling position size down in high-volatility regimes.
    vol_pct = None
    if garch:
        vols = [p["volatility"] for p in garch.get("conditional_volatility", [])]
        if len(vols) >= 30:
            arr = np.array(vols, dtype=float)
            vol_pct = float((arr < arr[-1]).mean())

    # Rule-based decision: net the signals into a stance, conviction and size.
    decision_payload = decide(signals, ticker=ticker, vol_percentile=vol_pct)

    top = signals[0]["label"] if signals else "No notable anomalies"
    result = {
        "ticker": ticker,
        "pairs": list(pairs) if pairs else None,
        "signals": signals,
        "overall": {"headline": top, "confidence": confidence},
        "decision": decision_payload,
        "volatility_percentile": round(vol_pct, 4) if vol_pct is not None else None,
        "detectors_run": len([e for e in detector_calls if e is not None]),
        "detectors_fired": len(signals),
        "rules_summary": _rules_summary(ticker, signals),
        "llm_narrative": None,
        "mode": "rules",
        "llm": llm_client.info(),
    }
    if diagnostics:
        result["diagnostics"] = diagnostics

    if use_llm:
        narrative = _llm_narrative(ticker, signals, decision_payload)
        if narrative:
            result["llm_narrative"] = narrative
            result["mode"] = "llm"

    return result
