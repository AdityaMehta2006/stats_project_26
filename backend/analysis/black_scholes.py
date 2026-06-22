"""
black_scholes.py
----------------
Options module (planned roadmap item, v1).

Black-Scholes-Merton pricing for European options, the Greeks, and an
implied-volatility solver. Plus a convenience that prices an option on a live
ticker (spot from Yahoo, risk-free rate from the 10-year yield, a model
volatility from realised returns) and — when an option chain is available —
compares the market's implied volatility to our model volatility.

Opportunity angle: implied volatility >> model volatility => options look "rich";
<< => "cheap" (the variance-risk-premium lens that links to the GARCH pillar).
"""

import numpy as np
from datetime import datetime, date
from scipy.stats import norm

from data_loader import get_equity_data, build_equity_returns, get_treasury_10y_fred

SQRT_252 = np.sqrt(252.0)


# ---------------------------------------------------------------------------
# Core Black-Scholes-Merton math (pure functions, no data access)
# ---------------------------------------------------------------------------

def _d1_d2(S, K, T, r, sigma, q=0.0):
    sig_rt = sigma * np.sqrt(T)
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / sig_rt
    d2 = d1 - sig_rt
    return d1, d2


def bs_price(S, K, T, r, sigma, option="call", q=0.0):
    """European option price. Falls back to intrinsic value if T or sigma <= 0."""
    option = option.lower()
    if T <= 0 or sigma <= 0:
        intrinsic = max(S - K, 0.0) if option == "call" else max(K - S, 0.0)
        return float(intrinsic)
    d1, d2 = _d1_d2(S, K, T, r, sigma, q)
    if option == "call":
        return float(S * np.exp(-q * T) * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2))
    return float(K * np.exp(-r * T) * norm.cdf(-d2) - S * np.exp(-q * T) * norm.cdf(-d1))


def bs_greeks(S, K, T, r, sigma, option="call", q=0.0):
    """Delta, Gamma, Vega (per 1 vol point), Theta (per day), Rho (per 1% rate)."""
    option = option.lower()
    if T <= 0 or sigma <= 0:
        return {"delta": 0.0, "gamma": 0.0, "vega": 0.0, "theta": 0.0, "rho": 0.0}
    d1, d2 = _d1_d2(S, K, T, r, sigma, q)
    pdf = norm.pdf(d1)
    disc_q = np.exp(-q * T)
    disc_r = np.exp(-r * T)

    gamma = disc_q * pdf / (S * sigma * np.sqrt(T))
    vega = S * disc_q * pdf * np.sqrt(T)  # per 1.0 change in sigma
    if option == "call":
        delta = disc_q * norm.cdf(d1)
        theta = (-S * disc_q * pdf * sigma / (2 * np.sqrt(T))
                 - r * K * disc_r * norm.cdf(d2) + q * S * disc_q * norm.cdf(d1))
        rho = K * T * disc_r * norm.cdf(d2)
    else:
        delta = -disc_q * norm.cdf(-d1)
        theta = (-S * disc_q * pdf * sigma / (2 * np.sqrt(T))
                 + r * K * disc_r * norm.cdf(-d2) - q * S * disc_q * norm.cdf(-d1))
        rho = -K * T * disc_r * norm.cdf(-d2)

    return {
        "delta": round(float(delta), 4),
        "gamma": round(float(gamma), 6),
        "vega": round(float(vega / 100.0), 4),     # per 1% (0.01) vol move
        "theta": round(float(theta / 365.0), 4),   # per calendar day
        "rho": round(float(rho / 100.0), 4),       # per 1% (0.01) rate move
    }


def implied_vol(price, S, K, T, r, option="call", q=0.0):
    """Back out implied volatility via Newton with a bisection fallback."""
    if T <= 0 or price <= 0:
        return None
    intrinsic = max(S - K, 0.0) if option.lower() == "call" else max(K - S, 0.0)
    if price < intrinsic - 1e-8:
        return None

    sigma = 0.25  # starting guess
    for _ in range(50):
        diff = bs_price(S, K, T, r, sigma, option, q) - price
        if abs(diff) < 1e-6:
            return float(sigma)
        d1, _ = _d1_d2(S, K, T, r, sigma, q)
        vega = S * np.exp(-q * T) * norm.pdf(d1) * np.sqrt(T)
        if vega < 1e-8:
            break
        sigma -= diff / vega
        if sigma <= 0 or sigma > 5:
            break

    # Bisection fallback
    lo, hi = 1e-4, 5.0
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        diff = bs_price(S, K, T, r, mid, option, q) - price
        if abs(diff) < 1e-6:
            return float(mid)
        if diff > 0:
            hi = mid
        else:
            lo = mid
    return float(0.5 * (lo + hi))


# ---------------------------------------------------------------------------
# Live-ticker convenience
# ---------------------------------------------------------------------------

def _risk_free_rate() -> float:
    """Latest 10-year Treasury yield as a decimal (fallback 4%)."""
    try:
        y = get_treasury_10y_fred()["Treasury10Y"].dropna().iloc[-1]
        return float(y) / 100.0
    except Exception:
        return 0.04


def _model_vol(ticker: str) -> float:
    """Annualised realised volatility from the last ~1y of daily returns."""
    r = build_equity_returns(ticker).dropna()
    if len(r) < 30:
        return 0.20
    return float(r.tail(252).std() * SQRT_252)


def analyze_option(ticker: str = "^GSPC", strike: float = None,
                   expiry: str = None, option: str = "call") -> dict:
    """
    Price an option on a live ticker and report Greeks. If `strike`/`expiry` are
    omitted, defaults to at-the-money and ~30 days. When a market option chain is
    available, also compares market implied volatility to our model volatility.
    """
    option = option.lower()
    spot = float(get_equity_data(ticker)["Close"].dropna().iloc[-1])
    r = _risk_free_rate()
    sigma = _model_vol(ticker)

    K = float(strike) if strike else round(spot, 2)
    if expiry:
        d = datetime.strptime(expiry, "%Y-%m-%d").date()
        T = max((d - date.today()).days, 1) / 365.0
    else:
        T = 30 / 365.0
        expiry = None

    price = bs_price(spot, K, T, r, sigma, option, q=0.0)
    greeks = bs_greeks(spot, K, T, r, sigma, option, q=0.0)

    result = {
        "ticker": ticker,
        "option": option,
        "inputs": {
            "spot": round(spot, 2), "strike": round(K, 2),
            "T_years": round(T, 4), "risk_free_rate": round(r, 4),
            "model_volatility": round(sigma, 4), "expiry": expiry,
        },
        "model_price": round(price, 4),
        "greeks": greeks,
        "market": None,
    }

    # Optional: compare to a live option chain (only some tickers have one)
    try:
        import yfinance as yf
        tk = yf.Ticker(ticker)
        expiries = list(tk.options or [])
        if expiries:
            use_exp = expiry if expiry in expiries else expiries[0]
            chain = tk.option_chain(use_exp)
            df = chain.calls if option == "call" else chain.puts
            row = df.iloc[(df["strike"] - K).abs().argmin()]
            mkt_price = float(row.get("lastPrice") or 0.0)
            mkt_iv = float(row.get("impliedVolatility") or 0.0)
            our_iv = implied_vol(mkt_price, spot, float(row["strike"]), T, r, option) if mkt_price > 0 else None
            verdict = None
            if mkt_iv > 0:
                ratio = mkt_iv / sigma if sigma > 0 else None
                if ratio:
                    verdict = ("rich (implied >> model)" if ratio > 1.15
                               else "cheap (implied << model)" if ratio < 0.85
                               else "fairly priced vs model")
            result["market"] = {
                "expiry_used": use_exp,
                "nearest_strike": round(float(row["strike"]), 2),
                "last_price": round(mkt_price, 4),
                "market_implied_vol": round(mkt_iv, 4),
                "our_implied_vol": round(our_iv, 4) if our_iv else None,
                "model_volatility": round(sigma, 4),
                "vol_verdict": verdict,
            }
    except Exception as e:  # noqa: BLE001 — chain is best-effort
        result["market_error"] = str(e)

    return result
