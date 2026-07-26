"""
macro_regression.py
-------------------
Pillar 1: Macro Factor & Lag Regression

Factors are z-score standardized before OLS so that all regression
coefficients are directly comparable "standardized betas" — the effect
on equity returns per one standard deviation move in each factor.

VIX is transformed to its monthly log-change (Δ log VIX) before
standardizing, which produces a stationary series appropriate for OLS.

The raw factor levels are kept separate (for time-series plotting) so
that the user always sees real values in charts.
"""

import io
import contextlib

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import grangercausalitytests
import statsmodels.api as sm

from data_loader import build_macro_dataset


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _prepare_factors(df: pd.DataFrame, target: str) -> tuple:
    """
    Returns (df_std, factor_stats) where:
      - df_std: copy of df with factor columns z-scored (target unchanged)
      - factor_stats: dict {col: {mean, std, latest_raw, latest_z}} for the
        raw (pre-standardization) series, used by the dislocation detector
    VIX is replaced by its monthly log-change before z-scoring.
    """
    df = df.copy()
    factors = [c for c in df.columns if c != target]

    # VIX: level → monthly log-return (better stationarity)
    if "VIX" in factors:
        df["VIX"] = np.log(df["VIX"] / df["VIX"].shift(1))
        df.dropna(inplace=True)

    factor_stats = {}
    for col in factors:
        raw = df[col]
        mu = float(raw.mean())
        sigma = float(raw.std())
        latest_raw = float(raw.iloc[-1])
        z = (latest_raw - mu) / sigma if sigma > 0 else 0.0
        # historical percentile of the latest value
        pct = float((raw.iloc[:-1] < latest_raw).mean()) if len(raw) > 1 else 0.5
        factor_stats[col] = {
            "mean": round(mu, 6),
            "std": round(sigma, 6),
            "latest_raw": round(latest_raw, 6),
            "latest_z": round(z, 3),
            "percentile": round(pct, 3),
        }
        df[col] = (raw - mu) / (sigma if sigma > 0 else 1)

    return df, factor_stats


def _add_lags(df: pd.DataFrame, target_col: str, factor_cols: list, max_lag: int = 3):
    """Add lagged versions of factor columns to the dataframe."""
    result = df[[target_col]].copy()
    for col in factor_cols:
        for lag in range(0, max_lag + 1):
            col_name = f"{col}_L{lag}" if lag > 0 else col
            result[col_name] = df[col].shift(lag)
    result.dropna(inplace=True)
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_ols_lag_regression(ticker: str = "^GSPC", max_lag: int = 3) -> dict:
    """
    OLS: Equity_Return ~ z-scored macro factors with lags 0..max_lag.

    Coefficients are standardized betas (effect per 1-SD move in each factor),
    making them directly comparable across factors with different units.

    Returns coefficients, p-values, R², lag comparison, and a driver ranking
    sorted by absolute standardized coefficient.
    """
    df_raw = build_macro_dataset(ticker)
    target = "Equity_Return"

    df, factor_stats = _prepare_factors(df_raw, target)
    factors = [c for c in df.columns if c != target]

    # --- Model comparison across lag depths ---
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

    # --- Full model at max_lag ---
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
            "p_value": round(float(pval), 6),
            "significant": bool(pval < 0.05),
        })

    # Driver ranking: sort significant betas by absolute effect (exclude const)
    sig_coefs = [c for c in coefficients if c["variable"] != "const"]
    driver_ranking = sorted(sig_coefs, key=lambda c: abs(c["coefficient"]), reverse=True)

    # Latest residual info (useful for the dislocation detector)
    residuals = full_model.resid.values
    resid_std = float(np.std(residuals))
    latest_resid_z = round(float(residuals[-1]) / resid_std, 3) if resid_std > 0 else 0.0

    return {
        "ticker": ticker,
        "lag_comparison": lag_results,
        "coefficients": coefficients,
        "driver_ranking": driver_ranking,
        "r_squared": round(full_model.rsquared, 4),
        "adj_r_squared": round(full_model.rsquared_adj, 4),
        "factor_stats": factor_stats,
        "latest_residual_z": latest_resid_z,
        "note": "Coefficients are standardized betas (per 1-SD move in each factor, with VIX as log-change).",
    }


def get_macro_diagnostics(ticker: str = "^GSPC") -> dict:
    """
    Lightweight diagnostic used by the recommender engine.

    Runs a single-lag OLS with standardized factors and returns:
    - latest_residual_z: how far the latest return is from the model's prediction
    - extreme_factors: any factor currently in the top/bottom 12th percentile
    - factor_stats: per-factor z-score, percentile, raw value
    """
    df_raw = build_macro_dataset(ticker)
    target = "Equity_Return"
    df, factor_stats = _prepare_factors(df_raw, target)
    factors = [c for c in df.columns if c != target]

    # OLS with lag 0 (fast, used only for residuals)
    X = sm.add_constant(df[factors])
    y = df[target]
    model = sm.OLS(y, X).fit()

    residuals = model.resid.values
    resid_std = float(np.std(residuals))
    latest_resid_z = round(float(residuals[-1]) / resid_std, 3) if resid_std > 0 else 0.0
    latest_actual = round(float(y.iloc[-1]), 4)
    latest_predicted = round(float(model.fittedvalues.iloc[-1]), 4)

    # Factors at historical extremes (threshold: outside middle 76%)
    extreme = {
        k: v for k, v in factor_stats.items()
        if v["percentile"] >= 0.88 or v["percentile"] <= 0.12
    }

    return {
        "latest_residual_z": latest_resid_z,
        "latest_actual_return": latest_actual,
        "latest_predicted_return": latest_predicted,
        "extreme_factors": extreme,
        "factor_stats": factor_stats,
        "r_squared": round(float(model.rsquared), 4),
        "n_obs": int(model.nobs),
    }


def run_granger_causality(ticker: str = "^GSPC", max_lag: int = 4) -> dict:
    """
    Granger causality: does each macro factor predict equity returns?
    Uses raw (non-standardized) factor values — Granger tests are invariant
    to monotone rescaling so z-scoring wouldn't change the result.
    """
    # copy(): build_macro_dataset is memoized, so the frame is shared — the
    # VIX rewrite below would otherwise corrupt it for every other caller.
    df = build_macro_dataset(ticker).copy()
    target = "Equity_Return"

    # VIX: log-change for stationarity
    if "VIX" in df.columns:
        df["VIX"] = np.log(df["VIX"] / df["VIX"].shift(1))
        df.dropna(inplace=True)

    factors = [c for c in df.columns if c != target]

    results = []
    for factor in factors:
        subset = df[[target, factor]].dropna()
        if len(subset) < max_lag + 10:
            continue
        try:
            # No verbose= kwarg: removed in statsmodels 0.14. Passing it raised
            # a TypeError that the except below swallowed, so this whole
            # function silently returned zero results. Without it the function
            # dumps a test block per lag to stdout, hence redirect_stdout.
            with contextlib.redirect_stdout(io.StringIO()):
                gc = grangercausalitytests(subset, maxlag=max_lag)
            for lag in range(1, max_lag + 1):
                f_test = gc[lag][0]["ssr_ftest"]
                results.append({
                    "factor": factor,
                    "lag": lag,
                    "f_stat": round(float(f_test[0]), 4),
                    "p_value": round(float(f_test[1]), 6),
                    "significant": bool(f_test[1] < 0.05),
                })
        except Exception:
            continue

    return {"ticker": ticker, "granger_results": results}


def run_correlation_heatmap(ticker: str = "^GSPC", max_lag: int = 3) -> dict:
    """
    Lagged correlation heatmap: correlation of equity return with each
    factor shifted 0..max_lag months. Uses raw factor values so the
    heatmap shows real-world correlations.
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
    """Raw macro time series for the chart (always raw, never standardized)."""
    df = build_macro_dataset(ticker)
    series = {}
    for col in df.columns:
        s = df[col].dropna()
        series[col] = [
            {"date": d.strftime("%Y-%m-%d"), "value": round(float(v), 6)}
            for d, v in zip(s.index, s.values)
        ]
    return {"ticker": ticker, "time_series": series, "columns": list(df.columns)}
