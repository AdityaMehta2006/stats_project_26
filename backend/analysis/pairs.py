"""
pairs.py
--------
Pillar 3: Pair Trading in Forex (or any asset pairs)
- Cointegration testing (Engle-Granger) on all pair combinations
- Spread construction & z-score for best pair
- Buy/sell signal generation
- Half-life of mean reversion
- Supports custom forex pair selection
"""

import numpy as np
import pandas as pd
from itertools import combinations
from statsmodels.tsa.stattools import adfuller, coint
import statsmodels.api as sm

from data_loader import get_forex, get_available_forex


def run_cointegration_tests(pair_labels: list = None) -> dict:
    """
    Test cointegration for all combinations of forex pairs using Engle-Granger.
    pair_labels: optional list like ["EURUSD", "GBPUSD", ...].
    Returns a matrix of p-values.
    """
    forex = get_forex(pair_labels).dropna()
    pairs_list = list(forex.columns)

    results = []
    for a, b in combinations(pairs_list, 2):
        try:
            score, pvalue, _ = coint(forex[a], forex[b])
            results.append({
                "pair_a": a,
                "pair_b": b,
                "pair_label": f"{a}/{b}",
                "coint_stat": round(float(score), 4),
                "p_value": round(float(pvalue), 4),
                "cointegrated": bool(pvalue < 0.05),
            })
        except Exception:
            continue

    # Sort by p-value
    results.sort(key=lambda x: x["p_value"])

    return {
        "cointegration_results": results,
        "pairs_tested": len(results),
        "cointegrated_pairs": sum(1 for r in results if r["cointegrated"]),
        "selected_pairs": pairs_list,
    }


def get_best_pair_analysis(pair_labels: list = None) -> dict:
    """
    Find the best cointegrated pair and compute:
    - Spread time series
    - Z-score with signals
    - Half-life of mean reversion
    """
    forex = get_forex(pair_labels).dropna()
    pairs_list = list(forex.columns)

    if len(pairs_list) < 2:
        return {"error": "Need at least 2 forex pairs for analysis"}

    # Find best cointegrated pair
    best_pair = None
    best_pvalue = 1.0
    for a, b in combinations(pairs_list, 2):
        try:
            _, pvalue, _ = coint(forex[a], forex[b])
            if pvalue < best_pvalue:
                best_pvalue = pvalue
                best_pair = (a, b)
        except Exception:
            continue

    if best_pair is None:
        best_pair = (pairs_list[0], pairs_list[1])

    a, b = best_pair

    # OLS to find hedge ratio: P_a = beta * P_b + alpha + epsilon
    X = sm.add_constant(forex[b])
    model = sm.OLS(forex[a], X).fit()
    hedge_ratio = float(model.params.iloc[1])

    # Spread
    spread = forex[a] - hedge_ratio * forex[b]

    # Rolling z-score (60-day window)
    window = 60
    spread_mean = spread.rolling(window=window).mean()
    spread_std = spread.rolling(window=window).std()
    z_score = ((spread - spread_mean) / spread_std).dropna()

    # Signals
    signals = []
    position = 0  # 0 = flat, 1 = long, -1 = short
    for date, z in zip(z_score.index, z_score.values):
        signal = "hold"
        if position == 0:
            if z < -2:
                signal = "buy"
                position = 1
            elif z > 2:
                signal = "sell"
                position = -1
        elif position == 1:
            if z >= 0:
                signal = "close_long"
                position = 0
        elif position == -1:
            if z <= 0:
                signal = "close_short"
                position = 0
        if signal != "hold":
            signals.append({
                "date": date.strftime("%Y-%m-%d"),
                "z_score": round(float(z), 4),
                "signal": signal,
            })

    # Half-life of mean reversion (AR(1) on spread)
    spread_lag = spread.shift(1)
    spread_diff = spread - spread_lag
    df_hl = pd.DataFrame({"y": spread_diff, "x": spread_lag}).dropna()
    hl_model = sm.OLS(df_hl["y"], sm.add_constant(df_hl["x"])).fit()
    lambda_val = float(hl_model.params.iloc[1])
    half_life = -np.log(2) / lambda_val if lambda_val < 0 else float("inf")

    # Time series for plotting (subsample)
    step = max(1, len(z_score) // 800)
    spread_series = []
    z_reindexed = z_score.reindex(spread.index)
    for d, s, z in list(zip(spread.index, spread.values, z_reindexed.values))[::step]:
        entry = {"date": d.strftime("%Y-%m-%d"), "spread": round(float(s), 6)}
        if not np.isnan(z):
            entry["z_score"] = round(float(z), 4)
        spread_series.append(entry)

    # Price series for the pair
    price_series = []
    for d, pa, pb in list(zip(forex.index, forex[a].values, forex[b].values))[::step]:
        price_series.append({
            "date": d.strftime("%Y-%m-%d"),
            a: round(float(pa), 4),
            b: round(float(pb), 4),
        })

    return {
        "pair_a": a,
        "pair_b": b,
        "hedge_ratio": round(hedge_ratio, 4),
        "coint_pvalue": round(best_pvalue, 4),
        "half_life_days": round(float(half_life), 1) if half_life != float("inf") else None,
        "spread_series": spread_series,
        "price_series": price_series,
        "signals": signals,
        "total_signals": len(signals),
    }


def get_forex_correlation(pair_labels: list = None) -> dict:
    """Return correlation matrix of forex pairs for a heatmap."""
    forex = get_forex(pair_labels).dropna()
    corr = forex.corr()

    rows = []
    for a in corr.index:
        for b in corr.columns:
            rows.append({
                "pair_a": a,
                "pair_b": b,
                "correlation": round(float(corr.loc[a, b]), 4),
            })

    return {
        "correlation_matrix": rows,
        "pairs": list(corr.columns),
    }
