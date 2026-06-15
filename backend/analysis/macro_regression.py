"""
macro_regression.py
-------------------
Pillar 1: Macro Factor & Lag Regression
- OLS with lagged macro factors for any ticker
- Granger causality tests
- Correlation heatmap data
"""

import numpy as np
import pandas as pd
from statsmodels.tsa.api import VAR
from statsmodels.tsa.stattools import grangercausalitytests
import statsmodels.api as sm

from data_loader import build_macro_dataset


def _add_lags(df: pd.DataFrame, target_col: str, factor_cols: list, max_lag: int = 3):
    """Add lagged versions of factor columns to the dataframe."""
    result = df[[target_col]].copy()
    for col in factor_cols:
        for lag in range(0, max_lag + 1):
            col_name = f"{col}_L{lag}" if lag > 0 else col
            result[col_name] = df[col].shift(lag)
    result.dropna(inplace=True)
    return result


def run_ols_lag_regression(ticker: str = "^GSPC", max_lag: int = 3) -> dict:
    """
    Run OLS: Equity_Return ~ macro factors with lags 0..max_lag.
    Returns coefficients, p-values, R², and model comparison by lag.
    """
    df = build_macro_dataset(ticker)
    target = "Equity_Return"
    factors = [c for c in df.columns if c != target]

    # Model comparison across lag depths
    lag_results = []
    for lag in range(0, max_lag + 1):
        data = df.copy()
        X_cols = []
        for col in factors:
            for l in range(0, lag + 1):
                col_name = f"{col}_L{l}" if l > 0 else col
                data[col_name] = df[col].shift(l)
                X_cols.append(col_name)
        data.dropna(inplace=True)

        X = sm.add_constant(data[X_cols])
        y = data[target]
        model = sm.OLS(y, X).fit()

        lag_results.append({
            "max_lag": lag,
            "r_squared": round(model.rsquared, 4),
            "adj_r_squared": round(model.rsquared_adj, 4),
            "aic": round(model.aic, 2),
            "bic": round(model.bic, 2),
            "f_pvalue": round(model.f_pvalue, 6),
            "n_obs": int(model.nobs),
        })

    # Full model with max_lag
    data_full = _add_lags(df, target, factors, max_lag)
    X_full = sm.add_constant(data_full.drop(columns=[target]))
    y_full = data_full[target]
    full_model = sm.OLS(y_full, X_full).fit()

    coefficients = []
    for name, coef, pval in zip(
        full_model.params.index, full_model.params.values, full_model.pvalues.values
    ):
        coefficients.append({
            "variable": name,
            "coefficient": round(float(coef), 6),
            "p_value": round(float(pval), 4),
            "significant": bool(pval < 0.05),
        })

    return {
        "ticker": ticker,
        "lag_comparison": lag_results,
        "coefficients": coefficients,
        "r_squared": round(full_model.rsquared, 4),
        "adj_r_squared": round(full_model.rsquared_adj, 4),
    }


def run_granger_causality(ticker: str = "^GSPC", max_lag: int = 4) -> dict:
    """
    Test Granger causality: does each macro factor Granger-cause equity returns?
    Returns p-values for each factor at each lag.
    """
    df = build_macro_dataset(ticker)
    target = "Equity_Return"
    factors = [c for c in df.columns if c != target]

    results = []
    for factor in factors:
        subset = df[[target, factor]].dropna()
        if len(subset) < max_lag + 10:
            continue
        try:
            gc = grangercausalitytests(subset, maxlag=max_lag)
            for lag in range(1, max_lag + 1):
                f_test = gc[lag][0]["ssr_ftest"]
                results.append({
                    "factor": factor,
                    "lag": lag,
                    "f_stat": round(float(f_test[0]), 4),
                    "p_value": round(float(f_test[1]), 4),
                    "significant": bool(f_test[1] < 0.05),
                })
        except Exception:
            continue

    return {"ticker": ticker, "granger_results": results}


def run_correlation_heatmap(ticker: str = "^GSPC", max_lag: int = 3) -> dict:
    """
    Compute correlation matrix between equity returns and lagged macro factors.
    Returns data suitable for a heatmap visualization.
    """
    df = build_macro_dataset(ticker)
    target = "Equity_Return"
    factors = [c for c in df.columns if c != target]

    rows = []
    for factor in factors:
        for lag in range(0, max_lag + 1):
            shifted = df[factor].shift(lag)
            corr = df[target].corr(shifted)
            rows.append({
                "factor": factor,
                "lag": lag,
                "correlation": round(float(corr), 4) if not np.isnan(corr) else 0.0,
            })

    return {"ticker": ticker, "heatmap_data": rows, "factors": factors, "max_lag": max_lag}


def get_macro_time_series(ticker: str = "^GSPC") -> dict:
    """Return the raw macro dataset as time series for plotting."""
    df = build_macro_dataset(ticker)
    series = {}
    for col in df.columns:
        s = df[col].dropna()
        series[col] = [
            {"date": d.strftime("%Y-%m-%d"), "value": round(float(v), 6)}
            for d, v in zip(s.index, s.values)
        ]
    return {"ticker": ticker, "time_series": series, "columns": list(df.columns)}
