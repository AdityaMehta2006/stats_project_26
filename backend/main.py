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
)
from analysis.recommender import generate_recommendations
from analysis.black_scholes import analyze_option
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


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    # reload=True requires an import string, not the app object — passing the
    # object made `python main.py` exit immediately with
    # "You must pass the application as an import string to enable 'reload'".
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
