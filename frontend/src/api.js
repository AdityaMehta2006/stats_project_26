/**
 * api.js
 * ------
 * Centralized API client for the FastAPI backend.
 * All analysis endpoints accept dynamic ticker/pair parameters.
 */

const API_BASE = "http://localhost:8000/api";

async function fetchJSON(endpoint, signal) {
  const res = await fetch(`${API_BASE}${endpoint}`, { signal });
  if (!res.ok) {
    // The backend explains itself in the body (e.g. an unknown ticker answers
    // 404 with a readable message). Showing "API error 404: Not Found" instead
    // throws that away and leaves the user with nothing to act on.
    const msg = await res
      .json()
      .then((b) => [b.error, b.detail].filter(Boolean).join(" "))
      .catch(() => "");
    throw new Error(msg || `API error ${res.status}: ${res.statusText}`);
  }
  return res.json();
}

// Health
export const checkHealth = () => fetchJSON("/health");

// Ticker search & validation
export const searchTickers = (query) =>
  fetchJSON(`/search?q=${encodeURIComponent(query)}`);
export const validateTicker = (ticker) =>
  fetchJSON(`/validate?ticker=${encodeURIComponent(ticker)}`);
export const getAvailableForex = () => fetchJSON("/forex/available");

// Pillar 1: Macro Regression — accepts any equity ticker
export const getMacroOLS = (ticker = "^GSPC", maxLag = 3) =>
  fetchJSON(`/macro-regression/ols?ticker=${encodeURIComponent(ticker)}&max_lag=${maxLag}`);
export const getMacroGranger = (ticker = "^GSPC", maxLag = 4) =>
  fetchJSON(`/macro-regression/granger?ticker=${encodeURIComponent(ticker)}&max_lag=${maxLag}`);
export const getMacroHeatmap = (ticker = "^GSPC", maxLag = 3) =>
  fetchJSON(`/macro-regression/heatmap?ticker=${encodeURIComponent(ticker)}&max_lag=${maxLag}`);
export const getMacroTimeSeries = (ticker = "^GSPC") =>
  fetchJSON(`/macro-regression/timeseries?ticker=${encodeURIComponent(ticker)}`);

// Pillar 2: GARCH — accepts any ticker
export const getGarchFit = (ticker = "^GSPC", dist = "t") =>
  fetchJSON(`/garch/fit?ticker=${encodeURIComponent(ticker)}&dist=${dist}`);
export const getGarchClustering = (ticker = "^GSPC") =>
  fetchJSON(`/garch/clustering?ticker=${encodeURIComponent(ticker)}`);
export const getGarchDistribution = (ticker = "^GSPC") =>
  fetchJSON(`/garch/distribution?ticker=${encodeURIComponent(ticker)}`);
export const getGarchCompare = (ticker = "^GSPC") =>
  fetchJSON(`/garch/compare?ticker=${encodeURIComponent(ticker)}`);

// Pillar 3: Pair Trading — accepts custom forex pair list
export const getPairsCointegration = (pairs = null) => {
  const q = pairs ? `?pairs=${encodeURIComponent(pairs.join(","))}` : "";
  return fetchJSON(`/pairs/cointegration${q}`);
};
export const getPairsBest = (pairs = null) => {
  const q = pairs ? `?pairs=${encodeURIComponent(pairs.join(","))}` : "";
  return fetchJSON(`/pairs/best${q}`);
};
export const getPairsCorrelation = (pairs = null) => {
  const q = pairs ? `?pairs=${encodeURIComponent(pairs.join(","))}` : "";
  return fetchJSON(`/pairs/correlation${q}`);
};

// Options — Black-Scholes price, Greeks, and implied-vs-realised vol.
// `strike` blank means at-the-money, `expiry` blank means the ~30-day contract.
export const getBlackScholes = (ticker = "^GSPC", option = "call", strike = null, expiry = null) =>
  fetchJSON(
    `/options/black-scholes?ticker=${encodeURIComponent(ticker)}&option=${option}` +
      (strike ? `&strike=${strike}` : "") +
      (expiry ? `&expiry=${expiry}` : "")
  );

// Decision engine — fused verdict over all three pillars.
// These sit above the per-pillar endpoints above; they don't replace them.
export const getLlmInfo = () => fetchJSON("/llm/info");

const pairsQ = (pairs, lead = "?") =>
  pairs && pairs.length ? `${lead}pairs=${encodeURIComponent(pairs.join(","))}` : "";

export const getEngineFeed = (pairs = null, limit = 12, signal) =>
  fetchJSON(`/engine/feed?limit=${limit}${pairsQ(pairs, "&")}`, signal);

export const getEngineAsset = (ticker = "^GSPC", pairs = null, signal) =>
  fetchJSON(
    `/engine/asset?ticker=${encodeURIComponent(ticker)}${pairsQ(pairs, "&")}`,
    signal
  );

export const getEngineStatus = (signal) => fetchJSON("/engine/status", signal);

/** URL only — the narration is server-sent events, consumed by EventSource. */
export const narrateURL = (ticker = "^GSPC", pairs = null) =>
  `${API_BASE}/engine/narrate?ticker=${encodeURIComponent(ticker)}${pairsQ(pairs, "&")}`;

export const getRecommendations = (ticker = "^GSPC", useLlm = false, pairs = null) => {
  const p = pairs ? `&pairs=${encodeURIComponent(pairs.join(","))}` : "";
  return fetchJSON(`/recommendations?ticker=${encodeURIComponent(ticker)}&use_llm=${useLlm}${p}`);
};

// ---------------------------------------------------------------------------
// Pillar 4: Options pricing — parameter-driven (theory) and market-wired
// ---------------------------------------------------------------------------

const qs = (params) =>
  Object.entries(params)
    .filter(([, v]) => v !== null && v !== undefined && v !== "")
    .map(([k, v]) => `${k}=${encodeURIComponent(v)}`)
    .join("&");

/** All models on one parameter set, with put-call parity + finite-difference validation. */
export const getOptionsMultiMarket = (p = {}) =>
  fetchJSON(`/options/multi-market?${qs({
    spot: 100, strike: 100, t_years: 0.25, rate: 0.05, sigma: 0.2,
    dividend: 0, option: "call", ...p,
  })}`);

/** GBM / Merton / Heston / Longstaff-Schwartz Monte Carlo vs their exact benchmarks. */
export const getOptionsSDE = (p = {}) =>
  fetchJSON(`/options/stochastic-sde?${qs({
    spot: 100, strike: 100, t_years: 0.25, rate: 0.05, sigma: 0.2,
    sims: 20000, option: "call", ...p,
  })}`);

/** Implied-vol smile: flat Black-Scholes vs curved Merton and Heston. */
export const getOptionsSmile = (p = {}) =>
  fetchJSON(`/options/smile?${qs({
    spot: 100, t_years: 1.0, rate: 0.05, sigma: 0.2, dividend: 0,
    lambda_jump: 0.75, mu_jump: -0.1, sigma_jump: 0.15,
    kappa: 2.0, xi: 0.4, rho: -0.7, strikes: 25, ...p,
  })}`);

/** Binomial lattice convergence + American early-exercise premium. */
export const getBinomialConvergence = (p = {}) =>
  fetchJSON(`/options/binomial-convergence?${qs({
    spot: 100, strike: 100, t_years: 1.0, rate: 0.05, sigma: 0.2,
    dividend: 0, option: "put", ...p,
  })}`);

// --- Market-wired options

/** Every model priced on a real ticker with market-derived inputs. */
export const getMarketOption = (ticker = "^GSPC", p = {}) =>
  fetchJSON(`/market-options/analyze?${qs({ ticker, option: "call", include_chain: true, ...p })}`);

/** GARCH(1,1) volatility forecast and its term structure. */
export const getVolTermStructure = (ticker = "^GSPC", horizonDays = 30) =>
  fetchJSON(`/market-options/vol-term-structure?${qs({ ticker, horizon_days: horizonDays })}`);

/** Smiles calibrated to this ticker, plus the observed market smile if listed. */
export const getMarketSmile = (ticker = "^GSPC", days = 60) =>
  fetchJSON(`/market-options/smile?${qs({ ticker, days })}`);

/** Live implied-vol surface from the option chain. */
export const getMarketChain = (ticker = "AAPL", maxExpiries = 4) =>
  fetchJSON(`/market-options/chain?${qs({ ticker, max_expiries: maxExpiries })}`);

/** Garman-Kohlhagen on a real FX pair with both legs' policy rates. */
export const getFxOption = (pair = "EURUSD", p = {}) =>
  fetchJSON(`/market-options/fx?${qs({ pair, days: 30, option: "call", ...p })}`);

/** Merton jump parameters fitted from the ticker's own return distribution. */
export const getJumpCalibration = (ticker = "^GSPC") =>
  fetchJSON(`/market-options/jump-calibration?${qs({ ticker })}`);

// ---------------------------------------------------------------------------
// Pillar 5: Stochastic processes
// ---------------------------------------------------------------------------

/** Sample paths for wiener | gbm | ou | cir | merton | heston. */
export const getStochasticPaths = (process = "gbm", p = {}) =>
  fetchJSON(`/stochastic/paths?${qs({
    process, s0: 100, mu: 0.05, sigma: 0.2, kappa: 2.0, theta: 0,
    rho: -0.7, t_years: 1.0, steps: 252, paths: 6, ...p,
  })}`);

/** Euler-Maruyama vs Milstein vs exact GBM. */
export const getSchemeConvergence = (p = {}) =>
  fetchJSON(`/stochastic/scheme-convergence?${qs({
    s0: 100, mu: 0.05, sigma: 0.4, t_years: 1.0, paths: 20000, ...p,
  })}`);

/** Plain vs antithetic vs control-variate Monte Carlo. */
export const getVarianceReduction = (p = {}) =>
  fetchJSON(`/stochastic/variance-reduction?${qs({
    spot: 100, strike: 100, t_years: 0.25, rate: 0.05, sigma: 0.2,
    dividend: 0, sims: 40000, option: "call", ...p,
  })}`);

/** Ornstein-Uhlenbeck fitted to the live pair-trading spread. */
export const getOuFit = (pairs = null) => {
  const q = pairs ? `?pairs=${encodeURIComponent(pairs.join(","))}` : "";
  return fetchJSON(`/stochastic/ou-fit${q}`);
};
