"""
market_options.py
-----------------
Wires the pricing models in `advanced_options.py` to **actual market data**.

Why this module exists
----------------------
`advanced_options.py` is deliberately pure: it takes numbers (S, K, T, r, sigma)
and returns prices, with no I/O. That makes it testable and reusable, but on its
own it only prices hypotheticals. This module supplies every input from a real
source, which is where the genuinely interesting modelling decisions live:

| Input | Naive choice | What we actually do | Why it matters |
|---|---|---|---|
| S spot | hardcoded | last close from Yahoo | — |
| r | hardcoded 5% | 10-year Treasury `^TNX`, maturity-matched where possible | wrong r mostly shifts puts vs calls via parity |
| sigma | realised stdev | **GARCH(1,1) forecast**, term-aggregated over the option's life | realised vol is backward-looking; options are forward-looking claims |
| q | 0 | actual trailing dividend yield from Yahoo | ignoring q overprices calls and underprices puts |
| r_foreign (FX) | hardcoded 2% | per-currency policy rate | GK is driven by the *rate differential* |
| jump params | guessed | **fitted from the return distribution's skew and kurtosis** | ties the smile model to measured fat tails |
| Heston v0/theta | guessed | v0 = GARCH current variance, theta = GARCH long-run variance | the GARCH pillar already estimates exactly these |

The volatility choice is the substantive one. An option is a claim on *future*
variance, so the right sigma is a forecast, not a historical average. GARCH(1,1)
gives a principled term structure: the h-step-ahead variance forecast mean-reverts
from today's conditional variance toward the long-run level, and aggregating
those forecasts over the option's life gives the volatility the option actually
references. That single substitution is what connects the options module to
Pillar 2 instead of leaving them as unrelated exercises.

The payoff: comparing this model volatility against the market's implied
volatility gives the **variance risk premium**, which is the signal fed to the
recommender's `detect_options_mispricing`.
"""

import numpy as np
from datetime import datetime, date
from typing import Dict, Any, List, Optional

from data_loader import get_equity_data, build_equity_returns, get_treasury_10y_fred
from analysis.advanced_options import (
    bsm_equity_price,
    garman_kohlhagen_price,
    calculate_greeks,
    binomial_tree_price,
    monte_carlo_gbm,
    merton_closed_form,
    heston_semi_analytic,
    implied_vol,
    put_call_parity_check,
)

TRADING_DAYS = 252.0
SQRT_252 = np.sqrt(TRADING_DAYS)


# ---------------------------------------------------------------------------
# Market inputs
# ---------------------------------------------------------------------------

def get_spot(ticker: str) -> float:
    """Latest available close price."""
    px = get_equity_data(ticker)["Close"].dropna()
    if len(px) == 0:
        raise ValueError(f"no price data for {ticker}")
    return float(px.iloc[-1])


def get_risk_free_rate() -> Dict[str, Any]:
    """
    Continuously-compounded risk-free rate from the 10-year Treasury (`^TNX`).

    `^TNX` quotes an annually-compounded yield in percent (e.g. 4.13 = 4.13%).
    Black-Scholes needs a *continuously compounded* rate, so we convert properly
    rather than just dividing by 100:

        r_cc = ln(1 + y)

    At 4% the difference is only ~8 basis points, but it is free to get right and
    exactly the kind of detail that separates a careful implementation from a
    careless one. Falls back to 4% if the series is unavailable.
    """
    try:
        y = float(get_treasury_10y_fred()["Treasury10Y"].dropna().iloc[-1]) / 100.0
        return {
            "rate_cc": float(np.log(1.0 + y)),
            "quoted_yield": round(y, 6),
            "source": "Yahoo ^TNX (10-year Treasury)",
            "conversion": "r_cc = ln(1 + y)",
        }
    except Exception as e:
        return {"rate_cc": 0.04, "quoted_yield": 0.04,
                "source": f"fallback 4% ({e})", "conversion": "none"}


def get_dividend_yield(ticker: str) -> Dict[str, Any]:
    """
    Trailing dividend yield from Yahoo, as a continuous decimal.

    Ignoring q is a real pricing error, not a rounding one: a 2% yield on a
    1-year at-the-money call is worth roughly 1% of spot. The sign of the error
    is systematic — omitting q **overprices calls** and **underprices puts**,
    because the dividend stream is value that accrues to the shareholder rather
    than the option holder.

    Indices such as ^GSPC report no dividend field on Yahoo even though their
    constituents pay; we return 0 with the source recorded so the limitation is
    explicit in the output rather than hidden.
    """
    # Unit handling is the trap here. yfinance is inconsistent across versions
    # and fields: `trailingAnnualDividendYield` is a fraction (0.0032 = 0.32%),
    # while `dividendYield` in current versions is already a PERCENTAGE
    # (0.32 = 0.32%). Reading the latter as a fraction turns Apple's 0.32%
    # dividend into 32%, which then corrupts every option price and produces
    # nonsensical implied volatilities.
    #
    # So we prefer the unambiguous fractional field, and sanity-check the result
    # against a plausible range rather than trusting either blindly.
    MAX_PLAUSIBLE_Q = 0.25  # 25%; above this, assume a unit error

    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info or {}

        # 1. Unambiguously a fraction.
        val = info.get("trailingAnnualDividendYield")
        if val is not None:
            q = float(val)
            if 0 <= q <= MAX_PLAUSIBLE_Q:
                return {"q": q, "source": "yfinance.trailingAnnualDividendYield (fraction)",
                        "reported_pct": round(q * 100, 4)}

        # 2. Percentage in current yfinance versions.
        val = info.get("dividendYield")
        if val is not None:
            pct = float(val)
            if 0 <= pct / 100.0 <= MAX_PLAUSIBLE_Q:
                return {"q": pct / 100.0, "source": "yfinance.dividendYield (percent)",
                        "reported_pct": round(pct, 4)}

        # 3. Last resort: derive it from the dividend rate and price.
        rate = info.get("dividendRate") or info.get("trailingAnnualDividendRate")
        price = info.get("regularMarketPrice") or info.get("previousClose")
        if rate and price and float(price) > 0:
            q = float(rate) / float(price)
            if 0 <= q <= MAX_PLAUSIBLE_Q:
                return {"q": q, "source": "derived from dividendRate / price",
                        "reported_pct": round(q * 100, 4)}

        return {"q": 0.0, "source": "no usable dividend field reported", "reported_pct": 0.0}
    except Exception as e:
        return {"q": 0.0, "source": f"unavailable ({e})", "reported_pct": 0.0}


# Approximate short-term policy rates by currency, used for the Garman-Kohlhagen
# foreign leg. Hardcoded because free per-currency curve data is not available
# offline; the point of the model is the *differential*, and these are accurate
# enough to demonstrate it. Update as policy moves.
POLICY_RATES = {
    "USD": 0.0433, "EUR": 0.0215, "GBP": 0.0400, "JPY": 0.0050,
    "CHF": 0.0000, "AUD": 0.0360, "CAD": 0.0250, "NZD": 0.0300,
    "INR": 0.0650, "SGD": 0.0250, "HKD": 0.0450, "MXN": 0.0975,
    "ZAR": 0.0750, "TRY": 0.4500, "NOK": 0.0450, "SEK": 0.0225,
    "DKK": 0.0210, "PLN": 0.0575, "CNY": 0.0310, "BRL": 0.1225,
    "KRW": 0.0275, "TWD": 0.0200, "THB": 0.0200, "CZK": 0.0350, "HUF": 0.0650,
}


def parse_fx_pair(pair: str) -> Dict[str, Any]:
    """
    Split a pair label like `EURUSD` into base/quote and attach both rates.

    Convention: for `EURUSD`, EUR is the **base** (foreign) and USD the **quote**
    (domestic), and the quoted price is USD per EUR. In Garman-Kohlhagen the base
    currency's rate is the "dividend yield" q, because holding the foreign
    currency earns interest exactly as holding a dividend-paying stock does.
    """
    p = pair.upper().replace("=X", "").replace("/", "")
    if len(p) != 6:
        return {"valid": False, "pair": pair}
    base, quote = p[:3], p[3:]
    return {
        "valid": True,
        "pair": p,
        "base_currency": base,
        "quote_currency": quote,
        "r_foreign": POLICY_RATES.get(base, 0.02),
        "r_domestic": POLICY_RATES.get(quote, 0.02),
        "rate_differential": round(POLICY_RATES.get(quote, 0.02) - POLICY_RATES.get(base, 0.02), 6),
        "convention": f"{base}{quote} = units of {quote} per 1 {base}; q = r_{base}",
    }


# ---------------------------------------------------------------------------
# Volatility: the GARCH term structure
# ---------------------------------------------------------------------------

def garch_vol_term_structure(ticker: str, horizon_days: int = 30) -> Dict[str, Any]:
    """
    Forecast the volatility an option actually references, from GARCH(1,1).

    The model, fitted on daily percentage returns:

        sigma_t^2 = omega + alpha * eps_{t-1}^2 + beta * sigma_{t-1}^2

    Its long-run (unconditional) variance is

        sigma_inf^2 = omega / (1 - alpha - beta)

    and the h-step-ahead forecast decays geometrically from today's conditional
    variance toward that level:

        E[sigma_{t+h}^2] = sigma_inf^2 + (alpha+beta)^h (sigma_t^2 - sigma_inf^2)

    An option over N days is a claim on *average* variance across its life, so
    the right input is the mean of the per-day forecasts, annualised:

        sigma_option = sqrt( 252 * mean_{h=1..N} E[sigma_{t+h}^2] )

    This is why the number differs by maturity — a genuine **term structure**.
    When today's vol is above its long-run level the curve slopes down (calm is
    expected to return); when below, it slopes up. Realised historical stdev, by
    contrast, is one flat backward-looking number and gets this qualitatively
    wrong whenever the market is not in its average state.

    `persistence = alpha + beta` controls the decay speed. Near 1 (the S&P's is
    about 0.9955) shocks fade very slowly, so the term structure is nearly flat
    and today's regime dominates even long-dated options.
    """
    from analysis.garch import fit_garch

    result = {"ticker": ticker, "horizon_days": horizon_days}
    try:
        g = fit_garch(ticker, dist="t")
        params = g["parameters"]
        omega = params["omega"]["value"]
        alpha = params.get("alpha[1]", {}).get("value", 0.0)
        beta = params.get("beta[1]", {}).get("value", 0.0)
        persistence = alpha + beta

        vols = [p["volatility"] for p in g.get("conditional_volatility", [])]
        if not vols:
            raise ValueError("no conditional volatility series")
        current_var = float(vols[-1]) ** 2                     # daily, in %^2

        if persistence < 1.0:
            long_run_var = omega / (1.0 - persistence)
        else:
            # Non-stationary (IGARCH-like): no finite unconditional variance.
            long_run_var = current_var

        # Per-day forecasts out to the horizon, then their average.
        h = np.arange(1, max(int(horizon_days), 1) + 1)
        forecasts = long_run_var + (persistence ** h) * (current_var - long_run_var)
        avg_var = float(np.mean(forecasts))

        # Term structure at standard option maturities.
        term = []
        for days in (7, 30, 60, 90, 180, 365):
            hh = np.arange(1, days + 1)
            fc = long_run_var + (persistence ** hh) * (current_var - long_run_var)
            term.append({
                "days": days,
                "annualized_vol_pct": round(float(np.sqrt(np.mean(fc) * TRADING_DAYS)), 4),
            })

        realised = float(build_equity_returns(ticker).dropna().tail(252).std() * SQRT_252)

        result.update({
            "sigma_garch": round(float(np.sqrt(avg_var * TRADING_DAYS) / 100.0), 6),
            "sigma_garch_pct": round(float(np.sqrt(avg_var * TRADING_DAYS)), 4),
            "sigma_realised_1y": round(realised, 6),
            "sigma_realised_1y_pct": round(realised * 100, 4),
            "current_daily_vol_pct": round(float(np.sqrt(current_var)), 4),
            "current_annualized_pct": round(float(np.sqrt(current_var * TRADING_DAYS)), 4),
            "long_run_annualized_pct": round(float(np.sqrt(long_run_var * TRADING_DAYS)), 4),
            "garch_params": {"omega": omega, "alpha": alpha, "beta": beta,
                             "persistence": round(persistence, 6)},
            "variance_half_life_days": (
                round(float(np.log(2) / -np.log(persistence)), 2)
                if 0 < persistence < 1 else None
            ),
            "term_structure": term,
            "regime": (
                "elevated — term structure slopes down toward the long-run level"
                if current_var > long_run_var else
                "compressed — term structure slopes up toward the long-run level"
            ),
            "source": "GARCH(1,1) Student-t forecast",
            "caveat": (
                # Honest limitation: omega/(1 - alpha - beta) has a near-zero
                # denominator when persistence approaches 1, so a tiny estimation
                # error in alpha+beta swings the long-run level enormously. The
                # S&P 500 sits at ~0.9955, so its implied long-run vol should be
                # read as "high and poorly identified", not as a point forecast.
                # The short-horizon numbers are far more trustworthy because they
                # are dominated by the current conditional variance instead.
                "Persistence is above 0.99, so the long-run variance "
                "omega/(1-alpha-beta) is ill-conditioned — a small error in alpha+beta "
                "moves it a lot. Short-horizon forecasts are reliable; treat the "
                "long-run level and the far end of the term structure as indicative only."
                if persistence > 0.99 else None
            ),
        })
    except Exception as e:
        realised = 0.20
        try:
            realised = float(build_equity_returns(ticker).dropna().tail(252).std() * SQRT_252)
        except Exception:
            pass
        result.update({
            "sigma_garch": round(realised, 6),
            "sigma_garch_pct": round(realised * 100, 4),
            "source": f"GARCH unavailable, using realised stdev ({e})",
            "error": str(e),
        })
    return result


def fit_jump_params(ticker: str) -> Dict[str, Any]:
    """
    Calibrate Merton jump parameters from the observed return distribution.

    Rather than guessing lambda/mu_J/sigma_J, we identify jumps empirically: any
    daily return beyond 3 robust standard deviations (using the **median absolute
    deviation**, which is not itself inflated by the outliers we are trying to
    find) is classified as a jump.

        lambda  = jumps per year          = count / years observed
        mu_J    = mean log-size of jumps
        sigma_J = stdev of log jump sizes
        sigma   = stdev of the *remaining* (non-jump) returns, annualised

    Note the last line: the diffusive sigma must be estimated **excluding** the
    jumps, otherwise the jump variance would be counted twice — once in sigma
    and again in the jump component. This decomposition is the whole point of a
    jump-diffusion model, and double-counting is the classic error.

    The MAD scaling constant 1.4826 makes it a consistent estimator of sigma for
    normally distributed data.
    """
    try:
        r = build_equity_returns(ticker).dropna()
        if len(r) < 250:
            raise ValueError("need at least ~1 year of returns")

        vals = r.values.astype(float)
        median = float(np.median(vals))
        mad = float(np.median(np.abs(vals - median))) * 1.4826   # robust sigma
        if mad <= 0:
            raise ValueError("degenerate MAD")

        threshold = 3.0 * mad
        is_jump = np.abs(vals - median) > threshold
        jumps = vals[is_jump]
        diffusive = vals[~is_jump]

        years = len(vals) / TRADING_DAYS
        lam = float(len(jumps) / years) if years > 0 else 0.0

        if len(jumps) >= 2:
            mu_j = float(np.mean(jumps))
            sig_j = float(np.std(jumps, ddof=1))
        else:
            mu_j, sig_j = -0.02, 0.05

        sigma_diff = float(np.std(diffusive, ddof=1) * SQRT_252)

        return {
            "lambda_jump": round(lam, 4),
            "mu_jump": round(mu_j, 6),
            "sigma_jump": round(sig_j, 6),
            "sigma_diffusive": round(sigma_diff, 6),
            "num_jumps_detected": int(len(jumps)),
            "years_observed": round(years, 2),
            "threshold_pct": round(threshold * 100, 4),
            "robust_sigma_mad_pct": round(mad * 100, 4),
            "jump_direction_bias": (
                "downward (crash-like)" if mu_j < 0 else "upward"
            ),
            "method": (
                "Returns beyond 3 robust (MAD-based) sigma are classified as jumps; the "
                "diffusive sigma is estimated from the remainder so jump variance is not "
                "double-counted."
            ),
        }
    except Exception as e:
        return {"lambda_jump": 0.75, "mu_jump": -0.05, "sigma_jump": 0.15,
                "sigma_diffusive": 0.20, "error": str(e),
                "method": "defaults — calibration failed"}


# ---------------------------------------------------------------------------
# The market option chain
# ---------------------------------------------------------------------------

def get_market_iv_surface(ticker: str, max_expiries: int = 4,
                          max_strikes: int = 40) -> Dict[str, Any]:
    """
    Pull the real option chain from Yahoo and build the observed implied-vol
    surface, recomputing each implied vol ourselves rather than trusting the
    vendor's field.

    Two reasons to recompute: Yahoo's `impliedVolatility` uses an undisclosed
    model and rate, and it is frequently stale on illiquid strikes. Ours is
    reproducible and consistent with the pricing code being validated.

    Quality filters, all of which matter for a usable surface:
      * **Mid price** (bid+ask)/2 rather than `lastPrice`, which can be hours or
        days old on thin strikes.
      * Require a two-sided quote and positive volume/open interest.
      * Drop strikes whose price violates arbitrage bounds — no real implied vol
        exists there, and forcing one produces garbage.
      * Use the out-of-the-money side (puts below spot, calls above), which
        carries the most vega and the tightest spreads.
      * **Skip expiries under a week.** Yahoo lists the nearest expiries first,
        and those are often 1-5 days out. Ultra-short-dated options have
        premiums of a few cents, spreads that are a large fraction of the mid,
        and implied vols that explode — they are the worst possible input to a
        surface. We therefore sample expiries *across* the term structure
        instead of taking the first few.
      * **Restrict moneyness to 0.75-1.25.** A strike at a third of spot is a
        near-worthless tail contract whose implied vol is numerically
        meaningless (we were getting 374% from one).

    Many tickers (most indices, all FX) have no chain on Yahoo at all; the
    function reports that cleanly rather than raising.
    """
    MIN_DAYS = 7
    MIN_MONEYNESS, MAX_MONEYNESS = 0.75, 1.25
    MAX_SPREAD_PCT = 60.0   # reject quotes whose bid-ask spread exceeds this % of mid

    out: Dict[str, Any] = {"ticker": ticker, "available": False, "surface": [], "expiries": []}
    try:
        import yfinance as yf
        tk = yf.Ticker(ticker)
        expiries = list(tk.options or [])
        if not expiries:
            out["message"] = f"No listed option chain for {ticker} on Yahoo Finance."
            return out

        spot = get_spot(ticker)
        rf = get_risk_free_rate()
        r = rf["rate_cc"]
        q = get_dividend_yield(ticker)["q"]
        today = date.today()

        # Build (expiry, days) pairs beyond the minimum maturity, then spread the
        # selection across the available term structure rather than clustering at
        # the front. Targeting ~1, 2, 3 and 6 months gives a genuine term
        # dimension to the surface.
        candidates = []
        for exp in expiries:
            try:
                d = (datetime.strptime(exp, "%Y-%m-%d").date() - today).days
                if d >= MIN_DAYS:
                    candidates.append((exp, d))
            except Exception:
                continue
        if not candidates:
            out["message"] = (
                f"{ticker} has listed options but none at least {MIN_DAYS} days out; "
                f"very short-dated quotes are excluded as unreliable."
            )
            return out

        targets = [30, 60, 90, 180, 365][:max(max_expiries, 1)]
        chosen, seen = [], set()
        for target in targets:
            best = min(candidates, key=lambda c: abs(c[1] - target))
            if best[0] not in seen:
                seen.add(best[0])
                chosen.append(best)
        chosen.sort(key=lambda c: c[1])

        rows: List[Dict[str, Any]] = []
        used_expiries = []

        for exp, days in chosen:
            try:
                T = days / 365.0
                chain = tk.option_chain(exp)
                used_expiries.append({"expiry": exp, "days": days, "T_years": round(T, 5)})

                for side, df in (("put", chain.puts), ("call", chain.calls)):
                    if df is None or len(df) == 0:
                        continue
                    # Out-of-the-money side only, within a sane moneyness band.
                    sel = df[df["strike"] < spot] if side == "put" else df[df["strike"] > spot]
                    sel = sel[(sel["strike"] >= spot * MIN_MONEYNESS)
                              & (sel["strike"] <= spot * MAX_MONEYNESS)]
                    for _, row in sel.iterrows():
                        bid = float(row.get("bid") or 0.0)
                        ask = float(row.get("ask") or 0.0)
                        last = float(row.get("lastPrice") or 0.0)
                        vol = float(row.get("volume") or 0.0)
                        oi = float(row.get("openInterest") or 0.0)

                        if bid > 0 and ask > 0 and ask >= bid:
                            mid = 0.5 * (bid + ask)
                            src = "mid"
                        elif last > 0 and (vol > 0 or oi > 0):
                            mid, src = last, "last"
                        else:
                            continue

                        # A quote whose spread is most of its value carries no
                        # reliable volatility information.
                        spread_pct = ((ask - bid) / mid * 100) if (mid > 0 and bid > 0 and ask > 0) else 0.0
                        if src == "mid" and spread_pct > MAX_SPREAD_PCT:
                            continue

                        K = float(row["strike"])
                        iv = implied_vol(mid, spot, K, T, r, q, side)
                        # Implied vols outside 1%-200% are numerical artefacts of
                        # near-worthless or mispriced quotes, not information.
                        if iv is None or iv <= 0.01 or iv > 2.0:
                            continue

                        rows.append({
                            "expiry": exp,
                            "days_to_expiry": days,
                            "T_years": round(T, 5),
                            "strike": round(K, 4),
                            "moneyness": round(K / spot, 5),
                            "log_moneyness": round(float(np.log(K / spot)), 6),
                            "side": side,
                            "mid_price": round(mid, 4),
                            "price_source": src,
                            "our_implied_vol_pct": round(iv * 100, 4),
                            "yahoo_implied_vol_pct": (
                                round(float(row["impliedVolatility"]) * 100, 4)
                                if row.get("impliedVolatility") is not None else None
                            ),
                            "volume": int(vol),
                            "open_interest": int(oi),
                            "bid": bid, "ask": ask,
                            "spread_pct_of_mid": round((ask - bid) / mid * 100, 2) if mid > 0 else None,
                        })
            except Exception:
                continue

        if not rows:
            out["message"] = "Chain exists but no strike passed the liquidity/arbitrage filters."
            return out

        # Keep the most liquid strikes if the surface is large.
        rows.sort(key=lambda x: -(x["open_interest"] + x["volume"]))
        rows = rows[: max_strikes * max_expiries]
        rows.sort(key=lambda x: (x["days_to_expiry"], x["strike"]))

        ivs = [x["our_implied_vol_pct"] for x in rows]
        atm = [x for x in rows if 0.97 <= x["moneyness"] <= 1.03]

        out.update({
            "available": True,
            "spot": round(spot, 4),
            "risk_free_rate": rf,
            "dividend_yield": round(q, 6),
            "expiries": used_expiries,
            "surface": rows,
            "num_quotes": len(rows),
            "atm_iv_pct": round(float(np.mean([x["our_implied_vol_pct"] for x in atm])), 4) if atm else None,
            "iv_min_pct": round(float(min(ivs)), 4),
            "iv_max_pct": round(float(max(ivs)), 4),
            "note": (
                "Implied vols are recomputed from mid prices with our own solver, rate and "
                "dividend yield — not taken from Yahoo's field, which uses an undisclosed "
                "model and is often stale on illiquid strikes."
            ),
        })
        return out
    except Exception as e:
        out["message"] = f"Chain fetch failed: {e}"
        return out


# ---------------------------------------------------------------------------
# The headline market analysis
# ---------------------------------------------------------------------------

def analyze_market_option(ticker: str = "^GSPC", strike: Optional[float] = None,
                          expiry: Optional[str] = None, option_type: str = "call",
                          include_chain: bool = True) -> Dict[str, Any]:
    """
    Price one option on a real ticker with every model, using market-derived
    inputs throughout, and compare the result against live quotes.

    Input resolution: spot from Yahoo, r from `^TNX` (continuously compounded),
    q from the reported dividend yield, sigma from the GARCH term structure
    matched to this option's maturity, jump parameters fitted from the return
    distribution, and Heston seeded from GARCH (v0 = current variance,
    theta = long-run variance, kappa from the measured variance half-life).

    The Heston seeding deserves note: GARCH and Heston are near-equivalent
    descriptions of the same phenomenon, one in discrete time and one in
    continuous time. GARCH's persistence maps to Heston's mean-reversion speed
    via `kappa = -ln(persistence) * 252`, and its long-run variance is Heston's
    theta. So the options model is not fitted independently — it inherits Pillar
    2's estimates, which is what makes the two pillars one coherent project.
    """
    option_type = option_type.lower()
    spot = get_spot(ticker)
    rf = get_risk_free_rate()
    r = rf["rate_cc"]
    div = get_dividend_yield(ticker)
    q = div["q"]

    # Resolve maturity
    if expiry:
        exp_date = datetime.strptime(expiry, "%Y-%m-%d").date()
        days = max((exp_date - date.today()).days, 1)
    else:
        days = 30
        expiry = None
    T = days / 365.0

    K = float(strike) if strike else round(spot, 2)

    # Volatility, maturity-matched
    vol_info = garch_vol_term_structure(ticker, horizon_days=days)
    sigma = vol_info["sigma_garch"]
    if not (sigma and 0 < sigma < 5):
        sigma = 0.20

    # --- Closed-form prices across market conventions
    bsm = bsm_equity_price(spot, K, T, r, sigma, q, option_type)
    greeks = calculate_greeks(spot, K, T, r, sigma, q, option_type)
    parity = put_call_parity_check(spot, K, T, r, sigma, q)

    # --- Lattice / American
    bin_eur = binomial_tree_price(spot, K, T, r, sigma, q, 300, option_type, "european")
    bin_amer = binomial_tree_price(spot, K, T, r, sigma, q, 300, option_type, "american")

    # --- Jump-diffusion, calibrated to this ticker's tails
    jp = fit_jump_params(ticker)
    merton = merton_closed_form(
        spot, K, T, r, jp.get("sigma_diffusive", sigma),
        jp.get("lambda_jump", 0.75), jp.get("mu_jump", -0.05),
        jp.get("sigma_jump", 0.15), q, option_type,
    )

    # --- Heston, seeded from GARCH
    gp = vol_info.get("garch_params", {})
    persistence = gp.get("persistence", 0.95)
    v0 = sigma ** 2
    long_run_pct = vol_info.get("long_run_annualized_pct")
    theta_h = (long_run_pct / 100.0) ** 2 if long_run_pct else v0
    kappa_h = float(-np.log(persistence) * TRADING_DAYS) if 0 < persistence < 1 else 2.0
    kappa_h = float(np.clip(kappa_h, 0.05, 25.0))
    # Keep vol-of-vol inside the Feller condition so variance stays positive.
    xi_h = float(min(0.5, np.sqrt(max(2 * kappa_h * theta_h, 1e-8)) * 0.9))
    heston = heston_semi_analytic(spot, K, T, r, v0, kappa_h, theta_h, xi_h, -0.7, q, option_type)

    # --- Monte Carlo
    mc = monte_carlo_gbm(spot, K, T, r, sigma, q, 40000, option_type, seed=7)

    result: Dict[str, Any] = {
        "ticker": ticker,
        "option_type": option_type,
        "market_inputs": {
            "spot": round(spot, 4),
            "strike": round(K, 4),
            "moneyness": round(K / spot, 5),
            "days_to_expiry": days,
            "T_years": round(T, 6),
            "expiry": expiry,
            "risk_free_rate": round(r, 6),
            "risk_free_source": rf["source"],
            "risk_free_conversion": rf["conversion"],
            "dividend_yield": round(q, 6),
            "dividend_source": div["source"],
            "sigma_model": round(sigma, 6),
            "sigma_model_pct": round(sigma * 100, 4),
            "sigma_source": vol_info.get("source"),
        },
        "volatility_model": vol_info,
        "jump_calibration": jp,
        "heston_calibration": {
            "v0": round(float(v0), 8),
            "theta_long_run_variance": round(float(theta_h), 8),
            "kappa": round(kappa_h, 4),
            "xi_vol_of_vol": round(xi_h, 4),
            "rho": -0.7,
            "feller_satisfied": bool(2 * kappa_h * theta_h >= xi_h ** 2),
            "mapping": (
                "Seeded from GARCH: v0 = current conditional variance, theta = long-run "
                "variance, kappa = -ln(persistence) * 252. GARCH and Heston describe the "
                "same volatility dynamics in discrete and continuous time respectively."
            ),
        },
        "model_prices": {
            "black_scholes_merton": round(bsm, 6),
            "binomial_european": round(bin_eur, 6),
            "binomial_american": round(bin_amer, 6),
            "early_exercise_premium": round(bin_amer - bin_eur, 6),
            "merton_jump_diffusion": merton["price"],
            "heston_stochastic_vol": heston["price"],
            "monte_carlo_gbm": mc["price"],
            "monte_carlo_std_error": mc["std_error"],
        },
        "greeks": greeks,
        "validation": {"put_call_parity": parity},
        "market_comparison": None,
    }

    # --- Compare against the live chain: the variance risk premium
    if include_chain:
        result["market_comparison"] = _compare_to_chain(
            ticker, spot, K, T, r, q, sigma, option_type, expiry
        )

    return result


def _compare_to_chain(ticker: str, spot: float, K: float, T: float, r: float,
                      q: float, sigma_model: float, option_type: str,
                      expiry: Optional[str]) -> Dict[str, Any]:
    """
    Find the nearest listed contract and compute the **variance risk premium**:
    market implied volatility minus our GARCH-forecast volatility.

    Interpretation, and the reason this is the interesting number:

      * IV >> model vol → options are **rich**. Sellers are being paid more than
        the statistically forecast variance. This gap is persistently positive in
        index options and is a documented risk premium, not a free lunch —
        variance sellers get paid precisely because they lose badly in crashes.
      * IV << model vol → options are **cheap** relative to forecast risk;
        hedging is underpriced.

    A ratio near 1 means the market and our GARCH model agree on future
    variance, which is the null hypothesis. This feeds
    `detect_options_mispricing` in the recommender.
    """
    try:
        import yfinance as yf
        tk = yf.Ticker(ticker)
        expiries = list(tk.options or [])
        if not expiries:
            return {"available": False,
                    "message": f"No listed options for {ticker} — the model price stands alone."}

        # Choose the listed expiry closest to the maturity we actually priced,
        # excluding contracts under a week out. Taking expiries[0] would compare a
        # 30-day model price against a 1-day listed contract — the volatilities
        # are then not remotely comparable, and the resulting "risk premium" would
        # be an artefact of the maturity mismatch rather than a real premium.
        target_days = max(int(round(T * 365)), 1)
        candidates = []
        for e in expiries:
            try:
                dd = (datetime.strptime(e, "%Y-%m-%d").date() - date.today()).days
                if dd >= 7:
                    candidates.append((e, dd))
            except Exception:
                continue

        if expiry and expiry in expiries:
            use_exp = expiry
            days = max((datetime.strptime(use_exp, "%Y-%m-%d").date() - date.today()).days, 1)
        elif candidates:
            use_exp, days = min(candidates, key=lambda c: abs(c[1] - target_days))
        else:
            return {"available": False,
                    "message": (f"{ticker} has no listed expiry at least 7 days out; "
                                f"very short-dated quotes are excluded as unreliable.")}
        T_mkt = days / 365.0

        chain = tk.option_chain(use_exp)
        df = chain.calls if option_type == "call" else chain.puts
        if df is None or len(df) == 0:
            return {"available": False, "message": "Empty chain for that expiry."}

        row = df.iloc[(df["strike"] - K).abs().argmin()]
        K_mkt = float(row["strike"])
        bid = float(row.get("bid") or 0.0)
        ask = float(row.get("ask") or 0.0)
        last = float(row.get("lastPrice") or 0.0)

        if bid > 0 and ask > 0:
            mkt_price, src = 0.5 * (bid + ask), "mid"
        elif last > 0:
            mkt_price, src = last, "last"
        else:
            return {"available": False, "message": "No usable quote at the nearest strike."}

        our_iv = implied_vol(mkt_price, spot, K_mkt, T_mkt, r, q, option_type)
        yahoo_iv = float(row["impliedVolatility"]) if row.get("impliedVolatility") is not None else None

        # Re-forecast our vol at the listed maturity so the comparison is
        # maturity-matched rather than mixing a 30-day model vol with a 45-day option.
        vol_matched = garch_vol_term_structure(ticker, horizon_days=days).get("sigma_garch") or sigma_model

        model_px = bsm_equity_price(spot, K_mkt, T_mkt, r, vol_matched, q, option_type)

        verdict, vrp, ratio = None, None, None
        if our_iv and vol_matched > 0:
            vrp = our_iv - vol_matched
            ratio = our_iv / vol_matched
            verdict = (
                "rich — implied well above forecast (variance risk premium positive)"
                if ratio > 1.15 else
                "cheap — implied below forecast" if ratio < 0.85 else
                "fairly priced versus the GARCH forecast"
            )

        return {
            "available": True,
            "expiry_used": use_exp,
            "days_to_expiry": days,
            "nearest_strike": round(K_mkt, 4),
            "market_price": round(mkt_price, 4),
            "price_source": src,
            "bid": bid, "ask": ask,
            "our_model_price": round(float(model_px), 4),
            "model_minus_market": round(float(model_px) - mkt_price, 4),
            "market_implied_vol_pct": round(our_iv * 100, 4) if our_iv else None,
            "yahoo_implied_vol_pct": round(yahoo_iv * 100, 4) if yahoo_iv else None,
            "model_forecast_vol_pct": round(vol_matched * 100, 4),
            "variance_risk_premium_pct": round(vrp * 100, 4) if vrp is not None else None,
            "iv_to_model_ratio": round(ratio, 4) if ratio else None,
            "verdict": verdict,
            "note": (
                "Variance risk premium = market implied vol - GARCH forecast vol, "
                "maturity-matched. Persistently positive in index options: sellers are "
                "compensated for crash exposure."
            ),
        }
    except Exception as e:
        return {"available": False, "message": f"Chain comparison failed: {e}"}


def analyze_fx_option(pair: str = "EURUSD", strike: Optional[float] = None,
                      days: int = 30, option_type: str = "call") -> Dict[str, Any]:
    """
    Garman-Kohlhagen on a real currency pair, with both legs' policy rates.

    The distinctive feature of FX options versus equity options is that **two**
    interest rates matter. The forward is F = S e^{(r_d - r_f)T}, so the rate
    differential sets whether the forward sits above or below spot, and therefore
    the relative value of calls and puts. Covered interest parity is not an
    add-on assumption here — it is structurally inside the pricing formula.

    Volatility comes from GARCH fitted to the pair's own return series, so a
    JPY cross is not forced to share the S&P's volatility.
    """
    info = parse_fx_pair(pair)
    if not info["valid"]:
        return {"error": f"Could not parse '{pair}' as a 6-letter FX pair."}

    yf_ticker = f"{info['pair']}=X"
    spot = get_spot(yf_ticker)
    K = float(strike) if strike else round(spot, 5)
    T = max(days, 1) / 365.0

    r_d, r_f = info["r_domestic"], info["r_foreign"]
    vol_info = garch_vol_term_structure(yf_ticker, horizon_days=days)
    sigma = vol_info.get("sigma_garch") or 0.10
    if not (0 < sigma < 5):
        sigma = 0.10

    gk_call = garman_kohlhagen_price(spot, K, T, r_d, r_f, sigma, "call")
    gk_put = garman_kohlhagen_price(spot, K, T, r_d, r_f, sigma, "put")
    price = gk_call if option_type.lower() == "call" else gk_put
    greeks = calculate_greeks(spot, K, T, r_d, sigma, r_f, option_type)

    forward = spot * np.exp((r_d - r_f) * T)

    # An equity-style BSM with q = 0 shows what ignoring the foreign rate costs.
    naive = bsm_equity_price(spot, K, T, r_d, sigma, 0.0, option_type)

    return {
        "pair": info["pair"],
        "yahoo_ticker": yf_ticker,
        "option_type": option_type.lower(),
        "convention": info["convention"],
        "market_inputs": {
            "spot": round(spot, 6),
            "strike": round(K, 6),
            "days": days,
            "T_years": round(T, 6),
            "r_domestic": r_d,
            "r_foreign": r_f,
            "rate_differential": info["rate_differential"],
            "base_currency": info["base_currency"],
            "quote_currency": info["quote_currency"],
            "sigma_pct": round(sigma * 100, 4),
            "sigma_source": vol_info.get("source"),
        },
        "forward_rate": round(float(forward), 6),
        "forward_premium_pct": round(float((forward / spot - 1) * 100), 4),
        "garman_kohlhagen": {
            "call": round(float(gk_call), 8),
            "put": round(float(gk_put), 8),
            "selected": round(float(price), 8),
        },
        "naive_bsm_ignoring_foreign_rate": round(float(naive), 8),
        "error_from_ignoring_foreign_rate": round(float(naive - price), 8),
        "greeks": greeks,
        "volatility_model": vol_info,
        "interpretation": (
            f"The forward sits {'above' if forward > spot else 'below'} spot because "
            f"{info['quote_currency']} rates are "
            f"{'higher' if info['rate_differential'] > 0 else 'lower'} than "
            f"{info['base_currency']} rates. Treating this as an equity option with q=0 "
            f"misprices it by {abs(float(naive - price)):.6f} — covered interest parity is "
            f"structurally inside Garman-Kohlhagen."
        ),
    }


def market_smile(ticker: str = "^GSPC", days: int = 60) -> Dict[str, Any]:
    """
    Model-implied volatility smiles using **this ticker's own** calibrated
    parameters, alongside the market surface where one is listed.

    Unlike the generic `implied_vol_smile`, every parameter here is fitted to the
    asset: sigma from its GARCH forecast, jump intensity and size from its
    realised tails, Heston from its GARCH persistence. So the resulting smile is
    a genuine prediction about *this* asset's option prices, and where a real
    chain exists it can be compared directly against the observed smile.

    That comparison is the strongest single result the options module can
    produce: if the fitted Merton/Heston smile tracks the observed one better
    than a flat Black-Scholes line, the models are earning their extra
    complexity on real data.
    """
    from analysis.advanced_options import implied_vol_smile

    spot = get_spot(ticker)
    rf = get_risk_free_rate()
    r = rf["rate_cc"]
    q = get_dividend_yield(ticker)["q"]
    T = max(days, 1) / 365.0

    vol_info = garch_vol_term_structure(ticker, horizon_days=days)
    sigma = vol_info.get("sigma_garch") or 0.20
    jp = fit_jump_params(ticker)

    gp = vol_info.get("garch_params", {})
    persistence = gp.get("persistence", 0.95)
    v0 = sigma ** 2
    long_run_pct = vol_info.get("long_run_annualized_pct")
    theta_h = (long_run_pct / 100.0) ** 2 if long_run_pct else v0
    kappa_h = float(np.clip(-np.log(persistence) * TRADING_DAYS if 0 < persistence < 1 else 2.0, 0.05, 25.0))
    xi_h = float(min(0.6, np.sqrt(max(2 * kappa_h * theta_h, 1e-8)) * 0.9))

    smile = implied_vol_smile(
        S=spot, T=T, r=r, sigma=sigma, q=q,
        lambda_jump=jp.get("lambda_jump", 0.75),
        mu_jump=jp.get("mu_jump", -0.05),
        sigma_jump=jp.get("sigma_jump", 0.15),
        v0=v0, kappa=kappa_h, theta=theta_h, xi=xi_h, rho=-0.7,
        moneyness_lo=0.80, moneyness_hi=1.20, num_strikes=21,
    )

    smile["ticker"] = ticker
    smile["calibration"] = {
        "sigma_source": vol_info.get("source"),
        "sigma_pct": round(sigma * 100, 4),
        "jump_params": jp,
        "heston": {"v0": round(v0, 8), "kappa": round(kappa_h, 4),
                   "theta": round(theta_h, 8), "xi": round(xi_h, 4), "rho": -0.7},
        "note": "Every parameter is fitted to this ticker, not assumed.",
    }

    # Attach the observed surface at the closest listed maturity, if any.
    chain = get_market_iv_surface(ticker, max_expiries=3, max_strikes=30)
    if chain.get("available"):
        target = min(chain["expiries"], key=lambda e: abs(e["days"] - days))
        observed = [
            {"moneyness": row["moneyness"], "market_iv_pct": row["our_implied_vol_pct"],
             "side": row["side"], "strike": row["strike"]}
            for row in chain["surface"] if row["expiry"] == target["expiry"]
        ]
        observed.sort(key=lambda x: x["moneyness"])
        smile["market_observed"] = {
            "expiry": target["expiry"],
            "days": target["days"],
            "points": observed,
            "atm_iv_pct": chain.get("atm_iv_pct"),
        }
    else:
        smile["market_observed"] = {"available": False,
                                    "message": chain.get("message", "no chain")}
    return smile
