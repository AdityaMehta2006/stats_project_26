"""
stochastic.py
-------------
Stochastic-process simulation engines: the mathematical substrate underneath
the options module (`advanced_options.py`) and the pair-trading pillar
(`pairs.py`).

Every process here is a **stochastic differential equation** (SDE) of the
general Itô form

    dX_t = a(X_t, t) dt  +  b(X_t, t) dW_t
           ^^^^^^^^^^^^     ^^^^^^^^^^^^^^
           drift            diffusion

where `W_t` is a **Wiener process** (standard Brownian motion): W_0 = 0,
increments `W_t - W_s ~ Normal(0, t - s)` are independent, and paths are
continuous but nowhere differentiable. That last property is why we cannot use
ordinary calculus and need Itô's lemma instead.

Processes implemented
---------------------
| Process                   | SDE                                                  | Used for                        |
|---------------------------|------------------------------------------------------|---------------------------------|
| Wiener                    | dW_t = dZ                                            | the driving noise itself        |
| Arithmetic Brownian       | dX = mu dt + sigma dW                                | log-price; Bachelier options    |
| Geometric Brownian (GBM)  | dS = mu S dt + sigma S dW                            | Black-Scholes underlying        |
| Ornstein-Uhlenbeck (OU)   | dX = kappa(theta - X) dt + sigma dW                  | **the pair-trading spread**     |
| Cox-Ingersoll-Ross (CIR)  | dv = kappa(theta - v) dt + xi sqrt(v) dW             | Heston's variance; short rates  |
| Merton jump-diffusion     | dS = (mu - lambda k) S dt + sigma S dW + (Y-1) S dN  | crash risk / fat tails          |
| Heston stochastic vol     | coupled GBM + CIR with correlation rho               | volatility smile                |

Discretisation
--------------
Only GBM and OU have exact discrete transition laws (both are Gaussian), so we
simulate those exactly. The rest need a numerical scheme, and the choice matters:

  * **Euler-Maruyama** — strong order 0.5, weak order 1.0. Simple, but for
    square-root diffusions like CIR it can produce negative variance.
  * **Milstein** — adds the Itô-Taylor second-order term
    `0.5 b b' (dW^2 - dt)`, giving strong order 1.0. Materially better for
    state-dependent volatility.
  * **Full truncation** — Lord et al. (2010). Keeps `v` in the drift but uses
    `max(v, 0)` inside the square root. The lowest-bias fix for CIR/Heston,
    which is why `heston_paths` uses it.

Variance reduction
------------------
Monte Carlo error falls as `1/sqrt(N)`, so brute force is expensive. We use:
  * **Antithetic variates** — pair each Z with -Z. Free, and cuts variance
    whenever the payoff is monotone in Z.
  * **Control variates** — exploit a correlated quantity whose expectation is
    known analytically (for GBM, the discounted terminal spot: E[e^{-rT} S_T]
    = S_0 e^{-qT}). Typically 5-20x variance reduction for vanilla payoffs.

References: Glasserman (2004) *Monte Carlo Methods in Financial Engineering*;
Kloeden & Platen (1992) *Numerical Solution of SDEs*; Lord, Koekkoek & van Dijk
(2010) on the full-truncation scheme.
"""

import numpy as np
from typing import Dict, Any, Optional

# A module-level generator keeps results reproducible when a seed is supplied
# and avoids the legacy global np.random state.
def _rng(seed: Optional[int] = None) -> np.random.Generator:
    return np.random.default_rng(seed)


# ============================================================================
# 1. THE WIENER PROCESS — the noise that drives everything else
# ============================================================================

def wiener_paths(T: float = 1.0, num_steps: int = 252, num_paths: int = 5,
                 seed: Optional[int] = None) -> Dict[str, Any]:
    """
    Simulate standard Brownian motion W_t on [0, T].

    Construction: W_0 = 0 and W_{t+dt} = W_t + sqrt(dt) * Z with Z ~ N(0,1).
    The `sqrt(dt)` scaling (not `dt`) is the whole point — it is what makes the
    variance grow linearly in time, Var(W_t) = t, and what makes the paths
    nowhere differentiable.

    Also returns the realised **quadratic variation** sum((dW)^2), which
    converges to T as dt -> 0. That identity, "dW^2 = dt", is the engine of
    Itô's lemma and the reason stochastic calculus differs from ordinary
    calculus.
    """
    rng = _rng(seed)
    dt = T / num_steps
    dW = np.sqrt(dt) * rng.standard_normal((num_paths, num_steps))
    W = np.concatenate([np.zeros((num_paths, 1)), np.cumsum(dW, axis=1)], axis=1)
    times = np.linspace(0.0, T, num_steps + 1)

    quadratic_variation = float(np.mean(np.sum(dW ** 2, axis=1)))

    return {
        "times": [round(float(t), 6) for t in times],
        "paths": [[round(float(x), 6) for x in row] for row in W],
        "theory": {
            "mean_theoretical": 0.0,
            "variance_theoretical_at_T": round(float(T), 6),
            "variance_empirical_at_T": round(float(np.var(W[:, -1])), 6),
            "quadratic_variation_empirical": round(quadratic_variation, 6),
            "quadratic_variation_theoretical": round(float(T), 6),
        },
        "note": (
            "Quadratic variation converges to T, which is the identity dW^2 = dt "
            "underlying Ito's lemma."
        ),
    }


# ============================================================================
# 2. GEOMETRIC BROWNIAN MOTION — the Black-Scholes underlying
# ============================================================================

def gbm_paths(S0: float = 100.0, mu: float = 0.05, sigma: float = 0.2,
              T: float = 1.0, num_steps: int = 252, num_paths: int = 5,
              seed: Optional[int] = None) -> Dict[str, Any]:
    """
    Geometric Brownian Motion:  dS = mu S dt + sigma S dW.

    Applying Ito's lemma to f(S) = ln S gives the *exact* solution

        S_t = S_0 * exp( (mu - sigma^2/2) t + sigma W_t )

    Note the `-sigma^2/2`: it is the Itô correction. Ordinary calculus would
    predict `exp(mu*t)` growth for log-price, but because `ln` is concave and
    `dW^2 = dt` is non-negligible, the log drifts *slower* than mu. This is
    exactly why the median of S_T sits below its mean, and it is the single
    most commonly dropped term in student derivations.

    Because the solution is exact and closed form, we simulate with no
    discretisation error at all — dt only controls how finely we *observe* the
    path, not its accuracy.
    """
    rng = _rng(seed)
    dt = T / num_steps
    Z = rng.standard_normal((num_paths, num_steps))
    log_increments = (mu - 0.5 * sigma ** 2) * dt + sigma * np.sqrt(dt) * Z
    log_paths = np.concatenate([np.zeros((num_paths, 1)), np.cumsum(log_increments, axis=1)], axis=1)
    S = S0 * np.exp(log_paths)
    times = np.linspace(0.0, T, num_steps + 1)

    # Lognormal moments of S_T
    mean_theo = S0 * np.exp(mu * T)
    var_theo = S0 ** 2 * np.exp(2 * mu * T) * (np.exp(sigma ** 2 * T) - 1)

    return {
        "times": [round(float(t), 6) for t in times],
        "paths": [[round(float(x), 4) for x in row] for row in S],
        "theory": {
            "solution": "S_t = S_0 exp((mu - sigma^2/2) t + sigma W_t)",
            "ito_correction": round(float(-0.5 * sigma ** 2), 6),
            "mean_theoretical_at_T": round(float(mean_theo), 4),
            "mean_empirical_at_T": round(float(np.mean(S[:, -1])), 4),
            "median_theoretical_at_T": round(float(S0 * np.exp((mu - 0.5 * sigma ** 2) * T)), 4),
            "std_theoretical_at_T": round(float(np.sqrt(var_theo)), 4),
            "std_empirical_at_T": round(float(np.std(S[:, -1])), 4),
        },
        "note": (
            "The mean grows at exp(mu T) but the median only at "
            "exp((mu - sigma^2/2) T) — the gap is the Ito correction."
        ),
    }


def gbm_scheme_comparison(S0: float = 100.0, mu: float = 0.05, sigma: float = 0.4,
                          T: float = 1.0, num_paths: int = 20000,
                          seed: Optional[int] = None) -> Dict[str, Any]:
    """
    Convergence study: exact GBM vs Euler-Maruyama vs Milstein, across step counts.

    For GBM (b(S) = sigma*S, so b'(S) = sigma) the schemes are

        Euler:    S_{n+1} = S_n + mu S_n dt + sigma S_n dW
        Milstein: S_{n+1} = S_n + mu S_n dt + sigma S_n dW
                            + 0.5 sigma^2 S_n (dW^2 - dt)

    We report the mean absolute error in E[S_T] against the exact lognormal
    value. Milstein's extra term should shrink the error roughly one order
    faster as dt falls, demonstrating strong order 1.0 vs Euler's 0.5.
    """
    rng = _rng(seed)
    exact_mean = S0 * np.exp(mu * T)
    rows = []

    for num_steps in (4, 8, 16, 32, 64, 128, 256):
        dt = T / num_steps
        sqrt_dt = np.sqrt(dt)

        # Shared noise so the schemes are compared on identical randomness —
        # otherwise Monte Carlo noise would swamp the discretisation error.
        Z = rng.standard_normal((num_paths, num_steps))

        s_euler = np.full(num_paths, float(S0))
        s_mil = np.full(num_paths, float(S0))
        for i in range(num_steps):
            dW = sqrt_dt * Z[:, i]
            s_euler = s_euler + mu * s_euler * dt + sigma * s_euler * dW
            s_mil = (s_mil + mu * s_mil * dt + sigma * s_mil * dW
                     + 0.5 * sigma ** 2 * s_mil * (dW ** 2 - dt))
            # Euler can undershoot through zero for large dt/sigma; clamp so the
            # comparison stays meaningful rather than producing NaNs.
            s_euler = np.maximum(s_euler, 0.0)
            s_mil = np.maximum(s_mil, 0.0)

        # Exact scheme on the same noise
        log_inc = (mu - 0.5 * sigma ** 2) * dt + sigma * sqrt_dt * Z
        s_exact = S0 * np.exp(np.sum(log_inc, axis=1))

        rows.append({
            "num_steps": num_steps,
            "dt": round(float(dt), 6),
            "exact_mean": round(float(np.mean(s_exact)), 4),
            "euler_mean": round(float(np.mean(s_euler)), 4),
            "milstein_mean": round(float(np.mean(s_mil)), 4),
            "euler_error": round(float(abs(np.mean(s_euler) - exact_mean)), 5),
            "milstein_error": round(float(abs(np.mean(s_mil) - exact_mean)), 5),
        })

    return {
        "analytical_mean": round(float(exact_mean), 4),
        "convergence": rows,
        "interpretation": (
            "Milstein adds the Ito-Taylor term 0.5 sigma^2 S (dW^2 - dt), lifting strong "
            "convergence from order 0.5 (Euler) to order 1.0. The error column shrinks "
            "faster for Milstein as dt decreases."
        ),
    }


# ============================================================================
# 3. ORNSTEIN-UHLENBECK — the mathematics of the pair-trading spread
# ============================================================================

def ou_paths(X0: float = 0.0, kappa: float = 2.0, theta: float = 0.0,
             sigma: float = 0.3, T: float = 1.0, num_steps: int = 252,
             num_paths: int = 5, seed: Optional[int] = None) -> Dict[str, Any]:
    """
    Ornstein-Uhlenbeck (Vasicek) process:

        dX_t = kappa (theta - X_t) dt + sigma dW_t

    This is the continuous-time model of **mean reversion**, and it is the exact
    process the pair-trading pillar assumes for its spread. Read the drift term
    literally: whenever X is above theta the drift is negative and pulls it back
    down; below theta it pushes up. `kappa` is the speed of that pull.

    It has an exact Gaussian transition density, so we simulate exactly:

        X_{t+dt} = theta + (X_t - theta) e^{-kappa dt}
                   + sigma sqrt( (1 - e^{-2 kappa dt}) / (2 kappa) ) Z

    Key results this function reports, all of which the pairs module depends on:

      * **Half-life** = ln(2)/kappa. Solve E[X_t] - theta = (X_0 - theta)/2 for t.
        This is the headline number on the Pairs tab.
      * **Stationary distribution** X_inf ~ Normal(theta, sigma^2/(2 kappa)).
        Its existence is *why* a z-score of the spread is meaningful at all: a
        random walk has no stationary variance to standardise against.

    The link to `pairs.py`: discretising the OU SDE gives
    `X_t - X_{t-1} = kappa*theta*dt - kappa*dt*X_{t-1} + noise`, which is exactly
    the AR(1)-in-differences regression `spread_diff ~ spread_lag` that
    `get_best_pair_analysis` fits. The estimated slope is `-kappa*dt`, hence
    `half_life = -ln(2)/slope`.
    """
    rng = _rng(seed)
    dt = T / num_steps
    X = np.zeros((num_paths, num_steps + 1))
    X[:, 0] = X0

    decay = np.exp(-kappa * dt)
    # Exact conditional standard deviation of the OU increment.
    cond_std = sigma * np.sqrt((1 - np.exp(-2 * kappa * dt)) / (2 * kappa)) if kappa > 0 else sigma * np.sqrt(dt)

    Z = rng.standard_normal((num_paths, num_steps))
    for i in range(num_steps):
        X[:, i + 1] = theta + (X[:, i] - theta) * decay + cond_std * Z[:, i]

    times = np.linspace(0.0, T, num_steps + 1)
    half_life = float(np.log(2) / kappa) if kappa > 0 else float("inf")
    stat_var = float(sigma ** 2 / (2 * kappa)) if kappa > 0 else float("inf")

    return {
        "times": [round(float(t), 6) for t in times],
        "paths": [[round(float(x), 6) for x in row] for row in X],
        "theory": {
            "sde": "dX = kappa (theta - X) dt + sigma dW",
            "kappa": kappa,
            "theta": theta,
            "half_life_time_units": round(half_life, 6) if np.isfinite(half_life) else None,
            "stationary_mean": theta,
            "stationary_variance": round(stat_var, 6) if np.isfinite(stat_var) else None,
            "stationary_std": round(float(np.sqrt(stat_var)), 6) if np.isfinite(stat_var) else None,
            "empirical_terminal_mean": round(float(np.mean(X[:, -1])), 6),
            "empirical_terminal_std": round(float(np.std(X[:, -1])), 6),
        },
        "note": (
            "Half-life = ln(2)/kappa. The existence of a stationary variance "
            "sigma^2/(2 kappa) is what makes a spread z-score meaningful — a random "
            "walk has no such anchor."
        ),
    }


def fit_ou(series, dt: float = 1.0) -> Dict[str, Any]:
    """
    Estimate OU parameters (kappa, theta, sigma) from an observed series by
    least squares on the discrete AR(1) representation.

    Regress X_t on X_{t-1}:   X_t = a + b X_{t-1} + eps

    Matching to the exact OU transition gives
        b     = e^{-kappa dt}          ->  kappa = -ln(b)/dt
        a     = theta (1 - b)          ->  theta = a/(1 - b)
        sd(eps)^2 = sigma^2 (1-b^2)/(2 kappa)
                                       ->  sigma = sd(eps) sqrt(2 kappa/(1-b^2))

    This is the estimator behind the half-life reported for a traded spread.
    Mean reversion requires 0 < b < 1; b >= 1 means the series is a random walk
    (or explosive) and no finite half-life exists.
    """
    x = np.asarray(series, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 20:
        return {"error": "need at least 20 observations"}

    x_lag, x_now = x[:-1], x[1:]
    # OLS with intercept via the normal equations on a 2-column design matrix.
    A = np.column_stack([np.ones_like(x_lag), x_lag])
    coef, *_ = np.linalg.lstsq(A, x_now, rcond=None)
    a, b = float(coef[0]), float(coef[1])
    resid = x_now - (a + b * x_lag)
    resid_sd = float(np.std(resid, ddof=2))

    if b <= 0 or b >= 1:
        return {
            "ar1_intercept": round(a, 6),
            "ar1_slope": round(b, 6),
            "mean_reverting": False,
            "half_life": None,
            "note": (
                "AR(1) slope is outside (0,1): the series behaves as a random walk or is "
                "explosive, so no finite mean-reversion half-life exists."
            ),
        }

    kappa = -np.log(b) / dt
    theta = a / (1 - b)
    sigma = resid_sd * np.sqrt(2 * kappa / (1 - b ** 2))
    half_life = np.log(2) / kappa

    return {
        "ar1_intercept": round(a, 6),
        "ar1_slope": round(b, 6),
        "mean_reverting": True,
        "kappa": round(float(kappa), 6),
        "theta": round(float(theta), 6),
        "sigma": round(float(sigma), 6),
        "half_life": round(float(half_life), 4),
        "stationary_std": round(float(sigma / np.sqrt(2 * kappa)), 6),
        "residual_std": round(resid_sd, 6),
        "note": "kappa = -ln(b)/dt; theta = a/(1-b); half-life = ln(2)/kappa.",
    }


# ============================================================================
# 4. COX-INGERSOLL-ROSS — the variance process inside Heston
# ============================================================================

def cir_paths(v0: float = 0.04, kappa: float = 2.0, theta: float = 0.04,
              xi: float = 0.3, T: float = 1.0, num_steps: int = 252,
              num_paths: int = 5, scheme: str = "full_truncation",
              seed: Optional[int] = None) -> Dict[str, Any]:
    """
    Cox-Ingersoll-Ross square-root process:

        dv_t = kappa (theta - v_t) dt + xi sqrt(v_t) dW_t

    Mean-reverting like OU, but the `sqrt(v)` diffusion means volatility of the
    variance shrinks as v approaches zero. That structure keeps v non-negative
    in continuous time — provided the **Feller condition** `2 kappa theta >= xi^2`
    holds, the process never touches zero.

    Discretisation is the whole difficulty: plain Euler can step v below zero,
    and then `sqrt(v)` is undefined. Schemes offered:

      * `euler`           — raw; may produce NaN. Included to show the failure.
      * `reflection`      — use |v|. Simple but biases variance upward.
      * `full_truncation` — keep v in the drift, use max(v,0) under the sqrt.
                            Lowest bias (Lord et al. 2010). **Default.**
    """
    rng = _rng(seed)
    dt = T / num_steps
    sqrt_dt = np.sqrt(dt)
    v = np.zeros((num_paths, num_steps + 1))
    v[:, 0] = v0

    feller_ok = bool(2 * kappa * theta >= xi ** 2)
    Z = rng.standard_normal((num_paths, num_steps))
    negative_hits = 0

    for i in range(num_steps):
        v_prev = v[:, i]
        if scheme == "reflection":
            v_used = np.abs(v_prev)
            drift_base = v_used
        elif scheme == "euler":
            v_used = v_prev
            drift_base = v_prev
        else:  # full_truncation
            v_used = np.maximum(v_prev, 0.0)
            drift_base = v_prev

        sqrt_v = np.sqrt(np.maximum(v_used, 0.0))
        v_next = drift_base + kappa * (theta - drift_base) * dt + xi * sqrt_v * sqrt_dt * Z[:, i]
        negative_hits += int(np.sum(v_next < 0))
        if scheme == "reflection":
            v_next = np.abs(v_next)
        elif scheme == "full_truncation":
            # Store the raw value; the truncation is applied when it is *used*.
            pass
        v[:, i + 1] = v_next

    times = np.linspace(0.0, T, num_steps + 1)
    v_display = np.maximum(v, 0.0) if scheme == "full_truncation" else v

    # Stationary moments of CIR (Gamma distributed)
    stat_mean = theta
    stat_var = xi ** 2 * theta / (2 * kappa) if kappa > 0 else float("inf")

    return {
        "times": [round(float(t), 6) for t in times],
        "paths": [[round(float(x), 8) for x in row] for row in v_display],
        "vol_paths": [[round(float(np.sqrt(max(x, 0.0))), 6) for x in row] for row in v_display],
        "theory": {
            "sde": "dv = kappa (theta - v) dt + xi sqrt(v) dW",
            "scheme": scheme,
            "feller_condition": "2 kappa theta >= xi^2",
            "feller_lhs": round(float(2 * kappa * theta), 6),
            "feller_rhs": round(float(xi ** 2), 6),
            "feller_satisfied": feller_ok,
            "stationary_mean": round(float(stat_mean), 6),
            "stationary_variance": round(float(stat_var), 8) if np.isfinite(stat_var) else None,
            "empirical_terminal_mean": round(float(np.mean(v_display[:, -1])), 6),
            "negative_excursions": negative_hits,
        },
        "note": (
            "When the Feller condition fails the variance can reach zero, so the "
            "discretisation scheme materially changes the answer."
            if not feller_ok else
            "Feller condition holds: the variance stays strictly positive in continuous time."
        ),
    }


# ============================================================================
# 5. JUMP-DIFFUSION AND STOCHASTIC-VOLATILITY PATHS
# ============================================================================

def merton_paths(S0: float = 100.0, mu: float = 0.05, sigma: float = 0.2,
                 lambda_jump: float = 0.75, mu_jump: float = -0.05,
                 sigma_jump: float = 0.15, T: float = 1.0, num_steps: int = 252,
                 num_paths: int = 5, seed: Optional[int] = None) -> Dict[str, Any]:
    """
    Merton jump-diffusion:

        dS/S = (mu - lambda k) dt + sigma dW + (Y - 1) dN

    where N_t is a Poisson counter with intensity `lambda_jump` and each jump
    multiplies the price by Y = e^J, J ~ Normal(mu_jump, sigma_jump^2).

    The `- lambda k` term with `k = E[Y] - 1 = exp(mu_jump + sigma_jump^2/2) - 1`
    is the **compensator**. Without it, adding jumps would change the expected
    return; subtracting it keeps E[S_T] = S_0 e^{mu T} so the diffusion and jump
    parts are cleanly separated and the measure stays risk-neutral when mu = r.

    Economically: this is how you model crashes. A negative `mu_jump` produces
    exactly the negative skew and excess kurtosis the GARCH pillar measures
    empirically (excess kurtosis ~16 on the S&P 500), which a pure-diffusion
    GBM cannot generate at any sigma.
    """
    rng = _rng(seed)
    dt = T / num_steps
    sqrt_dt = np.sqrt(dt)

    k = np.exp(mu_jump + 0.5 * sigma_jump ** 2) - 1.0
    drift = (mu - lambda_jump * k - 0.5 * sigma ** 2) * dt

    log_S = np.zeros((num_paths, num_steps + 1))
    jump_times = []
    for i in range(num_steps):
        Z = rng.standard_normal(num_paths)
        N = rng.poisson(lambda_jump * dt, num_paths)
        # Sum of N iid normals is Normal(N*mu_j, N*sigma_j^2) — sample directly
        # rather than looping, which is both faster and exact.
        J = np.where(N > 0,
                     rng.normal(N * mu_jump, np.sqrt(np.maximum(N, 0)) * sigma_jump),
                     0.0)
        log_S[:, i + 1] = log_S[:, i] + drift + sigma * sqrt_dt * Z + J
        if np.any(N > 0):
            jump_times.append(round(float((i + 1) * dt), 6))

    S = S0 * np.exp(log_S)
    times = np.linspace(0.0, T, num_steps + 1)

    terminal = S[:, -1]
    log_ret = np.log(terminal / S0)

    return {
        "times": [round(float(t), 6) for t in times],
        "paths": [[round(float(x), 4) for x in row] for row in S],
        "theory": {
            "sde": "dS/S = (mu - lambda k) dt + sigma dW + (Y-1) dN",
            "expected_jump_size_k": round(float(k), 6),
            "compensator_drift_adjustment": round(float(-lambda_jump * k), 6),
            "expected_num_jumps": round(float(lambda_jump * T), 4),
            "mean_theoretical_at_T": round(float(S0 * np.exp(mu * T)), 4),
            "mean_empirical_at_T": round(float(np.mean(terminal)), 4),
            "log_return_skew": round(float(_skew(log_ret)), 4),
            "log_return_excess_kurtosis": round(float(_excess_kurtosis(log_ret)), 4),
        },
        "jump_step_times": jump_times[:50],
        "note": (
            "Negative mu_jump generates negative skew and excess kurtosis — the fat "
            "tails GARCH measures empirically, which pure GBM cannot produce."
        ),
    }


def heston_paths(S0: float = 100.0, r: float = 0.05, v0: float = 0.04,
                 kappa: float = 2.0, theta: float = 0.04, xi: float = 0.3,
                 rho: float = -0.7, T: float = 1.0, num_steps: int = 252,
                 num_paths: int = 5, seed: Optional[int] = None) -> Dict[str, Any]:
    """
    Heston stochastic-volatility model — two coupled SDEs:

        dS_t = r S_t dt + sqrt(v_t) S_t dW1
        dv_t = kappa (theta - v_t) dt + xi sqrt(v_t) dW2
        corr(dW1, dW2) = rho

    Volatility is itself random (a CIR process), which is what generates a
    **volatility smile** — Black-Scholes, with its single constant sigma, cannot.

    `rho < 0` (the empirical norm for equities, around -0.7) encodes the
    **leverage effect**: prices down, volatility up. It is what tilts the smile
    into the observed downward *skew*, making out-of-the-money puts expensive.

    Implementation notes — both matter for accuracy:
      * We evolve **log S**, not S. Log-Euler is exact for the diffusion part
        given v, so it removes the positivity problem and most of the bias that
        an Euler scheme on S itself would introduce.
      * Variance uses **full truncation** (max(v,0) under the square root),
        the lowest-bias standard fix.

    Correlated normals are built by Cholesky: Z2 = rho Z1 + sqrt(1-rho^2) Z_ind.
    """
    rng = _rng(seed)
    dt = T / num_steps
    sqrt_dt = np.sqrt(dt)

    log_S = np.zeros((num_paths, num_steps + 1))
    log_S[:, 0] = np.log(S0)
    v = np.zeros((num_paths, num_steps + 1))
    v[:, 0] = v0

    for i in range(num_steps):
        Z1 = rng.standard_normal(num_paths)
        Z_ind = rng.standard_normal(num_paths)
        Z2 = rho * Z1 + np.sqrt(1 - rho ** 2) * Z_ind

        v_pos = np.maximum(v[:, i], 0.0)          # full truncation
        sqrt_v = np.sqrt(v_pos)

        # Log-Euler for the asset: exact given the variance over the step.
        log_S[:, i + 1] = log_S[:, i] + (r - 0.5 * v_pos) * dt + sqrt_v * sqrt_dt * Z1
        v[:, i + 1] = v[:, i] + kappa * (theta - v_pos) * dt + xi * sqrt_v * sqrt_dt * Z2

    S = np.exp(log_S)
    v_display = np.maximum(v, 0.0)
    times = np.linspace(0.0, T, num_steps + 1)
    log_ret = np.log(S[:, -1] / S0)

    return {
        "times": [round(float(t), 6) for t in times],
        "paths": [[round(float(x), 4) for x in row] for row in S],
        "variance_paths": [[round(float(x), 8) for x in row] for row in v_display],
        "vol_paths": [[round(float(np.sqrt(x) * 100), 4) for x in row] for row in v_display],
        "theory": {
            "asset_sde": "dS = r S dt + sqrt(v) S dW1",
            "variance_sde": "dv = kappa (theta - v) dt + xi sqrt(v) dW2",
            "correlation_rho": rho,
            "leverage_effect": "negative rho: prices fall as volatility rises (equity norm)",
            "feller_satisfied": bool(2 * kappa * theta >= xi ** 2),
            "long_run_vol_pct": round(float(np.sqrt(theta) * 100), 2),
            "initial_vol_pct": round(float(np.sqrt(v0) * 100), 2),
            "vol_half_life": round(float(np.log(2) / kappa), 4) if kappa > 0 else None,
            "log_return_skew": round(float(_skew(log_ret)), 4),
            "log_return_excess_kurtosis": round(float(_excess_kurtosis(log_ret)), 4),
            "scheme": "log-Euler on S, full-truncation Euler on v",
        },
        "note": (
            "Random volatility produces a smile; negative rho tilts it into the "
            "downward skew observed in equity index options."
        ),
    }


def _skew(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    sd = x.std()
    return float(np.mean((x - x.mean()) ** 3) / sd ** 3) if sd > 0 else 0.0


def _excess_kurtosis(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    sd = x.std()
    return float(np.mean((x - x.mean()) ** 4) / sd ** 4 - 3.0) if sd > 0 else 0.0


# ============================================================================
# 6. VARIANCE REDUCTION — demonstrating why estimator design beats brute force
# ============================================================================

def variance_reduction_study(S0: float = 100.0, K: float = 100.0, T: float = 0.25,
                             r: float = 0.05, sigma: float = 0.2, q: float = 0.0,
                             num_sims: int = 40000, option_type: str = "call",
                             seed: Optional[int] = None) -> Dict[str, Any]:
    """
    Price the same European option four ways and compare standard errors:

      1. **Plain Monte Carlo** — the baseline, error ~ sd/sqrt(N).
      2. **Antithetic variates** — pair Z with -Z. Induces negative correlation
         between paired payoffs, so the pair average has lower variance.
      3. **Control variate** — use the discounted terminal spot, whose true mean
         E[e^{-rT} S_T] = S_0 e^{-qT} is known. Form
         `payoff - c (X - E[X])` with the variance-minimising
         `c = Cov(payoff, X)/Var(X)`.
      4. **Antithetic + control** — both together.

    The point for a write-up: halving the standard error by brute force needs 4x
    the paths, but a control variate can do it for free. All four estimates
    should agree with the closed-form Black-Scholes price within a couple of
    standard errors — which is also a correctness check on the analytic code.
    """
    from analysis.advanced_options import bsm_equity_price

    rng = _rng(seed)
    is_call = option_type.lower() == "call"
    disc = np.exp(-r * T)
    drift = (r - q - 0.5 * sigma ** 2) * T
    vol_sqrt_t = sigma * np.sqrt(T)

    def payoff(ST):
        return np.maximum(ST - K, 0.0) if is_call else np.maximum(K - ST, 0.0)

    def stats(vals):
        return float(np.mean(vals)), float(np.std(vals, ddof=1) / np.sqrt(len(vals)))

    analytic = bsm_equity_price(S0, K, T, r, sigma, q, option_type)

    # --- 1. Plain
    Z = rng.standard_normal(num_sims)
    ST = S0 * np.exp(drift + vol_sqrt_t * Z)
    plain_vals = disc * payoff(ST)
    plain_price, plain_se = stats(plain_vals)

    # --- 2. Antithetic (same total path count for a fair comparison)
    half = num_sims // 2
    Za = rng.standard_normal(half)
    ST_p = S0 * np.exp(drift + vol_sqrt_t * Za)
    ST_m = S0 * np.exp(drift - vol_sqrt_t * Za)
    anti_vals = 0.5 * disc * (payoff(ST_p) + payoff(ST_m))
    anti_price, anti_se = stats(anti_vals)

    # --- 3. Control variate on the plain sample
    X = disc * ST                     # discounted terminal spot
    EX = S0 * np.exp(-q * T)          # its known expectation
    cov = float(np.cov(plain_vals, X)[0, 1])
    varX = float(np.var(X, ddof=1))
    c = cov / varX if varX > 0 else 0.0
    cv_vals = plain_vals - c * (X - EX)
    cv_price, cv_se = stats(cv_vals)

    # --- 4. Antithetic + control
    Xa = 0.5 * disc * (ST_p + ST_m)
    cov_a = float(np.cov(anti_vals, Xa)[0, 1])
    varXa = float(np.var(Xa, ddof=1))
    ca = cov_a / varXa if varXa > 0 else 0.0
    both_vals = anti_vals - ca * (Xa - EX)
    both_price, both_se = stats(both_vals)

    def row(name, price, se, paths):
        return {
            "method": name,
            "price": round(price, 5),
            "std_error": round(se, 6),
            "abs_error_vs_analytic": round(abs(price - analytic), 5),
            "variance_reduction_factor": round((plain_se / se) ** 2, 2) if se > 0 else None,
            "paths_used": paths,
            "within_2_se": bool(abs(price - analytic) <= 2 * se) if se > 0 else None,
        }

    return {
        "inputs": {"spot": S0, "strike": K, "T_years": T, "rate": r, "sigma": sigma,
                   "dividend_yield": q, "option_type": option_type, "num_sims": num_sims},
        "analytic_black_scholes": round(float(analytic), 5),
        "control_variate_beta": round(float(c), 5),
        "methods": [
            row("plain_monte_carlo", plain_price, plain_se, num_sims),
            row("antithetic_variates", anti_price, anti_se, num_sims),
            row("control_variate", cv_price, cv_se, num_sims),
            row("antithetic_plus_control", both_price, both_se, num_sims),
        ],
        "interpretation": (
            "Standard error falls as 1/sqrt(N), so halving it by brute force costs 4x the "
            "paths. A control variate achieves comparable or better reduction at no extra "
            "path cost. The variance_reduction_factor column is the equivalent multiple of "
            "paths each technique saves."
        ),
    }
