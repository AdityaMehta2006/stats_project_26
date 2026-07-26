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
