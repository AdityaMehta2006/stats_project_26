"""
main.py
-------
FastAPI backend serving analysis results for the React dashboard.
All endpoints accept a dynamic ticker/pair selection via query params.
"""

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from contextlib import asynccontextmanager
from typing import List, Optional
import json
import threading
import traceback

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from data_loader import (
    validate_ticker,
    search_tickers,
    get_available_forex,
    NoDataError,
)
from analysis.macro_regression import (
    run_ols_lag_regression,
    run_granger_causality,
    run_correlation_heatmap,
    get_macro_time_series,
)
from analysis.garch import (
    fit_garch,
    get_volatility_clustering_evidence,
    get_return_distribution,
    compare_garch_models,
)
from analysis.pairs import (
    run_cointegration_tests,
    get_best_pair_analysis,
    get_forex_correlation,
    get_full_spread,
)
from analysis.recommender import generate_recommendations
from analysis.black_scholes import analyze_option
from analysis.advanced_options import (
    analyze_advanced_options,
    binomial_convergence,
    heston_stochastic_volatility,
    implied_vol_smile,
    longstaff_schwartz_american,
    merton_jump_diffusion,
    monte_carlo_gbm,
)
from analysis.market_options import (
    analyze_fx_option,
    analyze_market_option,
    fit_jump_params,
    garch_vol_term_structure,
    get_market_iv_surface,
    market_smile,
)
from analysis.stochastic import (
    cir_paths,
    fit_ou,
    gbm_paths,
    gbm_scheme_comparison,
    heston_paths,
    merton_paths,
    ou_paths,
    variance_reduction_study,
    wiener_paths,
)
import llm_client
import engine


def _startup_warm():
    """Pre-compute the universe and poke the model, so the first user request
    isn't the one that pays for both."""
    llm_client.prewarm()
    engine.warm()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Daemon thread: a ~20s cold sweep must not hold up the port binding.
    threading.Thread(target=_startup_warm, daemon=True).start()
    yield


app = FastAPI(
    title="Quantitative Anomalies API",
    description="Backend for financial markets anomaly analysis dashboard — supports any ticker",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS — allow React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# An unknown symbol is a user typo, not a server fault. Answer 404 with
# something readable — this used to surface as a 500 quoting an internal cache
# key ("Download returned empty data for 'equity_ZZZNOTREAL'").
@app.exception_handler(NoDataError)
async def no_data_handler(request: Request, exc: NoDataError):
    return JSONResponse(
        status_code=404,
        content={
            "error": "No market data for that symbol.",
            "detail": "Check the ticker and try again — search suggests valid symbols as you type.",
        },
    )


# Global exception handler — returns JSON errors with CORS headers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    tb = traceback.format_exc()
    print(f"ERROR in {request.url}: {exc}\n{tb}")
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "detail": "Analysis failed. Check backend logs."},
    )


# ---------------------------------------------------------------------------
# Health check & Ticker utilities
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/search")
def ticker_search(q: str = Query(..., description="Search query for tickers")):
    """Search for tickers on Yahoo Finance."""
    return {"results": search_tickers(q)}


@app.get("/api/validate")
def ticker_validate(ticker: str = Query(..., description="Ticker symbol to validate")):
    """Validate a specific ticker symbol."""
    return validate_ticker(ticker)


@app.get("/api/forex/available")
def forex_available():
    """List all available forex pairs."""
    return {"pairs": get_available_forex()}


# ---------------------------------------------------------------------------
# Pillar 1: Macro Factor & Lag Regression
# ---------------------------------------------------------------------------

@app.get("/api/macro-regression/ols")
def macro_ols(
    ticker: str = Query("^GSPC", description="Equity ticker symbol"),
    max_lag: int = Query(3, description="Maximum lag depth"),
):
    """OLS regression with lagged macro factors for any ticker."""
    return run_ols_lag_regression(ticker=ticker, max_lag=max_lag)


@app.get("/api/macro-regression/granger")
def macro_granger(
    ticker: str = Query("^GSPC", description="Equity ticker symbol"),
    max_lag: int = Query(4, description="Maximum lag depth"),
):
    """Granger causality tests for any ticker."""
    return run_granger_causality(ticker=ticker, max_lag=max_lag)


@app.get("/api/macro-regression/heatmap")
def macro_heatmap(
    ticker: str = Query("^GSPC", description="Equity ticker symbol"),
    max_lag: int = Query(3, description="Maximum lag depth"),
):
    """Correlation heatmap data for any ticker."""
    return run_correlation_heatmap(ticker=ticker, max_lag=max_lag)


@app.get("/api/macro-regression/timeseries")
def macro_ts(
    ticker: str = Query("^GSPC", description="Equity ticker symbol"),
):
    """Raw macro time series for plotting."""
    return get_macro_time_series(ticker=ticker)


# ---------------------------------------------------------------------------
# Pillar 2: GARCH & Volatility
# ---------------------------------------------------------------------------

@app.get("/api/garch/fit")
def garch_fit(
    ticker: str = Query("^GSPC", description="Equity/asset ticker symbol"),
    dist: str = Query("t", description="Error distribution: normal, t, skewt"),
):
    """Fit GARCH(1,1) for any ticker."""
    return fit_garch(ticker=ticker, dist=dist)


@app.get("/api/garch/clustering")
def garch_clustering(
    ticker: str = Query("^GSPC", description="Equity/asset ticker symbol"),
):
    """Volatility clustering evidence (ACF, Ljung-Box) for any ticker."""
    return get_volatility_clustering_evidence(ticker=ticker)


@app.get("/api/garch/distribution")
def garch_distribution(
    ticker: str = Query("^GSPC", description="Equity/asset ticker symbol"),
):
    """Return distribution analysis for any ticker."""
    return get_return_distribution(ticker=ticker)


@app.get("/api/garch/compare")
def garch_compare(
    ticker: str = Query("^GSPC", description="Equity/asset ticker symbol"),
):
    """Compare GARCH models with different distributions."""
    return compare_garch_models(ticker=ticker)


# ---------------------------------------------------------------------------
# Pillar 3: Forex Pair Trading
# ---------------------------------------------------------------------------

@app.get("/api/pairs/cointegration")
def pairs_coint(
    pairs: Optional[str] = Query(
        None,
        description="Comma-separated forex pair labels, e.g. EURUSD,GBPUSD,USDJPY. Omit for defaults.",
    ),
):
    """Cointegration tests for forex pair combinations."""
    pair_list = [p.strip() for p in pairs.split(",")] if pairs else None
    return run_cointegration_tests(pair_labels=pair_list)


@app.get("/api/pairs/best")
def pairs_best(
    pairs: Optional[str] = Query(
        None,
        description="Comma-separated forex pair labels. Omit for defaults.",
    ),
):
    """Best cointegrated pair: spread, z-score, signals."""
    pair_list = [p.strip() for p in pairs.split(",")] if pairs else None
    return get_best_pair_analysis(pair_labels=pair_list)


@app.get("/api/pairs/correlation")
def pairs_corr(
    pairs: Optional[str] = Query(
        None,
        description="Comma-separated forex pair labels. Omit for defaults.",
    ),
):
    """Forex correlation matrix."""
    pair_list = [p.strip() for p in pairs.split(",")] if pairs else None
    return get_forex_correlation(pair_labels=pair_list)


# ---------------------------------------------------------------------------
# Recommendation / Anomaly–Opportunity Engine
# ---------------------------------------------------------------------------

@app.get("/api/llm/info")
def llm_info():
    """Report the configured LLM provider and whether it is available."""
    return llm_client.info()


@app.get("/api/recommendations")
def recommendations(
    ticker: str = Query("^GSPC", description="Equity/asset ticker symbol"),
    pairs: Optional[str] = Query(None, description="Comma-separated forex pairs; omit for defaults"),
    use_llm: bool = Query(False, description="Generate a natural-language note via the local LLM"),
):
    """Scan a ticker (+ forex pairs) for anomalies/opportunities and rank them."""
    pair_list = [p.strip() for p in pairs.split(",")] if pairs else None
    return generate_recommendations(ticker=ticker, pairs=pair_list, use_llm=use_llm)


# ---------------------------------------------------------------------------
# Decision engine
#
# These sit above the per-module endpoints above — they do not replace them.
# Every signal carries `source` + `asset` so the UI can drill from a verdict
# straight into the macro / GARCH / pairs endpoint that produced it.
# ---------------------------------------------------------------------------

def _pairs(pairs: Optional[str]):
    return [p.strip() for p in pairs.split(",")] if pairs else None


@app.get("/api/engine/feed")
def engine_feed(
    pairs: Optional[str] = Query(None, description="Comma-separated forex pairs; omit for defaults"),
    limit: int = Query(12, description="Max signals in the ranked feed"),
):
    """Ranked cross-asset opportunities. Served from warm caches after startup."""
    return engine.scan_universe(pairs=_pairs(pairs), limit=limit)


@app.get("/api/engine/asset")
def engine_asset(
    ticker: str = Query("^GSPC", description="Any Yahoo ticker — need not be in the universe"),
    pairs: Optional[str] = Query(None, description="Comma-separated forex pairs; omit for defaults"),
):
    """Fused verdict plus every signal for one asset, with per-detector diagnostics."""
    return engine.scan_asset(ticker, pairs=_pairs(pairs))


@app.get("/api/engine/narrate")
def engine_narrate(
    ticker: str = Query("^GSPC", description="Asset to explain"),
    pairs: Optional[str] = Query(None, description="Comma-separated forex pairs; omit for defaults"),
):
    """
    Server-sent events: the model's own stance first (~10 tokens in), then the
    explanation streamed token by token, then a `done` frame carrying the
    number-guardrail result. The computed verdict is already on screen by the
    time this is called — nothing here blocks first paint.
    """
    scan = engine.scan_asset(ticker, pairs=_pairs(pairs))

    def events():
        try:
            for event, data in engine.narrate_stream(scan):
                yield f"event: {event}\ndata: {json.dumps(data)}\n\n"
        except Exception as e:  # noqa: BLE001 — a stream can't return a 500 mid-flight
            yield f"event: done\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/engine/status")
def engine_status():
    """Data freshness, warm state, and LLM health — drives the UI's status strip."""
    info = engine._garch_tier.cache_info()
    return {
        "llm": llm_client.info(),
        "universe": engine.UNIVERSE,
        "data_asof": engine._data_date("^GSPC"),
        "warm_assets": info.currsize,
        "warm": info.currsize >= len(engine.UNIVERSE),
    }


# ---------------------------------------------------------------------------
# Options — Black-Scholes
# ---------------------------------------------------------------------------

@app.get("/api/options/black-scholes")
def options_black_scholes(
    ticker: str = Query("^GSPC", description="Underlying ticker symbol"),
    strike: Optional[float] = Query(None, description="Strike price; omit for at-the-money"),
    expiry: Optional[str] = Query(None, description="Expiry date YYYY-MM-DD; omit for ~30 days"),
    option: str = Query("call", description="call or put"),
):
    """Black-Scholes price + Greeks for an option, with optional live-chain vol comparison."""
    return analyze_option(ticker=ticker, strike=strike, expiry=expiry, option=option)


@app.get("/api/options/multi-market")
def options_multi_market(
    spot: float = Query(100.0, description="Underlying Spot / Asset Price"),
    strike: float = Query(100.0, description="Option Strike Price"),
    t_years: float = Query(0.25, description="Time to expiry in years"),
    rate: float = Query(0.05, description="Domestic risk-free rate decimal"),
    sigma: float = Query(0.20, description="Annualized volatility decimal"),
    dividend: float = Query(0.0, description="Dividend yield / Foreign rate decimal"),
    option: str = Query("call", description="call or put"),
):
    """
    Every pricing model on one parameter set, with validation.
    BSM equity, Garman-Kohlhagen FX, Black-76 commodities, Bachelier normal,
    binomial lattice (European + American), Merton, Heston, Monte Carlo, full
    Greeks, plus put-call parity and finite-difference checks.
    """
    return analyze_advanced_options(S=spot, K=strike, T=t_years, r=rate,
                                    sigma=sigma, q=dividend, option_type=option)


@app.get("/api/options/stochastic-sde")
def options_stochastic_sde(
    spot: float = Query(100.0, description="Spot Price"),
    strike: float = Query(100.0, description="Strike Price"),
    t_years: float = Query(0.25, description="Time to expiry in years"),
    rate: float = Query(0.05, description="Risk-free rate"),
    sigma: float = Query(0.20, description="Volatility"),
    sims: int = Query(20000, description="Number of Monte Carlo simulations"),
    option: str = Query("call", description="call or put"),
):
    """
    SDE Monte Carlo comparison — GBM, Merton jump-diffusion, Heston stochastic
    volatility and Longstaff-Schwartz American, each reported next to the exact
    analytic price for the same model so simulation error is visible.
    """
    gbm_res = monte_carlo_gbm(S=spot, K=strike, T=t_years, r=rate, sigma=sigma,
                              num_sims=sims, option_type=option)
    merton_res = merton_jump_diffusion(S=spot, K=strike, T=t_years, r=rate, sigma=sigma,
                                       num_sims=sims, option_type=option)
    heston_res = heston_stochastic_volatility(S=spot, K=strike, T=t_years, r=rate,
                                              v0=sigma ** 2, num_sims=min(sims, 20000),
                                              option_type=option)
    lsm_res = longstaff_schwartz_american(S=spot, K=strike, T=t_years, r=rate, sigma=sigma,
                                          num_sims=min(sims, 40000), option_type=option)
    return {
        "inputs": {"spot": spot, "strike": strike, "T_years": t_years, "rate": rate,
                   "sigma": sigma, "simulations": sims, "option_type": option},
        "models": {
            "geometric_brownian_motion": gbm_res,
            "merton_jump_diffusion": merton_res,
            "heston_stochastic_volatility": heston_res,
            "longstaff_schwartz_american": lsm_res,
        },
    }


@app.get("/api/options/smile")
def options_smile(
    spot: float = Query(100.0, description="Spot price"),
    t_years: float = Query(1.0, description="Time to expiry in years"),
    rate: float = Query(0.05, description="Risk-free rate"),
    sigma: float = Query(0.20, description="Base volatility"),
    dividend: float = Query(0.0, description="Dividend yield"),
    lambda_jump: float = Query(0.75, description="Merton jump intensity per year"),
    mu_jump: float = Query(-0.10, description="Mean log jump size"),
    sigma_jump: float = Query(0.15, description="Std dev of log jump size"),
    kappa: float = Query(2.0, description="Heston mean-reversion speed"),
    xi: float = Query(0.4, description="Heston vol-of-vol"),
    rho: float = Query(-0.7, description="Heston spot/vol correlation"),
    strikes: int = Query(25, description="Number of strikes across the smile"),
):
    """
    Implied-volatility smile for Black-Scholes (flat by construction), Merton
    (jumps) and Heston (stochastic vol). The headline result of the module.
    """
    return implied_vol_smile(
        S=spot, T=t_years, r=rate, sigma=sigma, q=dividend,
        lambda_jump=lambda_jump, mu_jump=mu_jump, sigma_jump=sigma_jump,
        kappa=kappa, xi=xi, rho=rho, num_strikes=strikes,
    )


@app.get("/api/options/binomial-convergence")
def options_binomial_convergence(
    spot: float = Query(100.0, description="Spot price"),
    strike: float = Query(100.0, description="Strike price"),
    t_years: float = Query(1.0, description="Time to expiry in years"),
    rate: float = Query(0.05, description="Risk-free rate"),
    sigma: float = Query(0.20, description="Volatility"),
    dividend: float = Query(0.0, description="Dividend yield"),
    option: str = Query("put", description="call or put (puts show the early-exercise premium)"),
):
    """Lattice convergence to Black-Scholes plus the American early-exercise premium."""
    return binomial_convergence(S=spot, K=strike, T=t_years, r=rate, sigma=sigma,
                                q=dividend, option_type=option)


# ---------------------------------------------------------------------------
# Options wired to live market data
# ---------------------------------------------------------------------------

@app.get("/api/market-options/analyze")
def market_options_analyze(
    ticker: str = Query("^GSPC", description="Underlying ticker symbol"),
    strike: Optional[float] = Query(None, description="Strike; omit for at-the-money"),
    expiry: Optional[str] = Query(None, description="Expiry YYYY-MM-DD; omit for ~30 days"),
    option: str = Query("call", description="call or put"),
    include_chain: bool = Query(True, description="Compare against the live option chain"),
):
    """
    Price an option on a real ticker with every model using market-derived
    inputs: live spot, 10Y-derived continuously-compounded rate, actual dividend
    yield, GARCH-forecast volatility matched to maturity, jump parameters fitted
    to the return distribution, and Heston seeded from GARCH. Includes the
    variance risk premium versus live quotes.
    """
    return analyze_market_option(ticker=ticker, strike=strike, expiry=expiry,
                                 option_type=option, include_chain=include_chain)


@app.get("/api/market-options/vol-term-structure")
def market_options_vol_term(
    ticker: str = Query("^GSPC", description="Ticker symbol"),
    horizon_days: int = Query(30, description="Forecast horizon in days"),
):
    """GARCH(1,1) volatility forecast and its term structure across maturities."""
    return garch_vol_term_structure(ticker=ticker, horizon_days=horizon_days)


@app.get("/api/market-options/smile")
def market_options_smile(
    ticker: str = Query("^GSPC", description="Ticker symbol"),
    days: int = Query(60, description="Option maturity in days"),
):
    """
    Model smiles calibrated to this ticker's own GARCH and jump parameters,
    alongside the observed market smile where a chain is listed.
    """
    return market_smile(ticker=ticker, days=days)


@app.get("/api/market-options/chain")
def market_options_chain(
    ticker: str = Query("AAPL", description="Ticker with a listed option chain"),
    max_expiries: int = Query(4, description="Number of expiries to pull"),
):
    """Live implied-volatility surface, recomputed from mid prices with our own solver."""
    return get_market_iv_surface(ticker=ticker, max_expiries=max_expiries)


@app.get("/api/market-options/fx")
def market_options_fx(
    pair: str = Query("EURUSD", description="Six-letter FX pair, e.g. EURUSD"),
    strike: Optional[float] = Query(None, description="Strike; omit for at-the-money"),
    days: int = Query(30, description="Days to expiry"),
    option: str = Query("call", description="call or put"),
):
    """Garman-Kohlhagen on a real currency pair, using both legs' policy rates."""
    return analyze_fx_option(pair=pair, strike=strike, days=days, option_type=option)


@app.get("/api/market-options/jump-calibration")
def market_options_jump_calibration(
    ticker: str = Query("^GSPC", description="Ticker symbol"),
):
    """Merton jump parameters fitted from the ticker's own return distribution."""
    return fit_jump_params(ticker=ticker)


# ---------------------------------------------------------------------------
# Stochastic processes — the mathematical substrate
# ---------------------------------------------------------------------------

@app.get("/api/stochastic/paths")
def stochastic_paths(
    process: str = Query("gbm", description="wiener | gbm | ou | cir | merton | heston"),
    s0: float = Query(100.0, description="Initial value"),
    mu: float = Query(0.05, description="Drift (GBM) / risk-free rate (Heston)"),
    sigma: float = Query(0.20, description="Volatility / diffusion coefficient"),
    kappa: float = Query(2.0, description="Mean-reversion speed (OU, CIR, Heston)"),
    theta: float = Query(0.0, description="Long-run level (OU) / long-run variance (CIR, Heston)"),
    rho: float = Query(-0.7, description="Spot/vol correlation (Heston)"),
    t_years: float = Query(1.0, description="Time horizon in years"),
    steps: int = Query(252, description="Number of time steps"),
    paths: int = Query(6, description="Number of sample paths"),
    seed: Optional[int] = Query(None, description="Random seed for reproducibility"),
):
    """
    Simulate sample paths of a stochastic process, with theoretical moments
    reported alongside the empirical ones.
    """
    p = process.lower()
    if p == "wiener":
        return {"process": "wiener",
                **wiener_paths(T=t_years, num_steps=steps, num_paths=paths, seed=seed)}
    if p == "ou":
        return {"process": "ornstein_uhlenbeck",
                **ou_paths(X0=s0, kappa=kappa, theta=theta, sigma=sigma, T=t_years,
                           num_steps=steps, num_paths=paths, seed=seed)}
    if p == "cir":
        v0 = s0 if 0 < s0 < 1 else sigma ** 2
        th = theta if theta > 0 else sigma ** 2
        return {"process": "cox_ingersoll_ross",
                **cir_paths(v0=v0, kappa=kappa, theta=th, xi=sigma, T=t_years,
                            num_steps=steps, num_paths=paths, seed=seed)}
    if p == "merton":
        return {"process": "merton_jump_diffusion",
                **merton_paths(S0=s0, mu=mu, sigma=sigma, T=t_years,
                               num_steps=steps, num_paths=paths, seed=seed)}
    if p == "heston":
        v0 = sigma ** 2
        th = theta if theta > 0 else v0
        return {"process": "heston",
                **heston_paths(S0=s0, r=mu, v0=v0, kappa=kappa, theta=th,
                               xi=min(sigma * 1.5, 0.6), rho=rho, T=t_years,
                               num_steps=steps, num_paths=paths, seed=seed)}
    return {"process": "geometric_brownian_motion",
            **gbm_paths(S0=s0, mu=mu, sigma=sigma, T=t_years,
                        num_steps=steps, num_paths=paths, seed=seed)}


@app.get("/api/stochastic/scheme-convergence")
def stochastic_scheme_convergence(
    s0: float = Query(100.0, description="Initial price"),
    mu: float = Query(0.05, description="Drift"),
    sigma: float = Query(0.40, description="Volatility (high values show the gap clearly)"),
    t_years: float = Query(1.0, description="Horizon in years"),
    paths: int = Query(20000, description="Monte Carlo paths per step count"),
):
    """Euler-Maruyama vs Milstein vs exact GBM — strong order 0.5 against 1.0."""
    return gbm_scheme_comparison(S0=s0, mu=mu, sigma=sigma, T=t_years,
                                 num_paths=paths, seed=42)


@app.get("/api/stochastic/variance-reduction")
def stochastic_variance_reduction(
    spot: float = Query(100.0, description="Spot price"),
    strike: float = Query(100.0, description="Strike price"),
    t_years: float = Query(0.25, description="Time to expiry"),
    rate: float = Query(0.05, description="Risk-free rate"),
    sigma: float = Query(0.20, description="Volatility"),
    dividend: float = Query(0.0, description="Dividend yield"),
    sims: int = Query(40000, description="Monte Carlo paths"),
    option: str = Query("call", description="call or put"),
):
    """Plain vs antithetic vs control-variate vs both — standard errors compared."""
    return variance_reduction_study(S0=spot, K=strike, T=t_years, r=rate, sigma=sigma,
                                    q=dividend, num_sims=sims, option_type=option, seed=42)


@app.get("/api/stochastic/ou-fit")
def stochastic_ou_fit(
    pairs: Optional[str] = Query(None, description="Comma-separated forex pairs; omit for defaults"),
):
    """
    Fit an Ornstein-Uhlenbeck process to the live pair-trading spread.

    The explicit bridge between stochastic calculus and Pillar 3: OU is the
    continuous-time model the pairs strategy assumes, and its half-life
    ln(2)/kappa is exactly the number the Pairs tab reports.
    """
    pair_list = [p.strip() for p in pairs.split(",")] if pairs else None

    # Use the FULL daily spread, not the chart's subsampled series. Fitting on
    # the subsample would estimate kappa per ~3 days and understate the
    # half-life by that factor — the two half-lives must be directly comparable
    # for the comparison below to mean anything.
    full = get_full_spread(pair_labels=pair_list)
    if "error" in full:
        return full

    best = get_best_pair_analysis(pair_labels=pair_list)
    fit = fit_ou(full["spread"], dt=1.0)

    pairs_hl = best.get("half_life_days")
    ou_hl = fit.get("half_life")
    agree = None
    if pairs_hl and ou_hl:
        agree = abs(pairs_hl - ou_hl) / max(pairs_hl, ou_hl) < 0.10

    return {
        "pair": f"{full['pair_a']}/{full['pair_b']}",
        "coint_pvalue": full["coint_pvalue"],
        "hedge_ratio": full["hedge_ratio"],
        "n_obs": full["n_obs"],
        "frequency": full["frequency"],
        "pairs_module_half_life_days": pairs_hl,
        "ou_fit": fit,
        "half_lives_agree": agree,
        "note": (
            "Both estimates use the same full daily spread. The pairs module regresses the "
            "spread's first difference on its lag; this fits the OU transition directly. "
            "Discretising dX = kappa(theta - X)dt + sigma dW *is* that regression, so the two "
            "half-lives should agree closely — which is the point of computing them "
            "independently."
        ),
    }


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    # reload=True requires an import string, not the app object — passing the
    # object made `python main.py` exit immediately with
    # "You must pass the application as an import string to enable 'reload'".
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
