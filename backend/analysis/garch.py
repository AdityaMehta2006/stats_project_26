"""
garch.py
--------
Pillar 2: GARCH & Volatility Clustering
- GARCH(1,1) model on any ticker's daily log returns
- Conditional volatility time series
- Volatility clustering evidence
- QQ plot data
- Return distribution statistics
"""

import numpy as np
import pandas as pd
from arch import arch_model
from scipy import stats as sp_stats
from statsmodels.stats.diagnostic import acorr_ljungbox

from data_loader import build_equity_returns


def fit_garch(ticker: str = "^GSPC", p: int = 1, q: int = 1, dist: str = "t") -> dict:
    """
    Fit GARCH(p,q) on daily log returns of any ticker.
    Returns model parameters, conditional volatility, and diagnostics.
    """
    returns = build_equity_returns(ticker) * 100  # Scale to percentage

    # Fit GARCH
    model = arch_model(returns, vol="Garch", p=p, q=q, dist=dist, mean="Constant")
    result = model.fit(disp="off", show_warning=False)

    # Conditional volatility
    cond_vol = result.conditional_volatility
    std_resid = result.std_resid.dropna()

    # Parameters
    params = {}
    for name, val, pval in zip(result.params.index, result.params.values, result.pvalues.values):
        params[name] = {
            "value": round(float(val), 6),
            "p_value": round(float(pval), 4),
        }

    # Persistence (alpha + beta)
    alpha = result.params.get("alpha[1]", 0)
    beta = result.params.get("beta[1]", 0)
    persistence = round(float(alpha + beta), 4)

    # Conditional volatility time series (subsample for JSON size)
    vol_series = []
    step = max(1, len(cond_vol) // 1000)  # Max ~1000 points
    for d, v in list(zip(cond_vol.index, cond_vol.values))[::step]:
        vol_series.append({"date": d.strftime("%Y-%m-%d"), "volatility": round(float(v), 4)})

    # Return series (subsampled)
    ret_series = []
    for d, v in list(zip(returns.index, returns.values))[::step]:
        ret_series.append({"date": d.strftime("%Y-%m-%d"), "return": round(float(v), 4)})

    return {
        "ticker": ticker,
        "parameters": params,
        "persistence": persistence,
        "aic": round(float(result.aic), 2),
        "bic": round(float(result.bic), 2),
        "log_likelihood": round(float(result.loglikelihood), 2),
        "n_obs": int(result.nobs),
        "conditional_volatility": vol_series,
        "returns": ret_series,
    }


def get_volatility_clustering_evidence(ticker: str = "^GSPC") -> dict:
    """
    Provide evidence of volatility clustering:
    - Autocorrelation of squared returns
    - Ljung-Box test on squared returns
    """
    returns = build_equity_returns(ticker) * 100
    sq_returns = returns ** 2

    # Autocorrelation of |returns| at lags 1-20
    acf_vals = []
    for lag in range(1, 21):
        corr = sq_returns.autocorr(lag=lag)
        acf_vals.append({"lag": lag, "autocorrelation": round(float(corr), 4)})

    # Ljung-Box test on squared returns
    lb_result = acorr_ljungbox(sq_returns.dropna(), lags=10, return_df=True)
    lb_tests = []
    for lag_idx, row in lb_result.iterrows():
        lb_tests.append({
            "lag": int(lag_idx),
            "lb_stat": round(float(row["lb_stat"]), 2),
            "lb_pvalue": round(float(row["lb_pvalue"]), 6),
        })

    return {
        "ticker": ticker,
        "squared_return_acf": acf_vals,
        "ljung_box_test": lb_tests,
        "interpretation": "Significant autocorrelation in squared returns confirms volatility clustering (ARCH effects).",
    }


def get_return_distribution(ticker: str = "^GSPC") -> dict:
    """
    Return distribution analysis:
    - Descriptive stats (mean, std, skew, kurtosis)
    - QQ plot data (theoretical vs actual quantiles)
    - Jarque-Bera test
    """
    returns = build_equity_returns(ticker) * 100

    # Descriptive stats
    desc = {
        "mean": round(float(returns.mean()), 4),
        "std": round(float(returns.std()), 4),
        "skewness": round(float(returns.skew()), 4),
        "kurtosis": round(float(returns.kurtosis()), 4),  # Excess kurtosis
        "min": round(float(returns.min()), 4),
        "max": round(float(returns.max()), 4),
        "n_obs": int(len(returns)),
    }

    # Jarque-Bera test
    jb_stat, jb_pvalue = sp_stats.jarque_bera(returns.dropna())
    desc["jarque_bera_stat"] = round(float(jb_stat), 2)
    desc["jarque_bera_pvalue"] = round(float(jb_pvalue), 6)
    desc["is_normal"] = bool(jb_pvalue > 0.05)

    # QQ plot data (theoretical normal quantiles vs actual)
    sorted_returns = np.sort(returns.dropna().values)
    n = len(sorted_returns)
    theoretical = sp_stats.norm.ppf(np.linspace(0.001, 0.999, n))

    # Subsample for JSON
    step = max(1, n // 500)
    qq_data = []
    for t, a in zip(theoretical[::step], sorted_returns[::step]):
        qq_data.append({
            "theoretical": round(float(t), 4),
            "actual": round(float(a), 4),
        })

    # Histogram data
    hist_counts, hist_edges = np.histogram(returns.dropna(), bins=80)
    histogram = []
    for i in range(len(hist_counts)):
        histogram.append({
            "bin_start": round(float(hist_edges[i]), 3),
            "bin_end": round(float(hist_edges[i + 1]), 3),
            "bin_mid": round(float((hist_edges[i] + hist_edges[i + 1]) / 2), 3),
            "count": int(hist_counts[i]),
        })

    return {
        "ticker": ticker,
        "descriptive_stats": desc,
        "qq_plot": qq_data,
        "histogram": histogram,
    }


def compare_garch_models(ticker: str = "^GSPC") -> dict:
    """Compare GARCH(1,1) with Normal vs Student-t vs Skewed-t distribution."""
    results = []
    for dist, dist_label in [("normal", "Normal"), ("t", "Student-t"), ("skewt", "Skewed-t")]:
        try:
            res = fit_garch(ticker=ticker, dist=dist)
            results.append({
                "distribution": dist_label,
                "aic": res["aic"],
                "bic": res["bic"],
                "log_likelihood": res["log_likelihood"],
                "persistence": res["persistence"],
            })
        except Exception:
            continue

    return {"ticker": ticker, "model_comparison": results}
