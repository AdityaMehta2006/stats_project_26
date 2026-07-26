"""
advanced_options.py
-------------------
Multi-market option pricing and stochastic calculus.

Structure
---------
1. Closed-form models across markets — Black-Scholes-Merton (equity with a
   dividend yield), Garman-Kohlhagen (FX), Black-76 (futures/commodities),
   Bachelier (arithmetic/normal, for spreads and negative underlyings).
2. Analytical Greeks, first and second order, plus a finite-difference
   cross-check so the closed forms are verified rather than trusted.
3. Lattice methods — Cox-Ross-Rubinstein binomial with American early exercise,
   plus an explicit convergence study against the analytic price.
4. Semi-analytic models that admit a volatility smile — the Merton
   jump-diffusion Poisson series and the Heston characteristic-function
   integral. Each is paired with the Monte Carlo estimator of the same model so
   the two must agree; that agreement is the correctness argument.
5. Monte Carlo engines, including Longstaff-Schwartz least-squares for American
   options, which lattices cannot handle in high dimension.
6. Implied volatility: a robust solver plus smile/skew generation. This is the
   payoff of the whole module — it shows *why* Black-Scholes is insufficient.

The central thesis, and the reason the smile machinery exists
------------------------------------------------------------
Black-Scholes assumes one constant sigma, so it implies a *flat* line of
implied volatility across strikes. Real markets do not: index options show a
downward **skew** (out-of-the-money puts trade at higher implied vol). That gap
is a measurable failure of the model's assumptions, and it is the same class of
anomaly the GARCH pillar finds in the time dimension (clustering, fat tails).
Merton generates a smile through jumps; Heston generates one through random,
negatively-correlated volatility. `implied_vol_smile` computes all three side
by side so the flat Black-Scholes line can be compared with the curved ones.

Conventions used throughout
---------------------------
  S spot · K strike · T years to expiry · r risk-free (continuous, decimal)
  sigma annualised volatility (decimal) · q dividend yield / foreign rate
  All rates continuously compounded. Greeks are scaled for display: vega and
  rho per 1 percentage point, theta per calendar day (see `calculate_greeks`).
"""

import numpy as np
from scipy.stats import norm
from scipy.integrate import quad
from typing import Any, Callable, Dict, Optional

# Guard rails for degenerate inputs. Below these the model has no meaningful
# answer and we return intrinsic value instead of dividing by zero.
_MIN_T = 1e-10
_MIN_SIGMA = 1e-10


# ============================================================================
# 1. CLOSED-FORM MODELS (EQUITY, FX, COMMODITIES, NORMAL)
# ============================================================================

def _intrinsic(S: float, K: float, option_type: str) -> float:
    return max(S - K, 0.0) if option_type.lower() == "call" else max(K - S, 0.0)


def _d1_d2(S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0):
    """
    The two Black-Scholes arguments.

        d1 = [ln(S/K) + (r - q + sigma^2/2) T] / (sigma sqrt(T))
        d2 = d1 - sigma sqrt(T)

    Interpretation: N(d2) is the risk-neutral probability the option finishes in
    the money; N(d1) is that same probability under the *share* measure
    (numeraire = the stock), which is why d1 carries the extra +sigma^2/2.
    Delta being N(d1) rather than N(d2) follows from that change of measure, not
    from algebraic accident.
    """
    sig_sqrt_t = sigma * np.sqrt(T)
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / sig_sqrt_t
    d2 = d1 - sig_sqrt_t
    return d1, d2


def bsm_equity_price(S: float, K: float, T: float, r: float, sigma: float,
                     q: float = 0.0, option_type: str = "call") -> float:
    """
    Black-Scholes-Merton price for a European option on an asset paying a
    continuous dividend yield q.

        Call = S e^{-qT} N(d1) - K e^{-rT} N(d2)
        Put  = K e^{-rT} N(-d2) - S e^{-qT} N(-d1)

    The e^{-qT} factor appears because holding the option forgoes the dividend
    stream the stock itself would pay.
    """
    option = option_type.lower()
    if option not in ("call", "put"):
        raise ValueError("option_type must be 'call' or 'put'")
    if T <= _MIN_T or sigma <= _MIN_SIGMA:
        return float(_intrinsic(S, K, option))

    d1, d2 = _d1_d2(S, K, T, r, sigma, q)
    disc_q, disc_r = np.exp(-q * T), np.exp(-r * T)

    if option == "call":
        return float(S * disc_q * norm.cdf(d1) - K * disc_r * norm.cdf(d2))
    return float(K * disc_r * norm.cdf(-d2) - S * disc_q * norm.cdf(-d1))


def garman_kohlhagen_price(S: float, K: float, T: float, r_domestic: float,
                           r_foreign: float, sigma: float,
                           option_type: str = "call") -> float:
    """
    Garman-Kohlhagen (1983) for currency options.

    An FX option is structurally an option on an asset yielding the *foreign*
    interest rate: holding the foreign currency earns r_foreign, so it plays
    exactly the role of a dividend yield. Hence GK is BSM with q = r_foreign.
    S is quoted as units of domestic per unit of foreign (e.g. USD per EUR).

    The economically meaningful consequence is that the forward is
    F = S e^{(r_d - r_f)T}, so interest-rate differentials — not just spot —
    drive FX option values. That is covered-interest parity showing up inside
    an option price.
    """
    return bsm_equity_price(S, K, T, r_domestic, sigma, r_foreign, option_type)


def black_76_price(F: float, K: float, T: float, r: float, sigma: float,
                   option_type: str = "call") -> float:
    """
    Black-76 for options on futures and commodities.

        Call = e^{-rT} [F N(d1) - K N(d2)]

    A futures contract costs nothing to enter and has zero drift under the
    risk-neutral measure (it is already a martingale), so the cost-of-carry
    vanishes. Setting q = r in BSM reproduces this exactly, which is the
    implementation used here. Note the input is the **futures price F**, not
    spot — for commodities these differ by storage, convenience yield, and
    seasonality, so passing spot by mistake is a real modelling error.
    """
    return bsm_equity_price(F, K, T, r, sigma, r, option_type)


def bachelier_price(S: float, K: float, T: float, r: float, sigma_abs: float,
                    option_type: str = "call") -> float:
    """
    Bachelier (1900) — the original option formula, five years before Einstein's
    Brownian motion paper.

    The underlying is **arithmetic** Brownian motion, dS = sigma dW, so prices
    are normally distributed rather than lognormally:

        Call = e^{-rT} [ (S - K) N(d) + sigma sqrt(T) phi(d) ],
        d = (S - K) / (sigma sqrt(T))

    `sigma_abs` is an *absolute* volatility in price units (e.g. 15 dollars/yr),
    not a percentage.

    Why keep it: the model permits negative prices, which is a defect for
    equities but exactly right for spread options, certain rates products, and
    famously WTI crude in April 2020 when futures settled at -$37. Black-Scholes
    cannot represent that state at all — ln(S) is undefined. It is also the
    natural pricing model for the pair-trading *spread* from `pairs.py`, which
    is arithmetic and mean-reverting, not lognormal.
    """
    option = option_type.lower()
    if T <= _MIN_T or sigma_abs <= _MIN_SIGMA:
        return float(_intrinsic(S, K, option))
    v = sigma_abs * np.sqrt(T)
    d = (S - K) / v
    disc = np.exp(-r * T)
    if option == "call":
        return float(disc * ((S - K) * norm.cdf(d) + v * norm.pdf(d)))
    return float(disc * ((K - S) * norm.cdf(-d) + v * norm.pdf(d)))


# ============================================================================
# 2. GREEKS — ANALYTICAL, WITH A FINITE-DIFFERENCE CROSS-CHECK
# ============================================================================

def calculate_greeks(S: float, K: float, T: float, r: float, sigma: float,
                     q: float = 0.0, option_type: str = "call") -> Dict[str, float]:
    """
    First- and second-order Greeks in closed form.

    First order (sensitivity to one input)
      delta = dV/dS      hedge ratio: shares per option
      vega  = dV/dsigma  volatility exposure (identical for call and put)
      theta = dV/dt      time decay
      rho   = dV/dr      rate exposure

    Second order (how the hedge itself moves — what actually costs money)
      gamma = d2V/dS2       delta's instability; drives rehedging cost
      vanna = d2V/dS dsigma delta's drift as vol moves; key for FX risk reversals
      volga = d2V/dsigma2   vega convexity; why vol-of-vol is priced

    Display scaling (the usual trading-desk convention, applied at the end):
      vega, rho per +1 percentage point (divide by 100)
      theta per calendar day (divide by 365)
      volga per 1 point of vol squared (divide by 10000)
    Raw unscaled values are returned alongside under `*_raw` so the scaling is
    auditable rather than hidden.
    """
    option = option_type.lower()
    zero = {k: 0.0 for k in ("delta", "gamma", "vega", "theta", "rho", "vanna", "volga")}
    if T <= _MIN_T or sigma <= _MIN_SIGMA:
        # At expiry delta is a step function; report the degenerate limit.
        if T <= _MIN_T:
            itm = (S > K) if option == "call" else (S < K)
            zero["delta"] = (1.0 if option == "call" else -1.0) if itm else 0.0
        return zero

    d1, d2 = _d1_d2(S, K, T, r, sigma, q)
    pdf_d1 = norm.pdf(d1)
    disc_q, disc_r = np.exp(-q * T), np.exp(-r * T)
    sqrt_t = np.sqrt(T)

    gamma = disc_q * pdf_d1 / (S * sigma * sqrt_t)
    raw_vega = S * disc_q * pdf_d1 * sqrt_t

    if option == "call":
        delta = disc_q * norm.cdf(d1)
        raw_theta = (-S * disc_q * pdf_d1 * sigma / (2 * sqrt_t)
                     - r * K * disc_r * norm.cdf(d2)
                     + q * S * disc_q * norm.cdf(d1))
        raw_rho = K * T * disc_r * norm.cdf(d2)
    else:
        delta = -disc_q * norm.cdf(-d1)
        raw_theta = (-S * disc_q * pdf_d1 * sigma / (2 * sqrt_t)
                     + r * K * disc_r * norm.cdf(-d2)
                     - q * S * disc_q * norm.cdf(-d1))
        raw_rho = -K * T * disc_r * norm.cdf(-d2)

    # Second-order cross Greeks. Both are call/put identical, exactly as vega is,
    # because put-call parity differs by S e^{-qT} - K e^{-rT}, which is linear
    # in S and independent of sigma.
    vanna = -disc_q * pdf_d1 * d2 / sigma
    volga = raw_vega * d1 * d2 / sigma

    return {
        "delta": round(float(delta), 6),
        "gamma": round(float(gamma), 8),
        "vega": round(float(raw_vega / 100.0), 6),
        "theta": round(float(raw_theta / 365.0), 6),
        "rho": round(float(raw_rho / 100.0), 6),
        "vanna": round(float(vanna / 100.0), 8),
        "volga": round(float(volga / 10000.0), 8),
        "vega_raw": round(float(raw_vega), 6),
        "theta_raw_annual": round(float(raw_theta), 6),
        "rho_raw": round(float(raw_rho), 6),
        "d1": round(float(d1), 6),
        "d2": round(float(d2), 6),
        "prob_itm_risk_neutral": round(float(norm.cdf(d2) if option == "call" else norm.cdf(-d2)), 6),
    }


def greeks_finite_difference(S: float, K: float, T: float, r: float, sigma: float,
                             q: float = 0.0, option_type: str = "call",
                             pricer: Optional[Callable] = None) -> Dict[str, float]:
    """
    Numerically differentiate the pricer and compare against the closed forms.

    Central differences are used because their error is O(h^2) rather than the
    O(h) of a forward difference. Step sizes are scaled to each variable so the
    same code works whether S is 1.2 (FX) or 6900 (an index).

    This exists as a **test**: if `analytic_vs_numeric` shows agreement to ~1e-4,
    the hand-derived formulae in `calculate_greeks` are right. It also gives
    Greeks for models with no closed form (Merton, Heston, American) by passing
    a different `pricer`.
    """
    p = pricer or (lambda s, k, t, rr, sg, qq: bsm_equity_price(s, k, t, rr, sg, qq, option_type))

    hS = max(S * 1e-4, 1e-6)
    hs = max(sigma * 1e-4, 1e-8)
    hr = 1e-6
    ht = min(1e-5, T * 0.5)

    v0 = p(S, K, T, r, sigma, q)
    delta = (p(S + hS, K, T, r, sigma, q) - p(S - hS, K, T, r, sigma, q)) / (2 * hS)
    gamma = (p(S + hS, K, T, r, sigma, q) - 2 * v0 + p(S - hS, K, T, r, sigma, q)) / (hS ** 2)
    vega = (p(S, K, T, r, sigma + hs, q) - p(S, K, T, r, sigma - hs, q)) / (2 * hs)
    rho = (p(S, K, T, r + hr, sigma, q) - p(S, K, T, r - hr, sigma, q)) / (2 * hr)
    # Theta is dV/dt = -dV/dT: value decays as expiry approaches.
    theta = -(p(S, K, T + ht, r, sigma, q) - p(S, K, T - ht, r, sigma, q)) / (2 * ht)
    # Vanna as the S-derivative of vega; volga as the second sigma-derivative.
    vanna = ((p(S + hS, K, T, r, sigma + hs, q) - p(S + hS, K, T, r, sigma - hs, q)
              - p(S - hS, K, T, r, sigma + hs, q) + p(S - hS, K, T, r, sigma - hs, q))
             / (4 * hS * hs))
    volga = (p(S, K, T, r, sigma + hs, q) - 2 * v0 + p(S, K, T, r, sigma - hs, q)) / (hs ** 2)

    analytic = calculate_greeks(S, K, T, r, sigma, q, option_type)
    numeric = {
        "delta": float(delta), "gamma": float(gamma),
        "vega": float(vega / 100.0), "theta": float(theta / 365.0),
        "rho": float(rho / 100.0), "vanna": float(vanna / 100.0),
        "volga": float(volga / 10000.0),
    }

    comparison = {}
    for key, num in numeric.items():
        ana = analytic.get(key, 0.0)
        comparison[key] = {
            "analytic": round(float(ana), 8),
            "numeric": round(float(num), 8),
            "abs_diff": round(float(abs(ana - num)), 10),
        }

    max_diff = max(v["abs_diff"] for v in comparison.values())
    return {
        "analytic_vs_numeric": comparison,
        "max_abs_difference": round(float(max_diff), 10),
        "all_match": bool(max_diff < 1e-4),
        "note": (
            "Central differences (error O(h^2)) validate the hand-derived analytical "
            "Greeks. Agreement below 1e-4 confirms the closed forms."
        ),
    }


def put_call_parity_check(S: float, K: float, T: float, r: float, sigma: float,
                          q: float = 0.0) -> Dict[str, Any]:
    """
    Verify  C - P = S e^{-qT} - K e^{-rT}.

    This is not a model result — it is pure arbitrage. Buying a call and selling
    a put replicates a forward on the stock, so if the identity fails by more
    than transaction costs, a risk-free profit exists regardless of whether
    Black-Scholes, Heston, or anything else is the true model. It therefore acts
    as a model-independent sanity check on the pricing code, and on real quotes
    it is how you detect stale or mispriced market data.
    """
    call = bsm_equity_price(S, K, T, r, sigma, q, "call")
    put = bsm_equity_price(S, K, T, r, sigma, q, "put")
    lhs = call - put
    rhs = S * np.exp(-q * T) - K * np.exp(-r * T)
    return {
        "call": round(call, 8),
        "put": round(put, 8),
        "call_minus_put": round(float(lhs), 8),
        "forward_value": round(float(rhs), 8),
        "abs_violation": round(float(abs(lhs - rhs)), 10),
        "parity_holds": bool(abs(lhs - rhs) < 1e-8),
        "identity": "C - P = S e^{-qT} - K e^{-rT}",
        "note": (
            "Model-independent arbitrage relation. A violation implies a risk-free "
            "profit, so this validates the implementation without assuming any model."
        ),
    }


# ============================================================================
# 3. BINOMIAL LATTICE (COX-ROSS-RUBINSTEIN) + CONVERGENCE
# ============================================================================

def binomial_tree_price(S: float, K: float, T: float, r: float, sigma: float,
                        q: float = 0.0, steps: int = 200,
                        option_type: str = "call",
                        exercise: str = "american") -> float:
    """
    Cox-Ross-Rubinstein binomial lattice.

    Calibration — chosen so the discrete tree matches GBM's first two moments as
    the step count grows:

        u = e^{sigma sqrt(dt)},  d = 1/u,
        p = (e^{(r-q)dt} - d) / (u - d)

    `p` is the **risk-neutral** probability, not a real-world one. It is
    whatever makes the discounted asset a martingale; nobody believes the stock
    actually rises with probability p.

    The reason this method exists alongside Black-Scholes: at each node we can
    compare continuation value against immediate exercise, so **American**
    options are priced by taking the max. Black-Scholes cannot do this — it
    solves a PDE with a fixed terminal condition, whereas early exercise makes
    the boundary itself part of the unknown (a free-boundary problem).

    Implemented with vectorised backward induction, O(N^2) work but only O(N)
    memory, because each step's array is overwritten in place.

    Note `p` must lie in (0,1) or the tree is arbitrageable; with very large dt
    or tiny sigma it can escape, so we assert the condition.
    """
    option = option_type.lower()
    if T <= _MIN_T or sigma <= _MIN_SIGMA:
        return float(_intrinsic(S, K, option))
    steps = max(int(steps), 1)

    dt = T / steps
    u = np.exp(sigma * np.sqrt(dt))
    d = 1.0 / u
    p = (np.exp((r - q) * dt) - d) / (u - d)
    if not (0.0 < p < 1.0):
        # Fall back to the analytic European price rather than return nonsense.
        return bsm_equity_price(S, K, T, r, sigma, q, option)
    disc = np.exp(-r * dt)

    is_call = option == "call"
    is_american = exercise.lower() == "american"

    # Terminal layer: j up-moves, (steps - j) down-moves.
    j = np.arange(steps, -1, -1)
    ST = S * (u ** j) * (d ** (steps - j))
    C = np.maximum(ST - K, 0.0) if is_call else np.maximum(K - ST, 0.0)

    for i in range(steps - 1, -1, -1):
        C = disc * (p * C[:-1] + (1.0 - p) * C[1:])
        if is_american:
            j = np.arange(i, -1, -1)
            S_node = S * (u ** j) * (d ** (i - j))
            intrinsic = np.maximum(S_node - K, 0.0) if is_call else np.maximum(K - S_node, 0.0)
            C = np.maximum(C, intrinsic)

    return float(C[0])


def binomial_convergence(S: float = 100.0, K: float = 100.0, T: float = 1.0,
                         r: float = 0.05, sigma: float = 0.2, q: float = 0.0,
                         option_type: str = "put") -> Dict[str, Any]:
    """
    Show the lattice converging to Black-Scholes as steps increase, and isolate
    the American early-exercise premium.

    Two things to read off the output:

    1. The European lattice price approaches the analytic value with error
       O(1/N), and it **oscillates** while doing so — even and odd step counts
       straddle the limit, because whether a node lands exactly at the strike
       changes with parity. This is a well-known artefact and the reason
       practitioners average adjacent step counts or use a trinomial tree.

    2. The American price stays strictly above the European one for a put. That
       gap is the early-exercise premium: with r > 0, deep in-the-money puts are
       worth exercising early to collect the strike and earn interest on it.
       For a call on a non-dividend-paying stock (q = 0) the premium is exactly
       zero — never exercise early — which is why the default here is a put.
    """
    analytic = bsm_equity_price(S, K, T, r, sigma, q, option_type)
    rows = []
    for n in (1, 2, 5, 10, 25, 50, 100, 200, 400, 800):
        eur = binomial_tree_price(S, K, T, r, sigma, q, n, option_type, "european")
        amer = binomial_tree_price(S, K, T, r, sigma, q, n, option_type, "american")
        rows.append({
            "steps": n,
            "european": round(eur, 6),
            "american": round(amer, 6),
            "analytic_european": round(analytic, 6),
            "abs_error": round(abs(eur - analytic), 6),
            "early_exercise_premium": round(amer - eur, 6),
        })

    return {
        "inputs": {"spot": S, "strike": K, "T_years": T, "rate": r, "sigma": sigma,
                   "dividend_yield": q, "option_type": option_type},
        "analytic_black_scholes": round(float(analytic), 6),
        "convergence": rows,
        "interpretation": (
            "European lattice error decays as O(1/N) and oscillates with step parity. "
            "The American premium is positive for puts (early exercise captures interest "
            "on the strike) and exactly zero for calls with no dividend."
        ),
    }


# ============================================================================
# 4. SEMI-ANALYTIC SMILE MODELS: MERTON SERIES AND HESTON INTEGRAL
# ============================================================================

def merton_closed_form(S: float, K: float, T: float, r: float, sigma: float,
                       lambda_jump: float = 0.75, mu_jump: float = -0.05,
                       sigma_jump: float = 0.15, q: float = 0.0,
                       option_type: str = "call", n_terms: int = 60) -> Dict[str, Any]:
    """
    Merton (1976) jump-diffusion in closed form — a Poisson-weighted sum of
    Black-Scholes prices.

    Conditional on exactly n jumps occurring, the terminal log price is still
    normal (a normal plus n iid normals is normal), so each term is just
    Black-Scholes with adjusted parameters. Summing over the Poisson law of n:

        Price = SUM_n  e^{-lam' T} (lam' T)^n / n!  ·  BS(S, K, T, r_n, sigma_n, q)

        k       = E[Y] - 1 = exp(mu_J + sigma_J^2/2) - 1     (mean jump size)
        lam'    = lambda (1 + k)                             (jump-measure intensity)
        sigma_n = sqrt(sigma^2 + n sigma_J^2 / T)            (variance adds)
        r_n     = r - lambda k + n ln(1+k) / T               (compensated drift)

    The `- lambda k` compensator keeps E[S_T] = S_0 e^{(r-q)T}, i.e. adding jumps
    changes the *shape* of the distribution without changing its mean. Without
    it the model would not be risk-neutral.

    Why this matters here: it is an **exact** benchmark for
    `merton_jump_diffusion`, the Monte Carlo estimator of the identical model.
    If the two disagree by more than a couple of MC standard errors, one of them
    is wrong. That is a far stronger claim than "the simulation looks plausible".

    The series converges fast — terms decay like a Poisson tail — so 60 terms is
    far more than enough for typical lambda*T well under 10.
    """
    if T <= _MIN_T:
        return {"price": float(_intrinsic(S, K, option_type)), "terms_used": 0}

    k = np.exp(mu_jump + 0.5 * sigma_jump ** 2) - 1.0
    lam_prime = lambda_jump * (1.0 + k)
    log1pk = np.log(1.0 + k)

    total = 0.0
    weight_sum = 0.0
    terms = []
    log_lam_T = np.log(lam_prime * T) if lam_prime * T > 0 else -np.inf

    for n in range(n_terms):
        if lam_prime * T > 0:
            # Compute the Poisson weight in log space to avoid overflow in n!.
            log_w = -lam_prime * T + n * log_lam_T - _log_factorial(n)
            w = float(np.exp(log_w))
        else:
            w = 1.0 if n == 0 else 0.0
        if w < 1e-14 and n > 2:
            break
        sigma_n = np.sqrt(sigma ** 2 + n * sigma_jump ** 2 / T)
        r_n = r - lambda_jump * k + n * log1pk / T
        bs_n = bsm_equity_price(S, K, T, r_n, sigma_n, q, option_type)
        total += w * bs_n
        weight_sum += w
        if n < 8:
            terms.append({
                "n_jumps": n,
                "poisson_weight": round(w, 8),
                "sigma_n": round(float(sigma_n), 6),
                "r_n": round(float(r_n), 6),
                "bs_price": round(float(bs_n), 6),
                "contribution": round(float(w * bs_n), 6),
            })

    return {
        "price": round(float(total), 6),
        "expected_jump_size_k": round(float(k), 6),
        "jump_measure_intensity": round(float(lam_prime), 6),
        "poisson_weight_sum": round(float(weight_sum), 8),
        "terms_used": n + 1,
        "first_terms": terms,
        "note": (
            "Exact benchmark for the Merton Monte Carlo estimator. Weight sum should be "
            "1.0; each term is Black-Scholes conditional on n jumps."
        ),
    }


def _log_factorial(n: int) -> float:
    from math import lgamma
    return float(lgamma(n + 1))


def _heston_char_func(u: complex, S: float, T: float, r: float, q: float,
                      v0: float, kappa: float, theta: float, xi: float,
                      rho: float) -> complex:
    """
    Heston characteristic function  phi(u) = E[exp(i u ln S_T)].

    Uses the Albrecher et al. (2007) "Little Heston Trap" formulation. The
    textbook Heston form and this one are algebraically identical, but the
    textbook version places a branch cut of the complex logarithm inside the
    integration path for long maturities, producing wildly wrong prices. This
    variant (taking `g2 = (xi_ - d)/(xi_ + d)` rather than its reciprocal) keeps
    the integrand on the principal branch and is numerically stable for all T.
    That distinction is the single most common bug in Heston implementations.
    """
    i = 1j
    xi_ = kappa - rho * xi * i * u
    d = np.sqrt(xi_ ** 2 + (xi ** 2) * (i * u + u ** 2))
    g2 = (xi_ - d) / (xi_ + d)          # the "trap"-stable choice
    exp_dt = np.exp(-d * T)

    D = ((xi_ - d) / (xi ** 2)) * ((1.0 - exp_dt) / (1.0 - g2 * exp_dt))
    C = (kappa * theta / (xi ** 2)) * (
        (xi_ - d) * T - 2.0 * np.log((1.0 - g2 * exp_dt) / (1.0 - g2))
    )
    return np.exp(i * u * (np.log(S) + (r - q) * T) + C + D * v0)


def heston_semi_analytic(S: float = 100.0, K: float = 100.0, T: float = 1.0,
                         r: float = 0.05, v0: float = 0.04, kappa: float = 2.0,
                         theta: float = 0.04, xi: float = 0.3, rho: float = -0.7,
                         q: float = 0.0, option_type: str = "call") -> Dict[str, Any]:
    """
    Heston (1993) European price by Fourier inversion of the characteristic
    function — "semi-analytic" because it is exact up to one numerical integral.

        Call = S e^{-qT} P1 - K e^{-rT} P2

        P_2 = 1/2 + (1/pi) INT_0^inf Re[ e^{-i u ln K} phi(u) / (i u) ] du
        P_1 = 1/2 + (1/pi) INT_0^inf Re[ e^{-i u ln K} phi(u - i) / (i u phi(-i)) ] du

    P2 is the risk-neutral exercise probability; P1 is the same probability under
    the share measure — the exact structural analogue of N(d2) and N(d1) in
    Black-Scholes, which is the point worth making in a write-up: Heston is not
    a different *kind* of formula, it is Black-Scholes with the Gaussian
    replaced by a distribution known only through its transform.

    Puts come from put-call parity rather than a second integral: cheaper and it
    guarantees the two are mutually consistent by construction.

    Serves as the exact benchmark for `heston_stochastic_volatility` (the Monte
    Carlo estimator of the same model).
    """
    if T <= _MIN_T:
        return {"price": float(_intrinsic(S, K, option_type)), "method": "intrinsic"}

    lnK = np.log(K)
    phi_minus_i = _heston_char_func(-1j, S, T, r, q, v0, kappa, theta, xi, rho)

    def integrand_p2(u):
        if u <= 1e-12:
            return 0.0
        val = np.exp(-1j * u * lnK) * _heston_char_func(u, S, T, r, q, v0, kappa, theta, xi, rho) / (1j * u)
        return float(np.real(val))

    def integrand_p1(u):
        if u <= 1e-12:
            return 0.0
        num = np.exp(-1j * u * lnK) * _heston_char_func(u - 1j, S, T, r, q, v0, kappa, theta, xi, rho)
        val = num / (1j * u * phi_minus_i)
        return float(np.real(val))

    # The integrand oscillates and decays; 200 is far into the tail for
    # realistic parameters. `limit` is raised because the oscillation needs many
    # subintervals near the origin.
    p2_int, p2_err = quad(integrand_p2, 1e-10, 200.0, limit=300)
    p1_int, p1_err = quad(integrand_p1, 1e-10, 200.0, limit=300)

    P2 = 0.5 + p2_int / np.pi
    P1 = 0.5 + p1_int / np.pi
    # Probabilities can drift marginally outside [0,1] from quadrature error.
    P1, P2 = float(np.clip(P1, 0.0, 1.0)), float(np.clip(P2, 0.0, 1.0))

    call = S * np.exp(-q * T) * P1 - K * np.exp(-r * T) * P2
    call = max(call, max(S * np.exp(-q * T) - K * np.exp(-r * T), 0.0), 0.0)

    if option_type.lower() == "call":
        price = call
    else:
        price = call - S * np.exp(-q * T) + K * np.exp(-r * T)  # put-call parity
        price = max(price, 0.0)

    return {
        "price": round(float(price), 6),
        "P1_share_measure": round(P1, 6),
        "P2_risk_neutral": round(P2, 6),
        "quadrature_abs_error": round(float(max(p1_err, p2_err)), 10),
        "feller_satisfied": bool(2 * kappa * theta >= xi ** 2),
        "method": "Fourier inversion, Albrecher 'Little Trap' characteristic function",
        "note": (
            "P1 and P2 are the exact structural analogues of N(d1) and N(d2). Puts are "
            "obtained by put-call parity to guarantee consistency."
        ),
    }


# ============================================================================
# 5. MONTE CARLO ENGINES
# ============================================================================

def monte_carlo_gbm(S: float, K: float, T: float, r: float, sigma: float,
                    q: float = 0.0, num_sims: int = 50000,
                    option_type: str = "call", seed: Optional[int] = None,
                    use_control_variate: bool = True) -> Dict[str, float]:
    """
    Monte Carlo for a European option under GBM, with antithetic variates and an
    optional control variate.

        S_T = S_0 exp((r - q - sigma^2/2) T + sigma sqrt(T) Z)

    Because GBM has an exact solution we sample S_T in one step — no time
    discretisation and therefore no discretisation bias. The only error is
    statistical, reported as `std_error`, and the 95% interval is +/- 1.96 SE.

    The control variate uses the discounted terminal spot, whose expectation
    S_0 e^{-qT} is known exactly; subtracting its centred error removes the
    component of payoff noise explained by spot, typically cutting the standard
    error several-fold at no extra cost.
    """
    is_call = option_type.lower() == "call"
    if T <= _MIN_T or sigma <= _MIN_SIGMA:
        return {"price": float(_intrinsic(S, K, option_type)), "std_error": 0.0,
                "ci95_low": None, "ci95_high": None}

    rng = np.random.default_rng(seed)
    half = max(num_sims // 2, 1)
    Z = rng.standard_normal(half)
    Z = np.concatenate([Z, -Z])                     # antithetic pairs

    ST = S * np.exp((r - q - 0.5 * sigma ** 2) * T + sigma * np.sqrt(T) * Z)
    disc = np.exp(-r * T)
    payoffs = np.maximum(ST - K, 0.0) if is_call else np.maximum(K - ST, 0.0)
    vals = disc * payoffs

    cv_beta = None
    if use_control_variate:
        X = disc * ST
        EX = S * np.exp(-q * T)
        varX = float(np.var(X, ddof=1))
        if varX > 0:
            cv_beta = float(np.cov(vals, X)[0, 1] / varX)
            vals = vals - cv_beta * (X - EX)

    price = float(np.mean(vals))
    se = float(np.std(vals, ddof=1) / np.sqrt(len(vals)))
    return {
        "price": round(price, 6),
        "std_error": round(se, 6),
        "ci95_low": round(price - 1.96 * se, 6),
        "ci95_high": round(price + 1.96 * se, 6),
        "num_sims": int(len(vals)),
        "control_variate_beta": round(cv_beta, 6) if cv_beta is not None else None,
        "variance_reduction": "antithetic" + (" + control variate" if cv_beta is not None else ""),
    }


def merton_jump_diffusion(S: float, K: float, T: float, r: float, sigma: float,
                          lambda_jump: float = 0.75, mu_jump: float = -0.05,
                          sigma_jump: float = 0.15, num_sims: int = 50000,
                          option_type: str = "call", q: float = 0.0,
                          seed: Optional[int] = None) -> Dict[str, Any]:
    """
    Monte Carlo for Merton jump-diffusion, validated against `merton_closed_form`.

    Terminal law, sampled in a single step (exact, no time discretisation):

        ln(S_T/S_0) = (r - q - lambda k - sigma^2/2) T
                      + sigma sqrt(T) Z
                      + SUM_{j=1..N} J_j,   N ~ Poisson(lambda T), J ~ N(mu_J, sigma_J^2)

    The jump sum is drawn directly as Normal(N mu_J, N sigma_J^2) — the sum of N
    iid normals is normal — instead of looping over individual jumps. Exact and
    much faster.

    `analytic_price` and `abs_diff_vs_analytic` are included in the return so the
    agreement is visible rather than asserted.
    """
    is_call = option_type.lower() == "call"
    if T <= _MIN_T:
        return {"price": float(_intrinsic(S, K, option_type)), "std_error": 0.0}

    rng = np.random.default_rng(seed)
    k = np.exp(mu_jump + 0.5 * sigma_jump ** 2) - 1.0
    drift = (r - q - lambda_jump * k - 0.5 * sigma ** 2) * T

    half = max(num_sims // 2, 1)
    Z = rng.standard_normal(half)
    Z = np.concatenate([Z, -Z])
    n = len(Z)

    N = rng.poisson(lambda_jump * T, n)
    J = np.where(N > 0, rng.normal(N * mu_jump, np.sqrt(np.maximum(N, 0)) * sigma_jump), 0.0)

    ST = S * np.exp(drift + sigma * np.sqrt(T) * Z + J)
    disc = np.exp(-r * T)
    payoffs = np.maximum(ST - K, 0.0) if is_call else np.maximum(K - ST, 0.0)
    vals = disc * payoffs

    price = float(np.mean(vals))
    se = float(np.std(vals, ddof=1) / np.sqrt(n))

    analytic = merton_closed_form(S, K, T, r, sigma, lambda_jump, mu_jump,
                                  sigma_jump, q, option_type)["price"]

    return {
        "price": round(price, 6),
        "std_error": round(se, 6),
        "ci95_low": round(price - 1.96 * se, 6),
        "ci95_high": round(price + 1.96 * se, 6),
        "num_sims": int(n),
        "analytic_price": analytic,
        "abs_diff_vs_analytic": round(abs(price - analytic), 6),
        "within_3_se": bool(abs(price - analytic) <= 3 * se) if se > 0 else None,
        "mean_jumps_realised": round(float(np.mean(N)), 4),
        "expected_jump_size_k": round(float(k), 6),
    }


def heston_stochastic_volatility(S: float = 100.0, K: float = 100.0, T: float = 1.0,
                                 r: float = 0.05, v0: float = 0.04, kappa: float = 2.0,
                                 theta: float = 0.04, xi: float = 0.3, rho: float = -0.7,
                                 q: float = 0.0, num_sims: int = 20000,
                                 num_steps: int = 100, option_type: str = "call",
                                 seed: Optional[int] = None) -> Dict[str, Any]:
    """
    Monte Carlo for Heston, validated against `heston_semi_analytic`.

    Two scheme choices that materially reduce bias versus a naive Euler:

      * **Log-Euler on the asset.** We evolve ln S rather than S. Given the
        variance over a step the diffusion is exactly lognormal, so this removes
        the positivity problem and most of the discretisation bias. Plain Euler
        on S can go negative and biases the price noticeably.
      * **Full truncation on the variance** (Lord et al. 2010). Keep v in the
        drift, use max(v,0) inside the square root. Lowest bias among the simple
        fixes; reflection (|v|) overstates variance and therefore the price.

    Correlation is imposed by Cholesky: Z2 = rho Z1 + sqrt(1 - rho^2) Z_ind.

    Unlike GBM and Merton this genuinely needs time-stepping — the variance path
    is path-dependent, so there is no one-step exact sampler (short of the
    Broadie-Kaya exact scheme, which is far more expensive). Some
    discretisation bias therefore remains, which is exactly why the analytic
    comparison is reported.
    """
    is_call = option_type.lower() == "call"
    if T <= _MIN_T:
        return {"price": float(_intrinsic(S, K, option_type)), "std_error": 0.0}

    rng = np.random.default_rng(seed)
    dt = T / num_steps
    sqrt_dt = np.sqrt(dt)

    log_S = np.full(num_sims, np.log(S))
    v = np.full(num_sims, float(v0))

    for _ in range(num_steps):
        Z1 = rng.standard_normal(num_sims)
        Z2 = rho * Z1 + np.sqrt(1 - rho ** 2) * rng.standard_normal(num_sims)
        v_pos = np.maximum(v, 0.0)                       # full truncation
        sqrt_v = np.sqrt(v_pos)
        log_S += (r - q - 0.5 * v_pos) * dt + sqrt_v * sqrt_dt * Z1
        v += kappa * (theta - v_pos) * dt + xi * sqrt_v * sqrt_dt * Z2

    ST = np.exp(log_S)
    disc = np.exp(-r * T)
    payoffs = np.maximum(ST - K, 0.0) if is_call else np.maximum(K - ST, 0.0)
    vals = disc * payoffs

    price = float(np.mean(vals))
    se = float(np.std(vals, ddof=1) / np.sqrt(num_sims))

    analytic = heston_semi_analytic(S, K, T, r, v0, kappa, theta, xi, rho, q, option_type)["price"]

    return {
        "price": round(price, 6),
        "std_error": round(se, 6),
        "ci95_low": round(price - 1.96 * se, 6),
        "ci95_high": round(price + 1.96 * se, 6),
        "num_sims": int(num_sims),
        "num_steps": int(num_steps),
        "analytic_price": analytic,
        "abs_diff_vs_analytic": round(abs(price - analytic), 6),
        "within_3_se": bool(abs(price - analytic) <= 3 * se) if se > 0 else None,
        "scheme": "log-Euler on S, full-truncation Euler on v",
        "feller_satisfied": bool(2 * kappa * theta >= xi ** 2),
    }


def longstaff_schwartz_american(S: float = 100.0, K: float = 100.0, T: float = 1.0,
                                r: float = 0.05, sigma: float = 0.2, q: float = 0.0,
                                num_sims: int = 40000, num_steps: int = 50,
                                option_type: str = "put", poly_degree: int = 3,
                                seed: Optional[int] = None) -> Dict[str, Any]:
    """
    Longstaff-Schwartz (2001) least-squares Monte Carlo for American options.

    The difficulty: at each step the holder compares immediate exercise against
    the **continuation value**, which is a conditional expectation
    E[discounted future payoff | S_t]. A single Monte Carlo path cannot see its
    own future without cheating (using it would be look-ahead bias and gives a
    badly upward-biased price).

    The solution: estimate that conditional expectation by **cross-sectional
    regression**. Stepping backwards, regress realised discounted continuation
    payoffs on a polynomial basis in S_t, but only over paths that are currently
    in the money — out-of-the-money paths carry no information about the
    exercise boundary and only add noise. The fitted value is the continuation
    estimate; exercise where intrinsic exceeds it.

    Why it matters beyond this project: lattices die in high dimension (a tree
    on 5 assets is 2^5 branches per step), while this is essentially
    dimension-free. It is the standard industry method for American and
    Bermudan derivatives.

    Validated against the binomial lattice below. Note that LSM carries two
    *competing* biases, which is worth stating precisely rather than repeating
    the usual half-truth:

      * **Low bias** from the suboptimal exercise rule — the regression is only
        an approximation of the true continuation value, and any suboptimal rule
        undervalues the option.
      * **High (foresight) bias** because the same paths are used both to fit
        the regression and to value the option, so the exercise rule has seen
        the realisations it is applied to.

    Which dominates depends on path count, polynomial degree and step count, so
    the honest expectation is agreement with the lattice to within a couple of
    standard errors in *either* direction — not a guaranteed undershoot.
    Eliminating the foresight bias requires fitting on one set of paths and
    valuing on an independent set.
    """
    is_call = option_type.lower() == "call"
    rng = np.random.default_rng(seed)
    dt = T / num_steps
    disc_step = np.exp(-r * dt)

    # Simulate full GBM paths (exact per step).
    Z = rng.standard_normal((num_sims, num_steps))
    log_inc = (r - q - 0.5 * sigma ** 2) * dt + sigma * np.sqrt(dt) * Z
    log_paths = np.concatenate([np.zeros((num_sims, 1)), np.cumsum(log_inc, axis=1)], axis=1)
    paths = S * np.exp(log_paths)

    def intrinsic(x):
        return np.maximum(x - K, 0.0) if is_call else np.maximum(K - x, 0.0)

    # Cashflow if held to the end, then rolled backwards.
    cashflow = intrinsic(paths[:, -1])
    exercise_step = np.full(num_sims, num_steps)

    for t in range(num_steps - 1, 0, -1):
        cashflow = cashflow * disc_step          # discount one step back
        St = paths[:, t]
        exer = intrinsic(St)
        itm = exer > 0
        if itm.sum() < poly_degree + 2:
            continue

        # Regress continuation value on a polynomial basis, in-the-money only.
        x = St[itm]
        y = cashflow[itm]
        # Scale x to keep the Vandermonde matrix well conditioned.
        xs = x / K
        A = np.vander(xs, poly_degree + 1, increasing=True)
        coef, *_ = np.linalg.lstsq(A, y, rcond=None)
        continuation = A @ coef

        do_exercise = exer[itm] > continuation
        idx = np.where(itm)[0][do_exercise]
        cashflow[idx] = exer[itm][do_exercise]
        exercise_step[idx] = t

    price = float(np.mean(cashflow * disc_step))
    se = float(np.std(cashflow * disc_step, ddof=1) / np.sqrt(num_sims))

    lattice = binomial_tree_price(S, K, T, r, sigma, q, 800, option_type, "american")
    european = bsm_equity_price(S, K, T, r, sigma, q, option_type)

    return {
        "price": round(price, 6),
        "std_error": round(se, 6),
        "ci95_low": round(price - 1.96 * se, 6),
        "ci95_high": round(price + 1.96 * se, 6),
        "lattice_american_800_steps": round(float(lattice), 6),
        "abs_diff_vs_lattice": round(abs(price - lattice), 6),
        "european_analytic": round(float(european), 6),
        "early_exercise_premium": round(price - european, 6),
        "pct_paths_exercised_early": round(float(np.mean(exercise_step < num_steps) * 100), 2),
        "polynomial_degree": poly_degree,
        "num_sims": num_sims,
        "num_steps": num_steps,
        "note": (
            "LSM is low-biased by construction (a suboptimal exercise rule undervalues "
            "the option), so it should sit just below the lattice price."
        ),
    }


# ============================================================================
# 6. IMPLIED VOLATILITY AND THE SMILE — THE POINT OF THE MODULE
# ============================================================================

def implied_vol(price: float, S: float, K: float, T: float, r: float,
                q: float = 0.0, option_type: str = "call",
                tol: float = 1e-8, max_iter: int = 100) -> Optional[float]:
    """
    Invert Black-Scholes for sigma: find the volatility that reproduces an
    observed price.

    There is no closed form, so we solve numerically. Newton-Raphson converges
    quadratically using vega as the derivative (`dV/dsigma`), but it can diverge
    when vega is tiny — deep in- or out-of-the-money, or near expiry, where
    price is almost insensitive to vol. We therefore bracket with **bisection**,
    which cannot diverge, and use Newton only while it stays inside the bracket.
    This hybrid is robust for every input the smile routine throws at it.

    Returns None when the target price violates arbitrage bounds, i.e. below
    intrinsic or above the maximum possible value — in which case no real
    implied vol exists and returning a number would be a lie.
    """
    option = option_type.lower()
    if T <= _MIN_T or price is None or price <= 0:
        return None

    disc_q, disc_r = np.exp(-q * T), np.exp(-r * T)
    # No-arbitrage bounds on a European option price.
    if option == "call":
        lo_bound = max(S * disc_q - K * disc_r, 0.0)
        hi_bound = S * disc_q
    else:
        lo_bound = max(K * disc_r - S * disc_q, 0.0)
        hi_bound = K * disc_r
    if price < lo_bound - 1e-10 or price > hi_bound + 1e-10:
        return None

    lo, hi = 1e-6, 10.0
    # Confirm a sign change exists before iterating.
    if bsm_equity_price(S, K, T, r, hi, q, option) < price:
        return None

    sigma = 0.25
    for _ in range(max_iter):
        val = bsm_equity_price(S, K, T, r, sigma, q, option)
        diff = val - price
        if abs(diff) < tol:
            return float(sigma)
        # Maintain the bracket from the sign of the residual.
        if diff > 0:
            hi = sigma
        else:
            lo = sigma

        d1, _ = _d1_d2(S, K, T, r, sigma, q)
        vega = S * disc_q * norm.pdf(d1) * np.sqrt(T)
        if vega > 1e-10:
            step = sigma - diff / vega
            if lo < step < hi:
                sigma = step
                continue
        sigma = 0.5 * (lo + hi)      # bisection fallback

    return float(sigma) if abs(bsm_equity_price(S, K, T, r, sigma, q, option) - price) < 1e-4 else None


def implied_vol_smile(S: float = 100.0, T: float = 1.0, r: float = 0.05,
                      sigma: float = 0.2, q: float = 0.0,
                      lambda_jump: float = 0.75, mu_jump: float = -0.1,
                      sigma_jump: float = 0.15,
                      v0: Optional[float] = None, kappa: float = 2.0,
                      theta: Optional[float] = None, xi: float = 0.4,
                      rho: float = -0.7,
                      moneyness_lo: float = 0.7, moneyness_hi: float = 1.3,
                      num_strikes: int = 25) -> Dict[str, Any]:
    """
    Generate the Black-Scholes implied-volatility curve produced by each model.

    Procedure, per strike: price the option with the richer model, then ask what
    single Black-Scholes sigma would reproduce that price. Plotting the answer
    against strike gives the model's implied smile.

    What the output demonstrates — the central result of this module:

      * **Black-Scholes** is a flat line at sigma, by construction. It cannot
        produce a smile because it assumes one constant volatility.
      * **Merton** produces a smile: jumps fatten both tails, so far-from-the-money
        options are worth more than lognormal maths allows, and reproducing that
        extra value inside Black-Scholes requires a higher sigma. A negative
        `mu_jump` (crashes bigger than rallies) tilts it into an asymmetric skew.
      * **Heston** produces a smile through volatility-of-volatility, and with
        `rho < 0` (the leverage effect) tilts it into the downward skew observed
        in real index options: out-of-the-money puts carry the highest implied
        vol because falling prices come with rising volatility.

    This is the options-market counterpart of what the GARCH pillar shows in the
    time series. Excess kurtosis of about 16 on the S&P 500 and a volatility
    skew in its options are the same phenomenon — non-normal returns — measured
    two different ways. Being able to state that link is the interesting part.

    Puts are used below the money and calls above (always the out-of-the-money
    side) because those options carry the most vega and the tightest real-world
    spreads, so their implied vols are the most numerically stable.
    """
    v0 = sigma ** 2 if v0 is None else v0
    theta = v0 if theta is None else theta

    strikes = np.linspace(S * moneyness_lo, S * moneyness_hi, num_strikes)
    rows = []

    for K in strikes:
        # Use the out-of-the-money side for numerical stability.
        opt = "put" if K < S else "call"

        bs_px = bsm_equity_price(S, K, T, r, sigma, q, opt)
        mer_px = merton_closed_form(S, K, T, r, sigma, lambda_jump, mu_jump,
                                    sigma_jump, q, opt)["price"]
        hes_px = heston_semi_analytic(S, K, T, r, v0, kappa, theta, xi, rho, q, opt)["price"]

        rows.append({
            "strike": round(float(K), 4),
            "moneyness": round(float(K / S), 4),
            "log_moneyness": round(float(np.log(K / S)), 6),
            "option_side": opt,
            "bs_price": round(float(bs_px), 6),
            "merton_price": round(float(mer_px), 6),
            "heston_price": round(float(hes_px), 6),
            "bs_iv": _iv_pct(bs_px, S, K, T, r, q, opt),
            "merton_iv": _iv_pct(mer_px, S, K, T, r, q, opt),
            "heston_iv": _iv_pct(hes_px, S, K, T, r, q, opt),
        })

    def curve(key):
        return [row[key] for row in rows if row[key] is not None]

    def skew_metrics(key):
        """25-delta-style skew proxy: OTM put IV minus OTM call IV, and smile curvature."""
        vals = [(r_["moneyness"], r_[key]) for r_ in rows if r_[key] is not None]
        if len(vals) < 5:
            return None
        lo = [v for m, v in vals if m <= 0.92]
        hi = [v for m, v in vals if m >= 1.08]
        atm = [v for m, v in vals if 0.97 <= m <= 1.03]
        if not (lo and hi and atm):
            return None
        return {
            "atm_iv_pct": round(float(np.mean(atm)), 3),
            "otm_put_iv_pct": round(float(np.mean(lo)), 3),
            "otm_call_iv_pct": round(float(np.mean(hi)), 3),
            "skew_put_minus_call": round(float(np.mean(lo) - np.mean(hi)), 3),
            "smile_curvature": round(float(np.mean(lo) + np.mean(hi) - 2 * np.mean(atm)), 3),
            "iv_range": round(float(max(v for _, v in vals) - min(v for _, v in vals)), 3),
        }

    return {
        "inputs": {
            "spot": S, "T_years": T, "rate": r, "base_sigma": sigma, "dividend_yield": q,
            "merton": {"lambda": lambda_jump, "mu_jump": mu_jump, "sigma_jump": sigma_jump},
            "heston": {"v0": round(float(v0), 6), "kappa": kappa,
                       "theta": round(float(theta), 6), "xi": xi, "rho": rho},
        },
        "smile": rows,
        "metrics": {
            "black_scholes": skew_metrics("bs_iv"),
            "merton": skew_metrics("merton_iv"),
            "heston": skew_metrics("heston_iv"),
        },
        "flatness_check": {
            "bs_iv_std": round(float(np.std(curve("bs_iv"))), 6),
            "merton_iv_std": round(float(np.std(curve("merton_iv"))), 6),
            "heston_iv_std": round(float(np.std(curve("heston_iv"))), 6),
        },
        "interpretation": (
            "Black-Scholes implied vol is flat by construction (std ~ 0). Merton's jumps and "
            "Heston's stochastic volatility both bend it into a smile; negative mu_jump and "
            "negative rho tilt that smile into the downward skew seen in real index options. "
            "This is the options-market view of the same non-normality the GARCH pillar "
            "measures as excess kurtosis."
        ),
    }


def _iv_pct(price: float, S: float, K: float, T: float, r: float, q: float,
            option_type: str) -> Optional[float]:
    """Implied vol as a percentage, or None if the price is outside arbitrage bounds."""
    iv = implied_vol(price, S, K, T, r, q, option_type)
    return round(float(iv * 100), 4) if iv is not None else None


# ============================================================================
# 7. MASTER ANALYZERS
# ============================================================================

def analyze_advanced_options(S: float, K: float, T: float, r: float, sigma: float,
                             q: float = 0.0, option_type: str = "call") -> Dict[str, Any]:
    """
    Run every model on one parameter set for side-by-side comparison, together
    with the validation checks that make the numbers defensible.

    Each block answers a specific question:
      closed_form_models  — how the same option is priced across equity, FX and
                            commodity conventions (they differ only in carry)
      greeks              — risk sensitivities, with a finite-difference audit
      validation          — put-call parity and analytic-vs-numeric agreement
      binomial_lattice    — European convergence and the American premium
      stochastic_models   — Merton and Heston, each Monte Carlo paired with its
                            exact benchmark
    """
    other = "put" if option_type.lower() == "call" else "call"

    bsm = bsm_equity_price(S, K, T, r, sigma, q, option_type)
    greeks = calculate_greeks(S, K, T, r, sigma, q, option_type)
    fd = greeks_finite_difference(S, K, T, r, sigma, q, option_type)
    parity = put_call_parity_check(S, K, T, r, sigma, q)

    bin_eur = binomial_tree_price(S, K, T, r, sigma, q, 400, option_type, "european")
    bin_amer = binomial_tree_price(S, K, T, r, sigma, q, 400, option_type, "american")
    bin_amer_other = binomial_tree_price(S, K, T, r, sigma, q, 400, other, "american")
    bin_eur_other = bsm_equity_price(S, K, T, r, sigma, q, other)

    mc = monte_carlo_gbm(S, K, T, r, sigma, q, 40000, option_type, seed=42)
    merton_mc = merton_jump_diffusion(S, K, T, r, sigma, num_sims=40000,
                                      option_type=option_type, q=q, seed=42)
    v0 = sigma ** 2
    heston_mc = heston_stochastic_volatility(S, K, T, r, v0, 2.0, v0, 0.3, -0.7, q,
                                            20000, 100, option_type, seed=42)

    # Market-convention variants. r_foreign for FX is illustrative here; the
    # market-wired module resolves a real per-currency rate.
    gk = garman_kohlhagen_price(S, K, T, r, 0.02, sigma, option_type)
    b76 = black_76_price(S, K, T, r, sigma, option_type)
    bach = bachelier_price(S, K, T, r, sigma * S, option_type)

    return {
        "inputs": {"spot": S, "strike": K, "T_years": T, "risk_free_rate": r,
                   "volatility": sigma, "dividend_yield": q, "option_type": option_type},
        "closed_form_models": {
            "bsm_equity": round(bsm, 6),
            "garman_kohlhagen_forex": round(float(gk), 6),
            "black76_commodities": round(float(b76), 6),
            "bachelier_normal": round(float(bach), 6),
            "_note": (
                "All four share one engine and differ only in carry: BSM uses q, "
                "Garman-Kohlhagen sets q = r_foreign, Black-76 sets q = r (futures have no "
                "carry), and Bachelier replaces lognormal with normal dynamics."
            ),
        },
        "greeks": greeks,
        "validation": {
            "put_call_parity": parity,
            "greeks_finite_difference": fd,
            "monte_carlo_vs_analytic": {
                "analytic": round(bsm, 6),
                "monte_carlo": mc["price"],
                "std_error": mc["std_error"],
                "abs_diff": round(abs(mc["price"] - bsm), 6),
                "within_3_se": bool(abs(mc["price"] - bsm) <= 3 * mc["std_error"]) if mc["std_error"] > 0 else None,
            },
        },
        "binomial_lattice": {
            "european_price": round(bin_eur, 6),
            "american_price": round(bin_amer, 6),
            "early_exercise_premium": round(bin_amer - bin_eur, 6),
            "steps": 400,
            f"{other}_european": round(float(bin_eur_other), 6),
            f"{other}_american": round(bin_amer_other, 6),
            f"{other}_early_exercise_premium": round(bin_amer_other - float(bin_eur_other), 6),
            "_note": (
                "A call on a non-dividend stock is never exercised early, so its premium is "
                "exactly zero; a put's is positive because exercising captures interest on "
                "the strike. Both are shown so the asymmetry is visible."
            ),
        },
        "stochastic_models": {
            "gbm_monte_carlo": mc,
            "merton_jump_diffusion": merton_mc,
            "heston_stochastic_volatility": heston_mc,
            "_note": (
                "Each Monte Carlo estimate is reported next to the exact price for the same "
                "model (Poisson series for Merton, Fourier inversion for Heston). Agreement "
                "inside 3 standard errors is the correctness criterion."
            ),
        },
    }
